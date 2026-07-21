"""Deterministic, provider-free negative-knowledge similarity."""

from __future__ import annotations

import hashlib
import re
from abc import ABC, abstractmethod


def normalize(text: str) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", text.lower()))


def fingerprint(strategy: str, assumptions: list[str], method: str = "") -> str:
    material = "|".join([normalize(strategy), normalize(method), *sorted(normalize(x) for x in assumptions)])
    return hashlib.sha256(material.encode()).hexdigest()


class SimilarityEngine(ABC):
    @abstractmethod
    def score(self, left: str, right: str) -> float: ...


class TokenOverlapSimilarity(SimilarityEngine):
    def score(self, left: str, right: str) -> float:
        a, b = set(normalize(left).split()), set(normalize(right).split())
        return len(a & b) / len(a | b) if a and b else 0.0
