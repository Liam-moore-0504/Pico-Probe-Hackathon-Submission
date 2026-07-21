"""Canonical, secret-free input supplied to every executable node."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from orchestra.pipelines.models import DownstreamExpectation
from orchestra.protocol.port_message import PicoPortMessage


class ArtifactReference(BaseModel):
    artifact_id: str
    media_type: str
    filename: str | None = None
    sha256: str
    description: str = ""


class UpstreamValue(BaseModel):
    source_pipeline_node_id: str
    source_research_node_id: str | None = None
    source_port: str
    target_port: str
    relation: str
    schema_id: str | None = None
    typed_objects: list[dict[str, Any]] = Field(default_factory=list)
    output: dict[str, Any] = Field(default_factory=dict)
    artifacts: list[ArtifactReference] = Field(default_factory=list)
    provenance: dict[str, Any] = Field(default_factory=dict)


class ExecutionBudget(BaseModel):
    max_input_tokens: int | None = None
    max_output_tokens: int | None = None
    max_cost_micros: int | None = None
    timeout_seconds: int | None = None
    max_retries: int = 1


class ResearchContextSnapshot(BaseModel):
    relevant_claims: list[dict[str, Any]] = Field(default_factory=list)
    relevant_evidence: list[dict[str, Any]] = Field(default_factory=list)
    relevant_dead_ends: list[dict[str, Any]] = Field(default_factory=list)
    literature_context: list[dict[str, Any]] = Field(default_factory=list)
    recent_events: list[dict[str, Any]] = Field(default_factory=list)


class NodeExecutionEnvelope(BaseModel):
    schema_version: Literal["1.0"] = "1.0"
    project_id: str
    run_id: str
    branch_id: str | None = None
    pipeline_id: str
    pipeline_version: int
    pipeline_node_id: str
    research_question: str
    project_abstract: str = ""
    project_tags: list[str] = Field(default_factory=list)
    epistemic_contract: dict[str, Any]
    node_assurance_requirements: dict[str, Any]
    node_type: str
    node_role: str
    node_goal: str
    node_instructions: str
    incoming_edges: list[dict[str, Any]] = Field(default_factory=list)
    upstream: list[UpstreamValue] = Field(default_factory=list)
    inputs: list[PicoPortMessage] = Field(default_factory=list)
    downstream: list[DownstreamExpectation] = Field(default_factory=list)
    context: ResearchContextSnapshot = Field(default_factory=ResearchContextSnapshot)
    resolved_inputs: dict[str, Any] = Field(default_factory=dict)
    required_output_schema: dict[str, Any]
    required_output_type: str
    output_port_contracts: dict[str, dict[str, Any]] = Field(default_factory=dict)
    output_port_schema_ids: dict[str, str] = Field(default_factory=dict)
    budget: ExecutionBudget
    execution_mode: Literal["live", "local", "mock", "disabled"]
    provenance_requirements: dict[str, Any]
