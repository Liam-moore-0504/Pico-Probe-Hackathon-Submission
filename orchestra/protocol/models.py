"""Versioned structured research language."""

from __future__ import annotations

from typing import Annotated, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


class Provenance(BaseModel):
    provider: str | None = None
    model: str | None = None
    plugin: str | None = None
    request_id: str | None = None
    execution_mode: Literal["live", "local", "mock", "disabled"]
    repaired: bool = False


class ResearchObject(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: Literal["1.0"] = "1.0"
    id: str = Field(default_factory=lambda: "obj_" + uuid4().hex)
    statement: str = Field(min_length=1, max_length=100_000)
    assumptions: list[str] = Field(default_factory=list, max_length=100)
    dependencies: list[str] = Field(default_factory=list, max_length=500)
    confidence: float = Field(default=0.0, ge=0, le=1)
    provenance: Provenance


class ResearchQuestion(ResearchObject):
    type: Literal["research_question"] = "research_question"


class Hypothesis(ResearchObject):
    type: Literal["hypothesis"] = "hypothesis"
    required_capabilities: list[str] = Field(default_factory=list)


class StructuredClaim(ResearchObject):
    type: Literal["claim"] = "claim"
    latex: str | None = None


class Assumption(ResearchObject):
    type: Literal["assumption"] = "assumption"


class Definition(ResearchObject):
    type: Literal["definition"] = "definition"


class ProofStep(ResearchObject):
    type: Literal["proof_step"] = "proof_step"


class StructuredEvidence(ResearchObject):
    type: Literal["evidence"] = "evidence"
    reliability: float = Field(ge=0, le=1)


class Contradiction(ResearchObject):
    type: Literal["contradiction"] = "contradiction"


class Counterexample(ResearchObject):
    type: Literal["counterexample"] = "counterexample"


class ExperimentDesign(ResearchObject):
    type: Literal["experiment_design"] = "experiment_design"
    seed: int | None = None


class ExperimentResult(ResearchObject):
    type: Literal["experiment_result"] = "experiment_result"
    reproducibility: dict = Field(default_factory=dict)


class VerificationRequest(ResearchObject):
    type: Literal["verification_request"] = "verification_request"


class VerificationResult(ResearchObject):
    type: Literal["verification_result"] = "verification_result"
    verified: bool
    formal: bool


class StructuredDeadEnd(ResearchObject):
    type: Literal["dead_end"] = "dead_end"
    lesson: str


class Synthesis(ResearchObject):
    type: Literal["synthesis"] = "synthesis"


class Conclusion(ResearchObject):
    type: Literal["conclusion"] = "conclusion"


class NextQuestion(ResearchObject):
    type: Literal["next_question"] = "next_question"


StructuredResearchObject = Annotated[
    ResearchQuestion
    | Hypothesis
    | StructuredClaim
    | Assumption
    | Definition
    | ProofStep
    | StructuredEvidence
    | Contradiction
    | Counterexample
    | ExperimentDesign
    | ExperimentResult
    | VerificationRequest
    | VerificationResult
    | StructuredDeadEnd
    | Synthesis
    | Conclusion
    | NextQuestion,
    Field(discriminator="type"),
]
