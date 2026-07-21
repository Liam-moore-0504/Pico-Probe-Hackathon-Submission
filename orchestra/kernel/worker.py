"""Redis-backed durable Pico Probe worker process."""

from __future__ import annotations

import asyncio
import logging
import socket
from datetime import UTC, datetime, timedelta

import redis

from orchestra.api.app import create_app
from orchestra.config import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("orchestra.worker")


async def main() -> None:
    if not settings.redis_url:
        raise RuntimeError("ORCHESTRA_REDIS_URL is required for a distributed worker")
    app = create_app(settings)
    scheduler = app.state.scheduler
    client = redis.Redis.from_url(settings.redis_url, decode_responses=True)
    worker_id = socket.gethostname()
    logger.info("worker_started id=%s", worker_id)
    while True:
        stale_before = (datetime.now(UTC) - timedelta(minutes=5)).isoformat()
        stale = scheduler.repo.all("SELECT id FROM jobs WHERE status IN ('queued','retrying') OR (status IN ('claimed','running') AND locked_at<?) ORDER BY priority DESC,created_at LIMIT 100", (stale_before,))
        queued = set(client.lrange("orchestra:jobs", 0, -1))
        for row in stale:
            if row["id"] not in queued:
                client.lpush("orchestra:jobs", row["id"])
        item = await asyncio.to_thread(client.brpop, "orchestra:jobs", 5)
        if not item:
            continue
        _, job_id = item
        try:
            task = asyncio.create_task(scheduler.execute_persisted(job_id, worker_id))
            while not task.done():
                scheduler.repo.execute(
                    "UPDATE jobs SET locked_at=?,updated_at=? WHERE id=? AND locked_by=? AND status IN ('claimed','running')",
                    (datetime.now(UTC).isoformat(), datetime.now(UTC).isoformat(), job_id, worker_id),
                )
                cancellation = scheduler.repo.one("SELECT cancellation_requested FROM jobs WHERE id=?", (job_id,))
                if cancellation and cancellation["cancellation_requested"]:
                    task.cancel()
                    break
                await asyncio.sleep(0.5)
            await task
        except Exception:
            logger.exception("job_failed id=%s", job_id)


if __name__ == "__main__":
    asyncio.run(main())
