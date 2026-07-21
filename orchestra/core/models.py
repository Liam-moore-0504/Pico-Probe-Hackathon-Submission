from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field

from .enums import ClaimStatus, EdgeType, NodeKind


class ResearchNode(BaseModel):
    model_config = ConfigDict(validate_assignment=True)
    id: UUID = Field(default_factory=uuid4)
    kind: NodeKind
    title: str
    content: dict[str, Any] = Field(default_factory=dict)
    status: str = "pending"
    provenance: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ResearchEdge(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    source_id: UUID
    target_id: UUID
    edge_type: EdgeType
    metadata: dict[str, Any] = Field(default_factory=dict)


class Claim(BaseModel):
    model_config = ConfigDict(validate_assignment=True)
    id: UUID = Field(default_factory=uuid4)
    statement: str
    latex: str | None = None
    assumptions: list[str] = Field(default_factory=list)
    status: ClaimStatus = ClaimStatus.PROPOSED
    confidence: float = 0.0
    proposed_by: str = "kernel"
    required_capabilities: list[str] = Field(default_factory=list)
    verification_history: list[dict[str, Any]] = Field(default_factory=list)


class Evidence(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    evidence_type: str
    title: str
    content: dict[str, Any] = Field(default_factory=dict)
    source: str = "kernel"
    reliability: float = 0.5


class DeadEnd(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    approach: str
    assumptions: list[str] = Field(default_factory=list)
    failure: str
    lesson: str
    discovered_by: str = "kernel"
    fingerprint: str | None = None


class ExperimentVersion(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    name: str
    version: int = 1
    seed: int | None = None
    inputs: dict[str, Any] = Field(default_factory=dict)
    environment: dict[str, Any] = Field(default_factory=dict)
    outputs: dict[str, Any] = Field(default_factory=dict)
    metrics: dict[str, float] = Field(default_factory=dict)


class ResearchProject(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    owner_id: UUID
    title: str
    question: str
    is_public: bool = False
    status: str = "draft"
    active_branch: str = "main"
