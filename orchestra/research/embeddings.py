"""Deterministic local feature hashing for privacy-safe semantic retrieval."""

from __future__ import annotations

import hashlib
import math
import re


class HashEmbedding:
    model = "orchestra-hash-embedding-v1"
    dimensions = 256

    def encode(self, text: str) -> list[float]:
        vector = [0.0] * self.dimensions
        tokens = re.findall(r"[a-z0-9]+", text.lower())
        features = tokens + [f"{a}_{b}" for a, b in zip(tokens, tokens[1:], strict=False)]
        for feature in features:
            digest = hashlib.blake2b(feature.encode(), digest_size=8).digest()
            index = int.from_bytes(digest[:4], "big") % self.dimensions
            vector[index] += 1.0 if digest[4] & 1 else -1.0
        norm = math.sqrt(sum(value * value for value in vector)) or 1.0
        return [value / norm for value in vector]

    def similarity(self, left: list[float], right: list[float]) -> float:
        return sum(a * b for a, b in zip(left, right, strict=True))
