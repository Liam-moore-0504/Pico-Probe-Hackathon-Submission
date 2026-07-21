"""Transparent, bounded heuristic confidence scoring (not a probability claim)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Signal:
    name: str
    weight: float
    positive: bool = True
    source: str = "unknown"
    detail: str = ""


def calculate_with_explanation(signals: list[Signal]) -> dict:
    base = 0.2
    contributions = []
    total = base
    for signal in signals:
        signed = abs(signal.weight) if signal.positive else -abs(signal.weight)
        total += signed
        contributions.append(
            {
                "signal": signal.name,
                "contribution": round(signed, 4),
                "source": signal.source,
                "detail": signal.detail,
            }
        )
    score = round(max(0.0, min(1.0, total)), 4)
    return {
        "score": score,
        "base_score": base,
        "signals": contributions,
        "disclaimer": "A transparent heuristic confidence score, not mathematical truth or calibrated probability.",
    }


def calculate(signals: list[Signal]) -> float:
    return calculate_with_explanation(signals)["score"]
