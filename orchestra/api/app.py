"""FastAPI application factory. Routes delegate all mutations to services."""

from __future__ import annotations

import asyncio
import csv
import io
import json
import logging
import os
import shutil
import subprocess
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal
from uuid import UUID, uuid4

from fastapi import Depends, FastAPI, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, EmailStr, Field
from starlette.middleware.trustedhost import TrustedHostMiddleware

from orchestra.auth.accounts import AccountService
from orchestra.auth.security import decode_token
from orchestra.benchmarks import BenchmarkService
from orchestra.billing import BillingPolicyService, PaymentService
from orchestra.config import Settings
from orchestra.config import settings as default_settings
from orchestra.core.enums import ClaimStatus, EdgeType, ExecutionMode, NodeKind
from orchestra.core.events import ResearchEvent
from orchestra.discovery import DiscoveryEngine
from orchestra.kernel import PluginExecutor, ProviderExecutor, RunScheduler
from orchestra.pipelines import templates
from orchestra.pipelines.compiler import PipelineCompilationError, PipelineCompiler
from orchestra.planning.strategy import ROLE_TEMPLATES, ResearchStrategyPlanner
from orchestra.plugins.lean import LeanPlugin
from orchestra.plugins.marketplace import PluginMarketplace
from orchestra.plugins.mock_llm import MockLLMPlugin
from orchestra.plugins.python_experiment import PythonExperimentPlugin
from orchestra.plugins.registry import PluginRegistry
from orchestra.plugins.sandbox import configured_sandbox
from orchestra.plugins.simulation import SimulationPlugin
from orchestra.plugins.sympy import SymPyPlugin
from orchestra.protocol.contracts import AssuranceContract
from orchestra.providers import PROVIDER_METADATA, PROVIDERS
from orchestra.providers.ollama_manager import APPROVED_MODELS, OllamaManager, validate_ollama_url
from orchestra.repositories import Repository
from orchestra.research.literature import LiteratureClient
from orchestra.research.search import SemanticSearch
from orchestra.security import RateLimiter
from orchestra.services import CollaborationService
from orchestra.services.research import AuthorizationError, ConflictError, InsufficientCreditsError, NotFoundError, ResearchService, ValidationError
from orchestra.storage.artifacts import ArtifactStore
from orchestra.storage.db import ALEMBIC_SCHEMA_HEAD, Database, sqlite_schema_head
from orchestra.storage.vault import create_secret_backend

logger = logging.getLogger("orchestra")
bearer = HTTPBearer(auto_error=False)


class RegisterRequest(BaseModel):
    username: str = Field(min_length=3, max_length=64, pattern=r"^[A-Za-z0-9_.-]+$")
    email: EmailStr
    password: str = Field(min_length=10, max_length=256)


class LoginRequest(BaseModel):
    username: str
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class EmailRequest(BaseModel):
    email: EmailStr


class ChallengeTokenRequest(BaseModel):
    token: str = Field(min_length=20, max_length=200)


class PasswordResetRequest(ChallengeTokenRequest):
    password: str = Field(min_length=10, max_length=256)


class AccountDeleteRequest(BaseModel):
    password: str


class ProjectRequest(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    question: str = Field(min_length=1, max_length=20_000)
    abstract: str = Field(default="", max_length=50_000)
    tags: list[str] = Field(default_factory=list, max_length=100)


class EpistemicContractRequest(BaseModel):
    evidence_standard: str = Field(min_length=3, max_length=5_000)
    falsification_criteria: str = Field(min_length=3, max_length=5_000)
    source_requirements: str = Field(min_length=3, max_length=5_000)
    verification_requirements: str = Field(min_length=3, max_length=5_000)
    human_checkpoints: str = Field(min_length=3, max_length=5_000)


class MemberRequest(BaseModel):
    user_id: UUID
    role: Literal["editor", "reviewer", "viewer"]


class BranchRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    parent_id: UUID | None = None


class NodeRequest(BaseModel):
    kind: NodeKind
    title: str = Field(min_length=1, max_length=1000)
    content: dict[str, Any] = Field(default_factory=dict)
    status: str = "pending"
    position: dict[str, float] = Field(default_factory=lambda: {"x": 0, "y": 0})
    branch_id: UUID | None = None
    run_id: UUID | None = None
    provenance: dict = Field(default_factory=dict)


class NodePatch(BaseModel):
    title: str | None = None
    content: dict | None = None
    status: str | None = None
    position: dict[str, float] | None = None


class EdgeRequest(BaseModel):
    source_id: UUID
    target_id: UUID
    edge_type: EdgeType
    branch_id: UUID | None = None
    metadata: dict = Field(default_factory=dict)


class ClaimRequest(BaseModel):
    statement: str = Field(min_length=1, max_length=100_000)
    latex: str | None = Field(default=None, max_length=100_000)
    assumptions: list[str] = Field(default_factory=list)
    proposed_by: str = "user"
    required_capabilities: list[str] = Field(default_factory=list)
    branch_id: UUID | None = None
    run_id: UUID | None = None
    execution_mode: ExecutionMode = ExecutionMode.LOCAL


class TransitionRequest(BaseModel):
    target_status: ClaimStatus


class EvidenceRequest(BaseModel):
    evidence_type: str = "observation"
    title: str = Field(min_length=1, max_length=1000)
    content: dict = Field(default_factory=dict)
    source: str = "user"
    reliability: float = Field(default=0.5, ge=0, le=1)
    reproducibility: dict = Field(default_factory=dict)
    assumptions: list[str] = Field(default_factory=list)
    independence_group: str | None = None
    run_id: UUID | None = None
    execution_mode: ExecutionMode = ExecutionMode.LOCAL


class ReviewRequest(BaseModel):
    actor: str = "reviewer"
    stance: Literal["agree", "disagree", "uncertain"]
    reason: str = Field(min_length=1, max_length=20_000)
    assumptions: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.5, ge=0, le=1)
    independence_group: str = Field(min_length=1)


class DeadEndRequest(BaseModel):
    approach: str = Field(min_length=1, max_length=20_000)
    assumptions: list[str] = Field(default_factory=list)
    method: str = ""
    failure: str = Field(min_length=1, max_length=50_000)
    lesson: str = Field(min_length=1, max_length=50_000)
    applies_where: str = ""
    may_not_apply_where: str = ""
    discovered_by: str = "user"
    target_id: UUID | None = None
    branch_id: UUID | None = None
    run_id: UUID | None = None


class PipelineRequest(BaseModel):
    name: str = Field(min_length=1, max_length=300)
    nodes: list[dict] = Field(default_factory=list, max_length=1000)
    edges: list[dict] = Field(default_factory=list, max_length=5000)


class RunRequest(BaseModel):
    goal: str = Field(min_length=1, max_length=20_000)
    pipeline_id: UUID | None = None
    branch_id: UUID | None = None
    execution_mode: ExecutionMode = ExecutionMode.MOCK
    use_default_contract: bool = True


