from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class ResearchOpportunity(BaseModel):
    id: str
    project_id: str
    opportunity_type: Literal["missing_proof", "missing_experiment", "conflicting_evidence", "unverified_generalization", "replication_need", "formalization_opportunity", "unresolved_dead_end"]
    title: str
    description: str
    source_nodes: list[str] = Field(default_factory=list)
    why_gap: str
    novelty_scope: str
    feasibility: float
    expected_impact: float
    required_capabilities: list[str]
    suggested_pipeline: dict
    uncertainty: str
    known_risks: list[str]
