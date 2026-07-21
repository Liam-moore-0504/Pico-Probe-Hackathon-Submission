"""Versioned pricing rules; values must be populated by reviewed administration."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class PricingRule:
    provider: str
    model_pattern: str
    input_micros_per_million: int
    output_micros_per_million: int
    currency: str
    effective_date: date
    markup: float
    source: str


class PricingRegistry:
    def __init__(self):
        self._rules: list[PricingRule] = []

    def add_reviewed_rule(self, rule: PricingRule) -> None:
        self._rules.append(rule)

    def find(self, provider: str, model: str) -> PricingRule | None:
        matches = [r for r in self._rules if r.provider == provider and (r.model_pattern == model or r.model_pattern == "*")]
        return sorted(matches, key=lambda r: r.effective_date, reverse=True)[0] if matches else None

    def calculate(self, rule: PricingRule, input_tokens: int, output_tokens: int) -> int:
        base = (input_tokens * rule.input_micros_per_million + output_tokens * rule.output_micros_per_million) / 1_000_000
        return int(round(base * (1 + rule.markup)))