class AssuranceContractCreateRequest(BaseModel):
    evidence_standard: str = "Claims require recorded evidence beyond model agreement."
    falsification_criteria: str = "State observations that would refute material claims."
    source_requirements: str = "Use stable literature identifiers."
    verification_requirements: str = "Use independent symbolic, numerical, or formal checks."
    reproducibility_requirements: str = "Experiments require code, environment, seed, and uncertainty."
    human_checkpoints: list[str] = Field(default_factory=lambda: ["final_conclusion"])
    uncertainty_policy: str = "Report unresolved uncertainty."
    publication_requirements: str = "Publish provenance, limitations, and assurance status."
    forbidden_shortcuts: list[str] = Field(default_factory=lambda: ["model consensus as evidence"])
    model_consensus_is_evidence: bool = False
    minimum_independent_checks: int = Field(default=1, ge=0, le=20)
    require_counterexample_search: bool = True
    require_human_final_approval: bool = True
    minimum_experiment_trials: int = Field(default=1000, ge=1)
    unresolved_contradictions_block_synthesis: bool = True


class KeyRequest(BaseModel):
    provider: str
    api_key: str = Field(min_length=1, max_length=20_000)


class ToolRequest(BaseModel):
    payload: dict = Field(default_factory=dict)
    run_id: UUID | None = None


class CreditRequest(BaseModel):
    amount_micros: int = Field(gt=0, le=1_000_000_000)


class ReserveRequest(BaseModel):
    run_id: UUID
    maximum_micros: int = Field(gt=0)


class SettleRequest(BaseModel):
    actual_micros: int = Field(ge=0)


class CheckoutRequest(BaseModel):
    amount_micros: int = Field(ge=5_000_000, le=10_000_000_000)


class PricingRuleRequest(BaseModel):
    provider: str
    model_pattern: str
    input_micros_per_million: int = Field(ge=0)
    output_micros_per_million: int = Field(ge=0)
    cache_micros_per_million: int = Field(default=0, ge=0)
    currency: str = "USD"
    effective_at: datetime
    markup: float = Field(default=0, ge=0, le=10)
    source: str
    active: bool = False


class QuotaRequest(BaseModel):
    user_id: UUID | None = None
    monthly_micros: int = Field(gt=0)
    per_run_micros: int = Field(gt=0)
    max_parallel_runs: int = Field(gt=0, le=100)
    effective_at: datetime | None = None


class LiteratureRequest(BaseModel):
    source_type: Literal["arxiv", "doi", "upload"]
    title: str = Field(min_length=1)
    authors: list[str] = Field(default_factory=list)
    doi: str | None = None
    arxiv_id: str | None = None
    url: str | None = None
    metadata: dict = Field(default_factory=dict)
    reliability: float = Field(default=0.5, ge=0, le=1)


class BenchmarkRequest(BaseModel):
    task_id: str
    mode: Literal["single_model", "orchestra"]
    metrics: dict[str, float | int | bool]


class BenchmarkExecuteRequest(BaseModel):
    task_id: str
    mode: Literal["single_model", "orchestra"]
    run_id: UUID


class InvitationRequest(BaseModel):
    email: EmailStr
    role: Literal["editor", "reviewer", "viewer"]


class InvitationAcceptRequest(BaseModel):
    token: str = Field(min_length=20, max_length=200)


class MergeRequest(BaseModel):
    source_branch_id: UUID
    target_branch_id: UUID


class MergeResolutionRequest(BaseModel):
    resolutions: dict[str, Literal["source", "target"]] = Field(default_factory=dict)


class PluginStateRequest(BaseModel):
    enabled: bool


class HumanInputRequest(BaseModel):
    pipeline_node_id: str = Field(min_length=1, max_length=200)
    payload: dict = Field(default_factory=dict)


class OllamaConfigureRequest(BaseModel):
    base_url: str = "http://127.0.0.1:11434"
    default_model: str | None = None


class OllamaModelRequest(BaseModel):
    model: str
    confirmed: bool = False


