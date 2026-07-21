from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, model_validator

EVENT_TYPES = {
    "PROJECT_CREATED",
    "PROJECT_UPDATED",
    "BRANCH_CREATED",
    "PIPELINE_CREATED",
    "PIPELINE_UPDATED",
    "RUN_CREATED",
    "RUN_STARTED",
    "RUN_PAUSED",
    "RUN_RESUMED",
    "RUN_CANCELLED",
    "RUN_COMPLETED",
    "RUN_FAILED",
    "RESEARCH_NODE_CREATED",
    "RESEARCH_NODE_UPDATED",
    "RESEARCH_NODE_DELETED",
    "RESEARCH_EDGE_CREATED",
    "RESEARCH_EDGE_DELETED",
    "CLAIM_PROPOSED",
    "CLAIM_STATUS_CHANGED",
    "EVIDENCE_ATTACHED",
    "CONTRADICTION_ATTACHED",
    "COUNTEREXAMPLE_FOUND",
    "DEAD_END_RECORDED",
    "EXPERIMENT_STARTED",
    "EXPERIMENT_COMPLETED",
    "PLUGIN_STARTED",
    "PLUGIN_COMPLETED",
    "PLUGIN_FAILED",
    "PROVIDER_REQUEST_STARTED",
    "PROVIDER_REQUEST_COMPLETED",
    "PROVIDER_REQUEST_FAILED",
    "PROVIDER_STREAM_CHUNK",
    "VERIFICATION_STARTED",
    "VERIFICATION_COMPLETED",
    "DESCENDANTS_INVALIDATED",
    "PUBLIC_SNAPSHOT_CREATED",
    "CREDITS_RESERVED",
    "CREDITS_SETTLED",
    "CREDITS_RELEASED",
    "CREDENTIAL_STORED",
    "CREDENTIAL_ROTATED",
    "CREDENTIAL_DELETED",
    "MEMBER_ADDED",
    "MEMBER_REVOKED",
    "PAYMENT_CONFIRMED",
    "REVIEW_ATTACHED",
    "LITERATURE_ADDED",
    "JOB_QUEUED",
    "RUN_STEP_STARTED",
    "RUN_STEP_COMPLETED",
    "RUN_STEP_FAILED",
    "INVITATION_CREATED",
    "INVITATION_ACCEPTED",
    "MEMBER_ROLE_CHANGED",
    "MERGE_PROPOSED",
    "MERGE_COMPLETED",
    "ARTIFACT_STORED",
    "PLUGIN_INSTALLED",
    "PLUGIN_ENABLED",
    "ACCOUNT_EXPORTED",
    "ACCOUNT_DELETED",
    "HUMAN_DECISION_RECORDED",
    "ASSURANCE_CONTRACT_CREATED",
    "ASSURANCE_CONTRACT_ACTIVATED",
    "ASSURANCE_CONTRACT_BOUND_TO_RUN",
    "NODE_CONTEXT_COMPILED",
    "NODE_INPUTS_RESOLVED",
    "NODE_OUTPUT_VALIDATION_STARTED",
    "NODE_OUTPUT_REPAIR_STARTED",
    "NODE_OUTPUT_VALIDATED",
    "NODE_OUTPUT_REJECTED",
    "DOWNSTREAM_CONTRACT_SATISFIED",
    "DOWNSTREAM_CONTRACT_UNSATISFIED",
    "ASSURANCE_RULE_PASSED",
    "ASSURANCE_RULE_FAILED",
}


class ResearchEvent(BaseModel):
    id: str = Field(default_factory=lambda: "evt_" + uuid4().hex)
    project_id: UUID | None = None
    run_id: UUID | None = None
    branch_id: UUID | None = None
    actor_id: str
    actor_type: str = "user"
    event_type: str
    payload: dict = Field(default_factory=dict)
    parent_event_id: str | None = None
    correlation_id: str = Field(default_factory=lambda: "cor_" + uuid4().hex)
    idempotency_key: str | None = None
    schema_version: str = "1.0"
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    integrity_hash: str = ""

    @model_validator(mode="after")
    def calculate_hash(self) -> ResearchEvent:
        if self.event_type not in EVENT_TYPES:
            raise ValueError(f"Unknown event type: {self.event_type}")
        if not self.integrity_hash:
            material = self.model_dump(mode="json", exclude={"integrity_hash"})
            self.integrity_hash = hashlib.sha256(json.dumps(material, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        return self
