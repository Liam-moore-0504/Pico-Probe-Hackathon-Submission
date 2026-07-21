"""Deterministic, reviewable research-strategy planning."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class StrategyPlan(BaseModel):
    domain: str
    rationale: list[str]
    proposed_pipeline: dict[str, Any]
    expected_evidence: list[str]
    expected_cost: dict[str, int]
    unresolved_capability_gaps: list[str] = Field(default_factory=list)
    human_checkpoints: list[str] = Field(default_factory=list)


ROLE_TEMPLATES = {
    "Formalizer": {"output": "pico.formalization.v1", "obligations": ["state assumptions", "define closed terms", "state falsification conditions"]},
    "Explorer": {"output": "pico.hypotheses.v1", "obligations": ["generate distinct mechanisms", "mark speculation"]},
    "Experimental Designer": {"output": "core.monte_carlo.input.v1", "obligations": ["seed", "trials", "uncertainty"]},
    "Skeptic": {"output": "pico.challenges.v1", "obligations": ["search counterexamples", "do not treat consensus as evidence"]},
    "Lean Proof Engineer": {"output": "core.lean.input.v1", "obligations": ["preserve full source", "separate semantic alignment"]},
    "Synthesizer": {"output": "pico.synthesis.v1", "obligations": ["cite support and contradiction nodes", "report unresolved uncertainty"]},
    "Opportunity Detector": {"output": "pico.opportunities.v1", "obligations": ["scope novelty claims", "cite source nodes"]},
}


class ResearchStrategyPlanner:
    def plan(self, question: str, assurance: dict, available_plugins: list[str], configured_providers: list[str], budget_micros: int = 0) -> StrategyPlan:
        lowered = question.lower()
        domain = "mathematics" if any(token in lowered for token in ("prove", "formula", "sum", "theorem", "integer", "geometry")) else "science"
        nodes = [
            {"id": "formalize", "type": "formalization", "role": "Formalizer", "config": {"provider": configured_providers[0] if configured_providers else "openai", "model": "gpt-5.6" if not configured_providers or configured_providers[0] == "openai" else "configured-model", "label": "Formalize question"}},
            {"id": "explore", "type": "hypothesis_generation", "role": "Explorer", "config": {"provider": configured_providers[0] if configured_providers else "openai", "model": "gpt-5.6" if not configured_providers or configured_providers[0] == "openai" else "configured-model", "label": "Generate competing hypotheses"}},
        ]
        edges: list[dict[str, Any]] = [{"source": "formalize", "target": "explore", "relation": "produces"}]
        previous = "explore"
        if "core.sympy" in available_plugins and domain == "mathematics":
            nodes.append({"id": "symbolic", "type": "plugin", "role": "Symbolic Analyst", "config": {"plugin": "core.sympy", "label": "Independent symbolic test", "input": {"operation": "simplify", "expression": "1", "variables": []}}})
            edges.append({"source": previous, "target": "symbolic", "relation": "tests", "mapping": {"operation": "$.operation", "expression": "$.expression", "variables": "$.variables"}})
            previous = "symbolic"
        nodes.extend([
            {"id": "skeptic", "type": "counterexample_search", "role": "Skeptic", "config": {"provider": configured_providers[0] if configured_providers else "openai", "model": "gpt-5.6" if not configured_providers or configured_providers[0] == "openai" else "configured-model", "label": "Search for counterexamples"}},
            {"id": "synthesis", "type": "synthesis", "role": "Synthesizer", "config": {"provider": configured_providers[0] if configured_providers else "openai", "model": "gpt-5.6" if not configured_providers or configured_providers[0] == "openai" else "configured-model", "label": "Assurance-aware synthesis"}},
            {"id": "human", "type": "human_review", "role": "Methodological Reviewer", "config": {"human_input": True, "label": "Final researcher approval"}},
        ])
        edges.extend([{"source": previous, "target": "skeptic", "relation": "challenges"}, {"source": "skeptic", "target": "synthesis", "relation": "informs"}, {"source": "synthesis", "target": "human", "relation": "requires_approval"}])
        return StrategyPlan(domain=domain, rationale=["Formalize before generating routes", "Require an adversarial stage before synthesis", "Preserve final human authority"], proposed_pipeline={"name": "Planned assurance-first investigation", "nodes": nodes, "edges": edges}, expected_evidence=["typed hypotheses", "recorded independent test", "counterexample search", "human decision"], expected_cost={"minimum_micros": 0, "expected_micros": budget_micros // 2, "maximum_micros": budget_micros}, human_checkpoints=assurance.get("human_checkpoints", ["final_conclusion"]))
