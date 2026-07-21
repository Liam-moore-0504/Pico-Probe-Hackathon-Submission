"""Canonical transport for every value crossing a pipeline edge."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field


def new_message_id() -> str:
    return "msg_" + uuid4().hex


class ArtifactReference(BaseModel):
    artifact_id: str
    media_type: str
    sha256: str
    filename: str | None = None
    size_bytes: int | None = None
    description: str = ""


class ProvenanceRecord(BaseModel):
    producer_type: Literal["provider", "plugin", "human", "kernel", "import"]
    producer_id: str
    producer_version: str | None = None
    provider_execution_id: str | None = None
    source_message_ids: list[str] = Field(default_factory=list)
    source_object_ids: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    repaired: bool = False
    repair_count: int = 0
    assurance_contract_id: str | None = None
    assurance_contract_version: int | None = None


class PicoPortMessage(BaseModel):
    message_id: str = Field(default_factory=new_message_id)
    schema_version: Literal["1.0"] = "1.0"
    project_id: str
    run_id: str
    branch_id: str | None = None
    pipeline_id: str
    pipeline_version: int
    pipeline_node_id: str
    direction: Literal["input", "output"]
    port: str
    schema_id: str
    object_ids: list[str] = Field(default_factory=list)
    data: dict[str, Any] = Field(default_factory=dict)
    artifacts: list[ArtifactReference] = Field(default_factory=list)
    provenance: ProvenanceRecord
    status: Literal["pending", "completed", "failed", "rejected", "waiting_for_user", "invalidated"] = "completed"
