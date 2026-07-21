"""Redis-backed fixed-window request limiting with a bounded local fallback."""

from __future__ import annotations

import hashlib
import threading
import time


class RateLimiter:
    def __init__(self, redis_url: str = ""):
        self.redis = None
        if redis_url:
            import redis.asyncio as redis

            self.redis = redis.Redis.from_url(redis_url, decode_responses=True)
        self.local: dict[str, tuple[int, int]] = {}
        self.lock = threading.Lock()

    async def check(self, identity: str, bucket: str, limit: int, window_seconds: int = 60) -> tuple[bool, int]:
        window = int(time.time()) // window_seconds
        digest = hashlib.sha256(identity.encode()).hexdigest()[:24]
        key = f"orchestra:rate:{bucket}:{digest}:{window}"
        if self.redis:
            count = await self.redis.incr(key)
            if count == 1:
                await self.redis.expire(key, window_seconds + 1)
        else:
            with self.lock:
                previous_window, previous_count = self.local.get(key, (window, 0))
                count = previous_count + 1 if previous_window == window else 1
                self.local[key] = (window, count)
                if len(self.local) > 10_000:
                    self.local = {item_key: value for item_key, value in self.local.items() if value[0] >= window - 1}
        retry_after = window_seconds - (int(time.time()) % window_seconds)
        return count <= limit, retry_after
