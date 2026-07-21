from datetime import date

import pytest
from pydantic import TypeAdapter, ValidationError

from orchestra.billing import PricingRegistry, PricingRule
from orchestra.core.confidence import Signal, calculate_with_explanation
from orchestra.protocol import StructuredResearchObject
from orchestra.research.similarity import TokenOverlapSimilarity, fingerprint


def test_protocol_discrimination_and_rejects_extra_fields():
    adapter = TypeAdapter(StructuredResearchObject)
    value = adapter.validate_python({"type": "hypothesis", "statement": "P", "provenance": {"execution_mode": "mock"}})
    assert value.type == "hypothesis"
    with pytest.raises(ValidationError):
        adapter.validate_python({"type": "hypothesis", "statement": "P", "provenance": {"execution_mode": "mock"}, "secret": "x"})


def test_confidence_is_bounded_and_explained():
    result = calculate_with_explanation([Signal("formal", 0.9), Signal("counterexample", 2, False)])
    assert result["score"] == 0 and result["signals"] and "not mathematical truth" in result["disclaimer"]


def test_similarity_and_fingerprint_are_deterministic():
    assert fingerprint("Fourier Method", ["Compact"], "Diagonal") == fingerprint("fourier method", ["compact"], "diagonal")
    assert TokenOverlapSimilarity().score("fourier diagonal", "diagonal Fourier method") > 0.5


def test_versioned_pricing_registry():
    registry = PricingRegistry()
    rule = PricingRule("test", "model", 1_000_000, 2_000_000, "USD", date(2026, 1, 1), 0.1, "reviewed fixture")
    registry.add_reviewed_rule(rule)
    assert registry.calculate(rule, 1000, 500) == 2200