def create_app(config: Settings | None = None) -> FastAPI:
    config = config or default_settings
    database = Database(config.database_url or config.database_path)
    if config.auto_migrate:
        database.migrate()
    repository = Repository(database)
    vault = create_secret_backend(config)
    service = ResearchService(repository, vault, config.jwt_secret)
    collaboration = CollaborationService(repository)
    registry = PluginRegistry()
    for plugin in (SymPyPlugin(), LeanPlugin(), PythonExperimentPlugin(), SimulationPlugin(), MockLLMPlugin()):
        registry.register(plugin)
    service.configure_execution(registry, PROVIDER_METADATA, config.platform_keys)
    executor = PluginExecutor(repository, registry)
    compiler = PipelineCompiler(repository, registry)
    strategy_planner = ResearchStrategyPlanner()
    discovery = DiscoveryEngine(repository)
    artifacts = ArtifactStore(repository)
    marketplace = PluginMarketplace(repository, registry, configured_sandbox(config), config.plugin_package_path)
    payments = PaymentService(repository, config.stripe_secret_key, config.stripe_webhook_secret, config.stripe_success_url, config.stripe_cancel_url)
    billing_policy = BillingPolicyService(repository)
    provider_executor = ProviderExecutor(
        repository,
        service,
        billing_policy,
        config.platform_keys,
        config.generic_provider_endpoints,
        bill_platform_calls=config.environment == "production",
    )
    scheduler = RunScheduler(repository, executor, provider_executor, config.redis_url)
    accounts = AccountService(repository, vault, config)
    semantic = SemanticSearch(repository)
    literature_client = LiteratureClient()
    benchmarks = BenchmarkService(repository, service)
    rate_limiter = RateLimiter(config.redis_url)
    app = FastAPI(title="Pico Probe Research Assurance API", version="3.0.0-rc1", description="Assurance-first, typed, auditable research execution")
    app.state.database, app.state.repository, app.state.service, app.state.registry, app.state.executor, app.state.scheduler, app.state.settings = (
        database,
        repository,
        service,
        registry,
        executor,
        scheduler,
        config,
    )
    app.state.compiler = compiler
    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
    )
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=config.allowed_hosts)
    frontend_dist = Path(__file__).resolve().parents[2] / "frontend" / "dist"
    if (frontend_dist / "assets").is_dir():
        app.mount("/assets", StaticFiles(directory=frontend_dist / "assets"), name="frontend-assets")

    @app.middleware("http")
    async def safeguards(request: Request, call_next):
        request_id = request.headers.get("X-Request-ID", "req_" + uuid4().hex)
        identity = request.client.host if request.client else "unknown"
        auth_bucket = request.url.path.startswith("/auth/")
        allowed, retry_after = await rate_limiter.check(
            identity,
            "auth" if auth_bucket else "api",
            config.auth_rate_limit_per_minute if auth_bucket else config.rate_limit_per_minute,
        )
        if not allowed:
            return JSONResponse({"detail": "Request rate limit exceeded", "request_id": request_id}, 429, headers={"Retry-After": str(retry_after)})
        length = int(request.headers.get("content-length", "0") or 0)
        if length > config.max_request_bytes:
            return JSONResponse({"detail": "Request body is too large", "request_id": request_id}, 413)
        started = time.perf_counter()
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Content-Security-Policy"] = "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; script-src 'self'; connect-src 'self'; frame-ancestors 'none'"
        logger.info(
            json.dumps(
                {
                    "request_id": request_id,
                    "method": request.method,
                    "path": request.url.path,
                    "status": response.status_code,
                    "duration_ms": round((time.perf_counter() - started) * 1000, 3),
                }
            )
        )
        return response

    @app.exception_handler(NotFoundError)
    async def not_found(_request, exc):
        return JSONResponse({"detail": str(exc)}, 404)

    @app.exception_handler(AuthorizationError)
    async def forbidden(_request, exc):
        return JSONResponse({"detail": str(exc)}, 403)

    @app.exception_handler(ConflictError)
    async def conflict(_request, exc):
        return JSONResponse({"detail": str(exc)}, 409)

    @app.exception_handler(InsufficientCreditsError)
    async def insufficient(_request, exc):
        return JSONResponse({"detail": str(exc)}, 402)

    async def invalid(_request, exc):
        return JSONResponse({"detail": str(exc)}, 422)

    app.add_exception_handler(ValidationError, invalid)
    app.add_exception_handler(ValueError, invalid)

    def current_user(credentials: HTTPAuthorizationCredentials | None = Depends(bearer)) -> UUID:
        if not credentials:
            raise HTTPException(401, "Authentication required")
        payload = decode_token(credentials.credentials, secret=config.jwt_secret)
        if not payload or repository.one("SELECT 1 FROM revoked_tokens WHERE jti=?", (payload.get("jti"),)):
            raise HTTPException(401, "Invalid or expired token")
        user_version = repository.one("SELECT token_version FROM users WHERE id=?", (payload["sub"],))
        if not user_version or user_version["token_version"] != payload.get("ver", 0):
            raise HTTPException(401, "Token has been revoked")
        return UUID(payload["sub"])

    def current_admin(actor: UUID = Depends(current_user)) -> UUID:
        row = repository.one("SELECT is_admin FROM users WHERE id=?", (str(actor),))
        if not row or not row["is_admin"]:
            raise HTTPException(403, "Administrator access required")
        return actor

    @app.get("/")
    def root():
        if (frontend_dist / "index.html").is_file():
            return FileResponse(frontend_dist / "index.html")
        return {"name": "Pico Probe", "version": app.version, "status": "online", "docs": "/docs"}

    @app.get("/api-info")
    def api_info():
        return {"name": "Pico Probe", "version": app.version, "status": "online", "docs": "/docs"}

    @app.get("/health/live")
    def live():
        return {"status": "live"}

    @app.get("/health/ready")
    async def ready():
        repository.one("SELECT 1 ok")
        if config.auto_migrate:
            revision = repository.one("SELECT MAX(version) revision FROM schema_migrations")["revision"]
            migrations_ready = revision == sqlite_schema_head()
        else:
            revision_row = repository.one("SELECT version_num revision FROM alembic_version")
            revision = revision_row["revision"] if revision_row else None
            migrations_ready = revision == ALEMBIC_SCHEMA_HEAD
        if not migrations_ready:
            raise HTTPException(503, "Database migrations are not current")
        if scheduler.redis:
            redis_ready = await asyncio.to_thread(scheduler.redis.ping)
            if not redis_ready:
                raise HTTPException(503, "Redis is unavailable")
        if config.environment == "production":
            if not shutil.which("docker"):
                raise HTTPException(503, "Docker sandbox client is unavailable")
            check = await asyncio.to_thread(
                subprocess.run,
                ["docker", "version", "--format", "{{.Server.Version}}"],
                capture_output=True,
                timeout=3,
            )
            if check.returncode != 0:
                raise HTTPException(503, "Docker sandbox service is unavailable")
        return {"status": "ready", "schema_revision": revision, "database": "postgresql" if database.is_postgres else "sqlite", "redis": bool(scheduler.redis)}

    @app.get("/health")
    def health():
        return {"status": "ok", "plugins": registry.list(), "vault_configured": vault.enabled}

    @app.post("/auth/register")
    def register(data: RegisterRequest):
        registered = service.register(data.username, str(data.email), data.password, str(data.email).lower() in config.admin_emails)
        return {**registered, "verification": accounts.request_verification(registered["user_id"])}

    @app.post("/auth/login")
    def login(data: LoginRequest, request: Request):
        return service.login(data.username, data.password, request.client.host if request.client else "unknown")

    @app.post("/auth/refresh")
    def refresh(data: RefreshRequest):
        return service.refresh(data.refresh_token)

    @app.post("/auth/logout")
    def logout(credentials: HTTPAuthorizationCredentials | None = Depends(bearer)):
        payload = decode_token(credentials.credentials, secret=config.jwt_secret) if credentials else None
        if not payload:
            raise HTTPException(401, "Invalid token")
        repository.execute("INSERT INTO revoked_tokens VALUES(?,?) ON CONFLICT(jti) DO NOTHING", (payload["jti"], datetime.fromtimestamp(payload["exp"], UTC).isoformat()))
        return {"status": "logged_out"}

    @app.post("/auth/email/verify")
    def verify_email(data: ChallengeTokenRequest):
        return accounts.verify_email(data.token)

    @app.post("/auth/password/forgot", status_code=202)
    def forgot_password(data: EmailRequest):
        return accounts.request_reset(str(data.email))

    @app.post("/auth/password/reset")
    def reset_password(data: PasswordResetRequest):
        return accounts.reset_password(data.token, data.password)

    @app.get("/auth/oauth/{provider}/start")
    def oauth_start(provider: str):
        return accounts.oauth_start(provider)

    @app.get("/auth/oauth/{provider}/callback")
    def oauth_callback(provider: str, code: str, state: str):
        return accounts.oauth_callback(provider, code, state)

    @app.get("/account/export")
    def account_export(actor=Depends(current_user)):
        return accounts.export(actor)

    @app.delete("/account", status_code=204)
    def delete_account(data: AccountDeleteRequest, actor=Depends(current_user)):
        accounts.delete(actor, data.password)

    @app.post("/projects")
    def create_project(data: ProjectRequest, actor=Depends(current_user)):
        return service.create_project(actor, data.model_dump(mode="json"))

    @app.get("/projects")
    def projects(actor=Depends(current_user)):
        return service.list_projects(actor)

    @app.get("/projects/{project_id}")
    def project(project_id: UUID, actor=Depends(current_user)):
        return service.get_project(actor, str(project_id))

    @app.get("/projects/{project_id}/epistemic-contract")
    def epistemic_contract(project_id: UUID, actor=Depends(current_user)):
        graph_data = service.graph(actor, str(project_id))
        node = next((item for item in graph_data["nodes"] if item["kind"] == "human_review" and item["title"] == "Epistemic Contract"), None)
        return node or {"project_id": str(project_id), "content": None, "status": "not_defined"}

    @app.put("/projects/{project_id}/epistemic-contract")
    def save_epistemic_contract(project_id: UUID, data: EpistemicContractRequest, actor=Depends(current_user)):
        project_id_string = str(project_id)
        graph_data = service.graph(actor, project_id_string)
        existing = next((item for item in graph_data["nodes"] if item["kind"] == "human_review" and item["title"] == "Epistemic Contract"), None)
        content = data.model_dump()
        if existing:
            return service.patch_node(actor, project_id_string, existing["id"], {"content": content, "status": "accepted"})
        return service.create_node(
            actor,
            project_id_string,
            {
                "kind": "human_review",
                "title": "Epistemic Contract",
                "content": content,
                "status": "accepted",
                "position": {"x": 40, "y": 40},
                "provenance": {"actor": str(actor), "authority": "researcher", "immutable_intent": True},
            },
        )

    @app.post("/projects/{project_id}/assurance-contracts", status_code=201)
    def create_assurance_contract(project_id: UUID, data: AssuranceContractCreateRequest, actor=Depends(current_user)):
        service.get_project(actor, str(project_id))
        version_row = repository.one("SELECT COALESCE(MAX(version),0)+1 version FROM assurance_contracts WHERE project_id=?", (str(project_id),))
        contract_id = str(uuid4())
        content = data.model_dump(mode="json")
        encoded = json.dumps(content, sort_keys=True, separators=(",", ":"))
        import hashlib
        digest = hashlib.sha256(encoded.encode()).hexdigest()
        with repository.database.transaction() as connection:
            connection.execute("UPDATE assurance_contracts SET active=0 WHERE project_id=?", (str(project_id),))
            connection.execute("INSERT INTO assurance_contracts VALUES(?,?,?,?,?,?,?,?)", (contract_id, str(project_id), version_row["version"], encoded, digest, 1, str(actor), datetime.now(UTC).isoformat()))
            repository.append_event(connection, ResearchEvent(project_id=project_id, actor_id=str(actor), event_type="ASSURANCE_CONTRACT_CREATED", payload={"contract_id": contract_id, "version": version_row["version"], "content_hash": digest}))
        return {"id": contract_id, "project_id": str(project_id), "version": version_row["version"], "active": True, "content_hash": digest, "content": content}

    @app.get("/projects/{project_id}/assurance-contracts")
    def assurance_contracts(project_id: UUID, actor=Depends(current_user)):
        service.get_project(actor, str(project_id))
        rows = repository.all("SELECT * FROM assurance_contracts WHERE project_id=? ORDER BY version DESC", (str(project_id),))
        return [{**row, "content": json.loads(row["content"]), "active": bool(row["active"])} for row in rows]

    @app.post("/projects/{project_id}/assurance-contracts/{contract_id}/activate")
    def activate_assurance_contract(project_id: UUID, contract_id: UUID, actor=Depends(current_user)):
        service.get_project(actor, str(project_id))
        with repository.database.transaction() as connection:
            target = connection.execute("SELECT id FROM assurance_contracts WHERE id=? AND project_id=?", (str(contract_id), str(project_id))).fetchone()
            if not target:
                raise HTTPException(404, "Assurance Contract not found")
            connection.execute("UPDATE assurance_contracts SET active=0 WHERE project_id=?", (str(project_id),))
            connection.execute("UPDATE assurance_contracts SET active=1 WHERE id=?", (str(contract_id),))
            repository.append_event(connection, ResearchEvent(project_id=project_id, actor_id=str(actor), event_type="ASSURANCE_CONTRACT_ACTIVATED", payload={"contract_id": str(contract_id)}))
        return {"id": str(contract_id), "active": True}

    @app.get("/projects/{project_id}/claim-passport")
    def claim_passport(project_id: UUID, actor=Depends(current_user)):
        project_data = service.get_project(actor, str(project_id))
        graph_data = service.graph(actor, str(project_id))
        nodes, edges = graph_data["nodes"], graph_data["edges"]
        contract = next((item for item in nodes if item["kind"] == "human_review" and item["title"] == "Epistemic Contract"), None)
        claims = [item for item in nodes if item["kind"] in {"claim", "hypothesis", "theorem", "conclusion"}]
        source_kinds = {"literature", "evidence"}
        challenge_kinds = {"contradiction", "counterexample", "dead_end"}
        verification_kinds = {"formal_verification", "computation", "simulation"}

        def related(claim, kinds):
            neighbor_ids = {
                edge["source_id"] if edge["target_id"] == claim["id"] else edge["target_id"]
                for edge in edges
                if edge["source_id"] == claim["id"] or edge["target_id"] == claim["id"]
            }
            return [item for item in nodes if item["id"] in neighbor_ids and item["kind"] in kinds]

        passports = []
        for claim in claims:
            supporting, challenges, checks = related(claim, source_kinds), related(claim, challenge_kinds), related(claim, verification_kinds)
            passports.append(
                {
                    "id": claim["id"],
                    "statement": claim.get("content", {}).get("statement") or claim["title"],
                    "status": claim["status"],
                    "assumptions": claim.get("content", {}).get("assumptions", []),
                    "provenance": claim.get("provenance", {}),
                    "supporting_evidence": len(supporting),
                    "challenges": len(challenges),
                    "independent_checks": len(checks),
                    "known_limitations": [item["title"] for item in challenges],
                }
            )
        return {
            "project": {"id": project_data["id"], "title": project_data["title"], "question": project_data["question"]},
            "contract": contract["content"] if contract else None,
            "claims": passports,
            "assurance": {
                "total_claims": len(claims),
                "sources": sum(item["kind"] in source_kinds for item in nodes),
                "challenges": sum(item["kind"] in challenge_kinds for item in nodes),
                "independent_checks": sum(item["kind"] in verification_kinds for item in nodes),
                "human_decisions": sum(item["kind"] == "human_review" for item in nodes),
            },
            "disclaimer": "A Claim Passport records what was checked. It does not convert model output into truth.",
        }

    @app.post("/projects/{project_id}/members")
    def add_member(project_id: UUID, data: MemberRequest, actor=Depends(current_user)):
        return service.add_member(actor, str(project_id), str(data.user_id), data.role)

    @app.post("/projects/{project_id}/branches")
    def branch(project_id: UUID, data: BranchRequest, actor=Depends(current_user)):
        return service.create_branch(actor, str(project_id), data.name, str(data.parent_id) if data.parent_id else None)

    @app.post("/projects/{project_id}/invitations", status_code=201)
    def invite_member(project_id: UUID, data: InvitationRequest, actor=Depends(current_user)):
        return collaboration.invite(actor, str(project_id), str(data.email), data.role)

    @app.post("/invitations/accept")
    def accept_invitation(data: InvitationAcceptRequest, actor=Depends(current_user)):
        return collaboration.accept(actor, data.token)

    @app.delete("/projects/{project_id}/members/{user_id}", status_code=204)
    def revoke_member(project_id: UUID, user_id: UUID, actor=Depends(current_user)):
        collaboration.revoke(actor, str(project_id), str(user_id))

    @app.get("/projects/{project_id}/branches/compare")
    def compare_branches(project_id: UUID, source_branch_id: UUID, target_branch_id: UUID, actor=Depends(current_user)):
        return collaboration.compare(actor, str(project_id), str(source_branch_id), str(target_branch_id))

    @app.post("/projects/{project_id}/merges", status_code=201)
    def propose_merge(project_id: UUID, data: MergeRequest, actor=Depends(current_user)):
        return collaboration.propose_merge(actor, str(project_id), str(data.source_branch_id), str(data.target_branch_id))

    @app.post("/merges/{proposal_id}/resolve")
    def resolve_merge(proposal_id: UUID, data: MergeResolutionRequest, actor=Depends(current_user)):
        return collaboration.resolve_merge(actor, str(proposal_id), data.resolutions)

    @app.get("/projects/{project_id}/graph")
    def graph(project_id: UUID, branch_id: UUID | None = None, actor=Depends(current_user)):
        return service.graph(actor, str(project_id), str(branch_id) if branch_id else None)

    @app.post("/projects/{project_id}/graph/nodes")
    def node(project_id: UUID, data: NodeRequest, actor=Depends(current_user)):
        return service.create_node(actor, str(project_id), data.model_dump(mode="json", exclude_none=True))

    @app.patch("/projects/{project_id}/graph/nodes/{node_id}")
    def patch_node(project_id: UUID, node_id: UUID, data: NodePatch, actor=Depends(current_user)):
        return service.patch_node(actor, str(project_id), str(node_id), data.model_dump(exclude_none=True))

    @app.delete("/projects/{project_id}/graph/nodes/{node_id}", status_code=204)
    def delete_node(project_id: UUID, node_id: UUID, actor=Depends(current_user)):
        service.delete_graph_object(actor, str(project_id), str(node_id), "node")

    @app.post("/projects/{project_id}/graph/edges")
    def edge(project_id: UUID, data: EdgeRequest, actor=Depends(current_user)):
        return service.create_edge(actor, str(project_id), data.model_dump(mode="json", exclude_none=True))

    @app.delete("/projects/{project_id}/graph/edges/{edge_id}", status_code=204)
    def delete_edge(project_id: UUID, edge_id: UUID, actor=Depends(current_user)):
        service.delete_graph_object(actor, str(project_id), str(edge_id), "edge")

    @app.post("/projects/{project_id}/claims")
    def claim(project_id: UUID, data: ClaimRequest, actor=Depends(current_user)):
        return service.create_claim(actor, str(project_id), data.model_dump(mode="json", exclude_none=True))

    @app.post("/projects/{project_id}/claims/{claim_id}/transition")
    def transition(project_id: UUID, claim_id: UUID, data: TransitionRequest, actor=Depends(current_user)):
        return service.transition_claim(actor, str(project_id), str(claim_id), data.target_status)

    @app.get("/projects/{project_id}/claims/{claim_id}/explanation")
    def explanation(project_id: UUID, claim_id: UUID, actor=Depends(current_user)):
        return service.explanation(actor, str(project_id), str(claim_id))

    @app.post("/projects/{project_id}/claims/{claim_id}/evidence")
    def evidence(project_id: UUID, claim_id: UUID, data: EvidenceRequest, actor=Depends(current_user)):
        return service.attach_evidence(actor, str(project_id), str(claim_id), data.model_dump(mode="json", exclude_none=True), "supports")

    @app.post("/projects/{project_id}/claims/{claim_id}/contradictions")
    def contradiction(project_id: UUID, claim_id: UUID, data: EvidenceRequest, actor=Depends(current_user)):
        return service.attach_evidence(actor, str(project_id), str(claim_id), data.model_dump(mode="json", exclude_none=True), "contradicts")

    @app.post("/projects/{project_id}/claims/{claim_id}/counterexamples")
    def counterexample(project_id: UUID, claim_id: UUID, data: EvidenceRequest, actor=Depends(current_user)):
        return service.attach_evidence(actor, str(project_id), str(claim_id), data.model_dump(mode="json", exclude_none=True), "counterexample")

    @app.post("/projects/{project_id}/claims/{claim_id}/reviews")
    def review(project_id: UUID, claim_id: UUID, data: ReviewRequest, actor=Depends(current_user)):
        return service.add_review(actor, str(project_id), str(claim_id), data.model_dump())

    @app.get("/projects/{project_id}/claims/controversial")
    def controversial(project_id: UUID, actor=Depends(current_user)):
        return service.controversial_claims(actor, str(project_id))

    @app.post("/projects/{project_id}/research-plan")
    async def create_research_plan(project_id: UUID, budget_micros: int = 0, actor=Depends(current_user)):
        project_data = service.get_project(actor, str(project_id))
        contracts = repository.all("SELECT content FROM assurance_contracts WHERE project_id=? AND active=1", (str(project_id),))
        assurance = json.loads(contracts[0]["content"]) if contracts else AssuranceContract(id="default-safe-v1").model_dump(mode="json")
        readiness = []
        for provider_name in PROVIDER_METADATA:
            _, credential = service.resolve_secret(actor, provider_name, config.platform_keys)
            if credential["source"] != "unavailable":
                readiness.append(provider_name)
        return strategy_planner.plan(project_data["question"], assurance, registry.list(), readiness, budget_micros).model_dump(mode="json")

    @app.get("/agent-roles")
    def agent_roles(actor=Depends(current_user)):
        return ROLE_TEMPLATES

    @app.get("/projects/{project_id}/opportunities")
    def project_opportunities(project_id: UUID, actor=Depends(current_user)):
        service.get_project(actor, str(project_id))
        return discovery.scan(str(project_id))

    @app.post("/discovery/scan")
    def discovery_scan(project_id: UUID, actor=Depends(current_user)):
        service.get_project(actor, str(project_id))
        return discovery.scan(str(project_id))

    @app.post("/opportunities/{opportunity_id}/create-project")
    def opportunity_create_project(opportunity_id: str, actor=Depends(current_user)):
        opportunity = repository.one("SELECT * FROM research_opportunities WHERE id=?", (opportunity_id,))
        if not opportunity:
            raise HTTPException(404, "Opportunity not found")
        service.get_project(actor, opportunity["project_id"])
        return service.create_project(actor, {"title": opportunity["title"], "question": opportunity["description"], "abstract": opportunity["rationale"], "tags": ["discovery-opportunity"]})

    @app.post("/opportunities/{opportunity_id}/instantiate-pipeline")
    def opportunity_pipeline(opportunity_id: str, actor=Depends(current_user)):
        opportunity = repository.one("SELECT * FROM research_opportunities WHERE id=?", (opportunity_id,))
        if not opportunity:
            raise HTTPException(404, "Opportunity not found")
        project_data = service.get_project(actor, opportunity["project_id"])
        plan = strategy_planner.plan(project_data["question"], AssuranceContract(id="default-safe-v1").model_dump(), registry.list(), [], 0)
        return service.save_pipeline(actor, opportunity["project_id"], plan.proposed_pipeline)

    @app.post("/projects/{project_id}/dead-ends")
    def dead_end(project_id: UUID, data: DeadEndRequest, actor=Depends(current_user)):
        return service.record_dead_end(actor, str(project_id), data.model_dump(mode="json", exclude_none=True))

    @app.get("/negative-knowledge/search")
    def negative(q: str = Query(min_length=2, max_length=1000), project_id: UUID | None = None, actor=Depends(current_user)):
        return service.search_dead_ends(actor, q, str(project_id) if project_id else None)

    @app.get("/search/semantic")
    def semantic_search(q: str = Query(min_length=2, max_length=2000), project_id: UUID | None = None, limit: int = Query(20, ge=1, le=100), actor=Depends(current_user)):
        return semantic.search(actor, q, str(project_id) if project_id else None, limit)

    @app.post("/projects/{project_id}/pipelines")
    def pipeline(project_id: UUID, data: PipelineRequest, actor=Depends(current_user)):
        return service.save_pipeline(actor, str(project_id), data.model_dump())

    @app.get("/projects/{project_id}/pipelines")
    def project_pipelines(project_id: UUID, actor=Depends(current_user)):
        return service.pipelines(actor, str(project_id))

    @app.get("/pipelines/{pipeline_id}")
    def get_pipeline(pipeline_id: UUID, actor=Depends(current_user)):
        return service.get_pipeline(actor, str(pipeline_id))

    @app.put("/pipelines/{pipeline_id}")
    def update_pipeline(pipeline_id: UUID, data: PipelineRequest, actor=Depends(current_user)):
        return service.save_pipeline(actor, service.get_pipeline(actor, str(pipeline_id))["project_id"], data.model_dump(), str(pipeline_id))

    @app.post("/pipelines/{pipeline_id}/duplicate")
    def duplicate_pipeline(pipeline_id: UUID, actor=Depends(current_user)):
        return service.duplicate_pipeline(actor, str(pipeline_id))

    @app.delete("/pipelines/{pipeline_id}", status_code=204)
    def delete_pipeline(pipeline_id: UUID, actor=Depends(current_user)):
        service.delete_pipeline(actor, str(pipeline_id))

    @app.post("/pipelines/validate")
    def validate_pipeline(data: PipelineRequest, actor=Depends(current_user)):
        return service.validate_pipeline(data.model_dump(), actor)

    @app.post("/pipelines/{pipeline_id}/compile")
    def compile_pipeline(pipeline_id: UUID, allow_default_contract: bool = False, actor=Depends(current_user)):
        pipeline_data = service.get_pipeline(actor, str(pipeline_id))
        try:
            return compiler.compile(pipeline_data, allow_default_contract=allow_default_contract).model_dump(mode="json")
        except PipelineCompilationError as exc:
            raise HTTPException(422, {"message": "Pipeline compilation failed", "errors": exc.errors}) from exc

    @app.post("/pipelines/{pipeline_id}/validate")
    def validate_saved_pipeline(pipeline_id: UUID, actor=Depends(current_user)):
        pipeline_data = service.get_pipeline(actor, str(pipeline_id))
        return service.validate_pipeline(pipeline_data["definition"], actor)

    @app.get("/pipeline-templates")
    def pipeline_templates():
        return templates()

    @app.post("/pipeline-templates/{template_id}/instantiate")
    def instantiate(template_id: str, project_id: UUID, actor=Depends(current_user)):
        template = next((x for x in templates() if x["id"] == template_id), None)
        if not template:
            raise HTTPException(404, "Template not found")
        return service.save_pipeline(actor, str(project_id), {"name": template["name"], "nodes": template["nodes"], "edges": template["edges"]})

    @app.post("/projects/{project_id}/runs")
    def create_run(project_id: UUID, data: RunRequest, actor=Depends(current_user)):
        return service.create_run(actor, str(project_id), data.model_dump(mode="json", exclude_none=True))

    @app.get("/runs/{run_id}")
    def run(run_id: UUID, actor=Depends(current_user)):
        return service.run(actor, str(run_id))

    @app.get("/runs/{run_id}/steps")
    def run_steps(run_id: UUID, actor=Depends(current_user)):
        return service.run_steps(actor, str(run_id))

    @app.get("/runs/{run_id}/messages")
    def run_messages(run_id: UUID, actor=Depends(current_user)):
        service.run(actor, str(run_id))
        rows = repository.all("SELECT * FROM pipeline_messages WHERE run_id=? ORDER BY created_at,message_id", (str(run_id),))
        response = []
        for row in rows:
            response.append({key: value for key, value in row.items() if key not in {"data_json", "artifact_ids_json", "provenance_json"}} | {"data": json.loads(row["data_json"]), "artifacts": json.loads(row["artifact_ids_json"]), "provenance": json.loads(row["provenance_json"])})
        return response

    @app.post("/runs/{run_id}/execute", status_code=202)
    async def execute_run(run_id: UUID, actor=Depends(current_user)):
        run_data = service.run(actor, str(run_id))
        if not run_data.get("pipeline_id"):
            raise HTTPException(422, "Run requires a persisted pipeline before execution")
        pipeline = service.get_pipeline(actor, run_data["pipeline_id"])
        try:
            plan = compiler.compile(pipeline, allow_default_contract=bool(run_data["checkpoint"].get("use_default_contract")))
        except PipelineCompilationError as exc:
            raise HTTPException(422, {"message": "Run cannot start until pipeline compilation succeeds", "errors": exc.errors}) from exc
        with repository.database.transaction() as connection:
            connection.execute("INSERT INTO run_assurance_bindings VALUES(?,?,?,?,?,?,?) ON CONFLICT(run_id) DO UPDATE SET compilation_id=excluded.compilation_id,contract_id=excluded.contract_id,contract_version=excluded.contract_version,contract_hash=excluded.contract_hash,contract_snapshot=excluded.contract_snapshot,bound_at=excluded.bound_at", (run_data["id"], plan.compilation_id, plan.contract_id, plan.contract_version, plan.contract_hash, json.dumps(plan.contract), datetime.now(UTC).isoformat()))
            repository.append_event(connection, ResearchEvent(project_id=UUID(run_data["project_id"]), run_id=run_id, actor_id=str(actor), event_type="ASSURANCE_CONTRACT_BOUND_TO_RUN", payload={"contract_id": plan.contract_id, "contract_version": plan.contract_version, "contract_hash": plan.contract_hash, "compilation_id": plan.compilation_id}))
        return scheduler.enqueue(actor, run_data, plan.model_dump(mode="json"))

    @app.get("/runs/{run_id}/assurance-status")
    def run_assurance_status(run_id: UUID, actor=Depends(current_user)):
        service.run(actor, str(run_id))
        binding = repository.one("SELECT * FROM run_assurance_bindings WHERE run_id=?", (str(run_id),))
        events = repository.events(run_id=run_id)
        rules = [event for event in events if event["event_type"] in {"ASSURANCE_RULE_PASSED", "ASSURANCE_RULE_FAILED"}]
        return {"bound": bool(binding), "binding": {**binding, "contract_snapshot": json.loads(binding["contract_snapshot"])} if binding else None, "rules": rules}

    @app.get("/jobs/{job_id}")
    def job(job_id: UUID, actor=Depends(current_user)):
        row = repository.one(
            "SELECT j.* FROM jobs j JOIN projects p ON p.id=j.project_id LEFT JOIN project_members pm ON pm.project_id=p.id AND pm.user_id=? WHERE j.id=? AND (p.owner_id=? OR pm.user_id=?)",
            (str(actor), str(job_id), str(actor), str(actor)),
        )
        if not row:
            raise HTTPException(404, "Job not found")
        row["checkpoint"] = json.loads(row["checkpoint"])
        return row

    @app.delete("/jobs/{job_id}", status_code=202)
    def cancel_job(job_id: UUID, actor=Depends(current_user)):
        row = repository.one("SELECT run_id FROM jobs WHERE id=?", (str(job_id),))
        if not row:
            raise HTTPException(404, "Job not found")
        service.run(actor, row["run_id"])
        if not scheduler.cancel(str(job_id)):
            raise HTTPException(409, "Job is not cancellable")
        return {"job_id": str(job_id), "cancellation_requested": True}

    @app.post("/jobs/{job_id}/retry", status_code=202)
    async def retry_job(job_id: UUID, actor=Depends(current_user)):
        row = repository.one("SELECT run_id FROM jobs WHERE id=?", (str(job_id),))
        if not row:
            raise HTTPException(404, "Job not found")
        service.run(actor, row["run_id"])
        return scheduler.retry(str(job_id))

    @app.post("/runs/{run_id}/human-input", status_code=202)
    async def submit_human_input(run_id: UUID, data: HumanInputRequest, actor=Depends(current_user)):
        run_data = service.run(actor, str(run_id))
        return scheduler.submit_human_input(actor, run_data, data.pipeline_node_id, data.payload)

    @app.get("/runs/{run_id}/stream")
    async def stream_run(run_id: UUID, actor=Depends(current_user)):
        service.run(actor, str(run_id))

        async def event_stream():
            last_id = None
            while True:
                rows = repository.events(run_id=run_id)
                fresh = rows if last_id is None else rows[next((i + 1 for i, row in enumerate(rows) if row["id"] == last_id), len(rows)) :]
                for row in fresh:
                    last_id = row["id"]
                    yield f"id: {row['id']}\nevent: {row['event_type']}\ndata: {json.dumps(row, default=str)}\n\n"
                status = repository.one("SELECT status FROM runs WHERE id=?", (str(run_id),))
                if status and status["status"] in {"completed", "failed", "cancelled"}:
                    yield f"event: end\ndata: {json.dumps(status)}\n\n"
                    break
                yield ": keepalive\n\n"
                await asyncio.sleep(1)

        return StreamingResponse(event_stream(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

    for action in ("start", "pause", "resume", "cancel"):
        app.add_api_route(
            f"/runs/{{run_id}}/{action}",
            lambda run_id, actor=Depends(current_user), action=action: service.set_run_status(actor, str(run_id), action),
            methods=["POST"],
            name=action + "_run",
        )

    @app.get("/runs/{run_id}/events")
    def run_events(run_id: UUID, actor=Depends(current_user)):
        service.run(actor, str(run_id))
        return repository.events(run_id=run_id)

    @app.get("/runs/{run_id}/graph")
    def run_graph(run_id: UUID, actor=Depends(current_user)):
        r = service.run(actor, str(run_id))
        g = service.graph(actor, r["project_id"])
        return {"nodes": [x for x in g["nodes"] if x["run_id"] == str(run_id)], "edges": g["edges"]}

    @app.get("/projects/{project_id}/replay")
    def replay(project_id: UUID, actor=Depends(current_user)):
        return service.replay(actor, str(project_id))

    @app.get("/runs/{run_id}/replay")
    def run_replay(run_id: UUID, actor=Depends(current_user)):
        return service.replay(actor, run_id=str(run_id))

    @app.get("/plugins")
    def plugins():
        return [{**registry.get(x).manifest.model_dump(), "enabled": True} for x in registry.list()]

    @app.post("/plugin-packages", status_code=201)
    async def install_plugin_package(manifest: str = Form(...), package: UploadFile = File(...), source: str = Form("local-upload"), actor=Depends(current_user)):
        try:
            manifest_data = json.loads(manifest)
        except json.JSONDecodeError as exc:
            raise HTTPException(422, "Plugin manifest is not valid JSON") from exc
        content = await package.read(20 * 1024 * 1024 + 1)
        if len(content) > 20 * 1024 * 1024:
            raise HTTPException(413, "Plugin package is too large")
        return marketplace.install(actor, manifest_data, content, source)

    @app.get("/plugin-packages")
    def plugin_packages(_actor=Depends(current_user)):
        return marketplace.list()

    @app.post("/admin/plugin-packages/{package_id}/approve")
    def approve_plugin_package(package_id: UUID, actor=Depends(current_admin)):
        return marketplace.approve(actor, str(package_id))

    @app.put("/admin/plugin-packages/{package_id}/state")
    def plugin_package_state(package_id: UUID, data: PluginStateRequest, actor=Depends(current_admin)):
        return marketplace.set_enabled(actor, str(package_id), data.enabled)

    @app.post("/projects/{project_id}/tools/{plugin_id}")
    def tool(project_id: UUID, plugin_id: str, data: ToolRequest, actor=Depends(current_user)):
        service.get_project(actor, str(project_id))
        return executor.execute(actor, str(project_id), plugin_id, data.payload, str(data.run_id) if data.run_id else None)

    @app.post("/user/api-key")
    def save_key(data: KeyRequest, actor=Depends(current_user)):
        return service.save_credential(actor, data.provider, data.api_key)

    @app.put("/user/api-key/{provider}/rotate")
    def rotate_key(provider: str, data: KeyRequest, actor=Depends(current_user)):
        return service.save_credential(actor, provider, data.api_key, True)

    @app.get("/user/api-keys")
    def keys(actor=Depends(current_user)):
        return {"credentials": service.list_credentials(actor)}

    @app.delete("/user/api-key/{provider}", status_code=204)
    def delete_key(provider: str, actor=Depends(current_user)):
        service.delete_credential(actor, provider)

    @app.get("/providers/status")
    async def provider_status(live: bool = False, actor=Depends(current_user)):
        result = []
        for name, metadata in PROVIDER_METADATA.items():
            _, secret = service.resolve_secret(actor, name, config.platform_keys)
            health = {"health": "available" if secret["source"] != "unavailable" else "unconfigured", "models": []}
            if live and name in PROVIDERS:
                api_key, _ = service.resolve_secret(actor, name, config.platform_keys)
                health = await asyncio.to_thread(PROVIDERS[name]().health, api_key)
            result.append(
                {
                    "provider": name,
                    "configured": secret["source"] != "unavailable",
                    "source": secret["source"],
                    **health,
                    **metadata,
                }
            )
        return result

    def ollama_configuration(actor_id: UUID) -> tuple[OllamaManager, dict]:
        saved = repository.one("SELECT * FROM ollama_settings WHERE user_id=?", (str(actor_id),))
        base = saved["base_url"] if saved else os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
        manager = OllamaManager(base)
        return manager, saved or {"base_url": manager.base_url, "default_model": None, "companion_url": None}

    @app.get("/providers/ollama/status")
    async def ollama_status(actor=Depends(current_user)):
        manager, saved = ollama_configuration(actor)
        status = await asyncio.to_thread(manager.status, saved.get("default_model"))
        binary = await asyncio.to_thread(manager.local_binary_status)
        return {**status, **binary, "default_model": saved.get("default_model"), "companion_connected": False, "approved_model_presets": sorted(APPROVED_MODELS)}

    @app.post("/providers/ollama/start")
    async def start_ollama(actor=Depends(current_user)):
        manager, saved = ollama_configuration(actor)
        try:
            result = await asyncio.to_thread(manager.start_local)
            return {**result, "default_model": saved.get("default_model")}
        except Exception as exc:
            raise HTTPException(503, str(exc)) from exc

    @app.post("/providers/ollama/configure")
    def configure_ollama(data: OllamaConfigureRequest, actor=Depends(current_user)):
        base_url = validate_ollama_url(data.base_url)
        repository.execute(
            "INSERT INTO ollama_settings VALUES(?,?,?,?,?) ON CONFLICT(user_id) DO UPDATE SET base_url=excluded.base_url,default_model=excluded.default_model,updated_at=excluded.updated_at",
            (str(actor), base_url, data.default_model, None, datetime.now(UTC).isoformat()),
        )
        return {"configured": True, "base_url": base_url, "openai_compatible_url": base_url + "/v1", "default_model": data.default_model}

    @app.get("/providers/ollama/models")
    async def ollama_models(actor=Depends(current_user)):
        manager, saved = ollama_configuration(actor)
        status = await asyncio.to_thread(manager.status, saved.get("default_model"))
        if not status["reachable"]:
            raise HTTPException(503, "Ollama is unavailable; start Ollama and test again")
        return {"models": status["models"], "default_model": saved.get("default_model")}

    @app.post("/providers/ollama/test")
    async def test_ollama(data: OllamaModelRequest, actor=Depends(current_user)):
        manager, saved = ollama_configuration(actor)
        model = data.model or saved.get("default_model")
        try:
            return await asyncio.to_thread(manager.structured_test, model)
        except Exception as exc:
            raise HTTPException(503, "Ollama structured-output test failed; verify that the service and selected model are available") from exc

    @app.post("/providers/ollama/pull-model")
    async def pull_ollama_model(data: OllamaModelRequest, actor=Depends(current_user)):
        if not data.confirmed:
            raise HTTPException(409, "Explicit confirmation is required before downloading a local model")
        manager, _saved = ollama_configuration(actor)
        try:
            return await asyncio.to_thread(manager.pull, data.model)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        except Exception as exc:
            raise HTTPException(503, "Ollama model pull failed") from exc

    @app.get("/billing/balance")
    def balance(actor=Depends(current_user)):
        return service.balance(actor)

    @app.post("/billing/test-credits")
    def test_credits(data: CreditRequest, actor=Depends(current_user)):
        if config.environment != "test":
            raise HTTPException(404, "Not found")
        return service.add_credits(actor, data.amount_micros)

    @app.post("/billing/reservations")
    def reserve(data: ReserveRequest, actor=Depends(current_user)):
        billing_policy.enforce(str(actor), data.maximum_micros)
        return service.reserve_credits(actor, str(data.run_id), data.maximum_micros)

    @app.post("/billing/reservations/{reservation_id}/settle")
    def settle(reservation_id: UUID, data: SettleRequest, actor=Depends(current_user)):
        return service.settle_credits(actor, str(reservation_id), data.actual_micros)

    @app.post("/billing/checkout-sessions", status_code=201)
    def checkout_session(data: CheckoutRequest, actor=Depends(current_user)):
        return payments.create_checkout(actor, data.amount_micros)

    @app.post("/billing/stripe/webhook")
    async def stripe_webhook(request: Request):
        signature = request.headers.get("stripe-signature", "")
        try:
            return payments.webhook(await request.body(), signature)
        except Exception as exc:
            logger.warning("stripe_webhook_rejected type=%s", type(exc).__name__)
            raise HTTPException(400, "Invalid Stripe webhook") from exc

    @app.post("/admin/pricing-rules", status_code=201)
    def add_pricing_rule(data: PricingRuleRequest, actor=Depends(current_admin)):
        return billing_policy.add_pricing(actor, data.model_dump(mode="json", exclude_none=True))

    @app.get("/admin/pricing-rules")
    def pricing_rules(_actor=Depends(current_admin)):
        return repository.all("SELECT * FROM pricing_rules ORDER BY effective_at DESC")

    @app.post("/admin/quotas", status_code=201)
    def set_quota(data: QuotaRequest, _actor=Depends(current_admin)):
        payload = data.model_dump(mode="json", exclude_none=True)
        return billing_policy.set_quota(str(data.user_id) if data.user_id else None, payload)

    @app.post("/admin/billing/reservations/{reservation_id}/reconcile")
    def reconcile_reservation(reservation_id: UUID, data: SettleRequest, _actor=Depends(current_admin)):
        reservation = repository.one("SELECT user_id FROM credit_reservations WHERE id=?", (str(reservation_id),))
        if not reservation:
            raise HTTPException(404, "Reservation not found")
        return service.settle_credits(UUID(reservation["user_id"]), str(reservation_id), data.actual_micros)

    @app.post("/projects/{project_id}/publish")
    def publish(project_id: UUID, actor=Depends(current_user)):
        return service.publish(actor, str(project_id))

    @app.post("/projects/{project_id}/unpublish")
    def unpublish(project_id: UUID, actor=Depends(current_user)):
        return service.unpublish(actor, str(project_id))

    @app.get("/public/projects")
    def public_projects():
        return service.public_projects()

    @app.get("/public/snapshots/{snapshot_id}")
    def snapshot(snapshot_id: str):
        return service.public_snapshot(snapshot_id)

    @app.post("/projects/{project_id}/literature")
    def literature(project_id: UUID, data: LiteratureRequest, actor=Depends(current_user)):
        return service.add_literature(actor, str(project_id), data.model_dump(mode="json", exclude_none=True))

    @app.post("/projects/{project_id}/literature/resolve", status_code=201)
    def resolve_literature(project_id: UUID, doi: str | None = None, arxiv_id: str | None = None, actor=Depends(current_user)):
        if bool(doi) == bool(arxiv_id):
            raise HTTPException(422, "Provide exactly one DOI or arXiv identifier")
        metadata = literature_client.resolve_doi(doi) if doi else literature_client.resolve_arxiv(arxiv_id)
        return service.add_literature(actor, str(project_id), metadata)

    @app.post("/projects/{project_id}/artifacts", status_code=201)
    async def upload_artifact(project_id: UUID, file: UploadFile = File(...), run_id: UUID | None = Form(None), actor=Depends(current_user)):
        service.get_project(actor, str(project_id))
        content = await file.read(artifacts.maximum_bytes + 1)
        return artifacts.store(actor, str(project_id), file.filename or "artifact", file.content_type or "application/octet-stream", content, str(run_id) if run_id else None)

    @app.get("/projects/{project_id}/artifacts")
    def list_artifacts(project_id: UUID, actor=Depends(current_user)):
        service.get_project(actor, str(project_id))
        return repository.all(
            "SELECT id,run_id,filename,media_type,size_bytes,sha256,metadata,created_at FROM artifacts WHERE project_id=? ORDER BY created_at DESC", (str(project_id),)
        )

    @app.get("/projects/{project_id}/artifacts/{artifact_id}")
    def download_artifact(project_id: UUID, artifact_id: UUID, actor=Depends(current_user)):
        service.get_project(actor, str(project_id))
        row = repository.one("SELECT * FROM artifacts WHERE id=? AND project_id=?", (str(artifact_id), str(project_id)))
        if not row:
            raise HTTPException(404, "Artifact not found")
        return FileResponse(artifacts.path(row["storage_key"]), filename=row["filename"], media_type=row["media_type"])

    @app.post("/benchmarks/runs")
    def benchmark(data: BenchmarkRequest, actor=Depends(current_user)):
        return service.record_benchmark(actor, data.task_id, data.mode, data.metrics)

    @app.get("/benchmarks/tasks")
    def benchmark_tasks(_actor=Depends(current_user)):
        return benchmarks.tasks()

    @app.post("/benchmarks/execute", status_code=201)
    def execute_benchmark(data: BenchmarkExecuteRequest, actor=Depends(current_user)):
        return benchmarks.execute(actor, data.task_id, data.mode, str(data.run_id))

    @app.get("/benchmarks/runs")
    def benchmark_runs(actor=Depends(current_user)):
        rows = repository.all("SELECT * FROM benchmark_runs WHERE user_id=? ORDER BY created_at DESC", (str(actor),))
        for row in rows:
            row["metrics"] = json.loads(row["metrics"])
        return rows

    @app.get("/benchmarks/export.csv")
    def benchmark_csv(actor=Depends(current_user)):
        rows = repository.all("SELECT id,task_id,mode,metrics,created_at FROM benchmark_runs WHERE user_id=? ORDER BY created_at", (str(actor),))
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=["id", "task_id", "mode", "metrics", "created_at"])
        writer.writeheader()
        writer.writerows(rows)
        return StreamingResponse(iter([output.getvalue()]), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=orchestra-benchmarks.csv"})

    return app


app = create_app()
