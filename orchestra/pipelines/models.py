"""Typed visual-pipeline and assurance-aware compilation models."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

ANY_SCHEMA = {"type": "object", "additionalProperties": True}


class PortSpec(BaseModel):
    name: str
    schema_id: str = "pico.any.v1"
    json_schema: dict[str, Any] = Field(default_factory=lambda: dict(ANY_SCHEMA))
    required: bool = True
    accepts_multiple: bool = False
    description: str = ""


class NodeInterface(BaseModel):
    input_ports: list[PortSpec] = Field(default_factory=list)
    output_ports: list[PortSpec] = Field(default_factory=list)


class PipelineNode(BaseModel):
    model_config = ConfigDict(extra="allow")
    id: str
    type: str
    role: str = "Research worker"
    config: dict[str, Any] = Field(default_factory=dict)
    interface: NodeInterface = Field(default_factory=NodeInterface)


class PipelineEdge(BaseModel):
    model_config = ConfigDict(extra="allow")
    source: str
    target: str
    source_port: str = "result"
    target_port: str = "context"
    relation: str = "dependency"
    mapping: dict[str, str] = Field(default_factory=dict)


class PipelineDefinition(BaseModel):
    name: str
    nodes: list[PipelineNode] = Field(default_factory=list)
    edges: list[PipelineEdge] = Field(default_factory=list)


class NodeAssuranceRequirements(BaseModel):
    require_assumptions: bool = False
    require_falsification_conditions: bool = False
    require_seed: bool = False
    require_sources: bool = False
    require_independent_check: bool = False
    prohibit_self_certification: bool = True
    preserve_tool_output: bool = False
    rules: list[str] = Field(default_factory=list)


class DownstreamExpectation(BaseModel):
    target_pipeline_node_id: str
    target_node_type: str
    target_plugin_id: str | None = None
    source_port: str
    target_port: str
    relation: str
    required_input_schema: dict[str, Any] = Field(default_factory=dict)
    human_description: str = ""
    required_artifacts: list[str] = Field(default_factory=list)


class CompiledEdge(PipelineEdge):
    compatible: bool = True
    compatibility_reason: str = ""


class CompiledNode(PipelineNode):
    predecessor_ids: list[str] = Field(default_factory=list)
    successor_ids: list[str] = Field(default_factory=list)
    downstream: list[DownstreamExpectation] = Field(default_factory=list)
    assurance: NodeAssuranceRequirements = Field(default_factory=NodeAssuranceRequirements)
    required_output_schema: dict[str, Any] = Field(default_factory=lambda: dict(ANY_SCHEMA))
    required_output_type: str = "pico.any.v1"
    required_output_ports: dict[str, PortSpec] = Field(default_factory=dict)


class CostEstimate(BaseModel):
    minimum_micros: int = 0
    expected_micros: int = 0
    maximum_micros: int = 0


class CompiledPipeline(BaseModel):
    schema_version: Literal["1.0"] = "1.0"
    compilation_id: str
    pipeline_id: str
    pipeline_version: int
    project_id: str
    contract_id: str
    contract_version: int
    contract_hash: str
    contract: dict[str, Any]
    nodes: list[CompiledNode]
    edges: list[CompiledEdge]
    topological_order: list[str]
    warnings: list[str] = Field(default_factory=list)
    cost_estimate: CostEstimate = Field(default_factory=CostEstimate)
    compiled_at: str
