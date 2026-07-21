"""Assurance contract and output-contract definitions."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class AssuranceContract(BaseModel):
    id: str
    version: int = 1
    evidence_standard: str = "Claims require recorded evidence beyond model agreement."
    falsification_criteria: str = "State what observation or counterexample would refute each material claim."
    source_requirements: str = "Use stable identifiers for literature sources."
    verification_requirements: str = "Preserve independent symbolic, numerical, or formal checks."
    reproducibility_requirements: str = "Experiments require code, environment, deterministic seed, and uncertainty."
    human_checkpoints: list[str] = Field(default_factory=lambda: ["final_conclusion"])
    uncertainty_policy: str = "Report unresolved uncertainty; do not convert absence of a counterexample into proof."
    publication_requirements: str = "Publish provenance, limitations, and assurance status."
    forbidden_shortcuts: list[str] = Field(default_factory=lambda: ["model consensus as evidence", "unrecorded tool execution"])
    model_consensus_is_evidence: bool = False
    minimum_independent_checks: int = 1
    require_counterexample_search: bool = True
    require_human_final_approval: bool = True
    minimum_experiment_trials: int = 1000
    unresolved_contradictions_block_synthesis: bool = True


class OutputContract(BaseModel):
    schema_id: str
    json_schema: dict[str, Any]
    strict: bool = True
    output_ports: dict[str, dict[str, Any]] = Field(default_factory=dict)
