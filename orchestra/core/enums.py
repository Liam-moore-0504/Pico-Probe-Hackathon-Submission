from enum import Enum


class ClaimStatus(str, Enum):
    UNVERIFIED = "unverified"
    PROPOSED = "proposed"
    UNDER_TEST = "under_test"
    TESTED = "tested"
    SUPPORTED = "supported"
    INDEPENDENTLY_CONFIRMED = "independently_confirmed"
    FORMALLY_VERIFIED = "formally_verified"
    COUNTEREXAMPLE_FOUND = "counterexample_found"
    DISPROVEN = "disproven"
    INVALIDATED = "invalidated"
    INCONCLUSIVE = "inconclusive"


class NodeKind(str, Enum):
    QUESTION = "question"
    HYPOTHESIS = "hypothesis"
    CLAIM = "claim"
    DEFINITION = "definition"
    LEMMA = "lemma"
    THEOREM = "theorem"
    PROOF_STEP = "proof_step"
    COMPUTATION = "computation"
    SIMULATION = "simulation"
    LITERATURE = "literature"
    EVIDENCE = "evidence"
    CONTRADICTION = "contradiction"
    COUNTEREXAMPLE = "counterexample"
    VERIFICATION = "formal_verification"
    HUMAN_REVIEW = "human_review"
    DEAD_END = "dead_end"
    UNEXPLORED_BRANCH = "unexplored_branch"
    CONCLUSION = "conclusion"
    NEXT_QUESTION = "next_question"
    EXPERIMENT = "experiment"


class EdgeType(str, Enum):
    SUPPORTS = "supports"
    CONTRADICTS = "contradicts"
    DEPENDS_ON = "depends_on"
    DERIVES_FROM = "derives_from"
    VERIFIES = "verifies"
    TESTS = "tests"
    DISPROVES = "disproves"
    REFINES = "refines"
    CITES = "cites"
    CRITIQUES = "critiques"
    AGREES_WITH = "agrees_with"
    DISAGREES_WITH = "disagrees_with"
    ALTERNATIVE_TO = "alternative_to"
    INVALIDATES = "invalidates"
    PRODUCES = "produces"
    ANSWERS = "answers"
    MOTIVATES = "motivates"


class ProjectRole(str, Enum):
    OWNER = "owner"
    EDITOR = "editor"
    REVIEWER = "reviewer"
    VIEWER = "viewer"


class RunStatus(str, Enum):
    DRAFT = "draft"
    QUEUED = "queued"
    RUNNING = "running"
    PAUSED = "paused"
    WAITING_FOR_USER = "waiting_for_user"
    COMPLETED = "completed"
    FAILED = "failed"
    INCONCLUSIVE = "inconclusive"
    CANCELLED = "cancelled"


class ExecutionMode(str, Enum):
    LIVE = "live"
    LOCAL = "local"
    MOCK = "mock"
    DISABLED = "disabled"
