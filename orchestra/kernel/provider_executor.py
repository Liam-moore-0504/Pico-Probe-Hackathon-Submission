"""Provider execution boundary with BYOK resolution, usage billing, and provenance."""

from __future__ import annotations

import asyncio
import hashlib
import time
from urllib.parse import urlparse
from uuid import UUID, uuid4

from orchestra.core.events import ResearchEvent
from orchestra.protocol.ingest import ProtocolIngestor
from orchestra.providers import PROVIDERS, ProviderRequest, ProviderResponse
from orchestra.providers.base import OpenAICompatibleProvider
from orchestra.repositories.repository import Repository, dumps, loads, now


class ProviderExecutor:
    def __init__(self, repository: Repository, research_service, billing_policy, platform_keys: dict[str, str], generic_endpoints: dict[str, str] | None = None, bill_platform_calls: bool = True):
        self.repo = repository
        self.service = research_service
        self.billing = billing_policy
        self.platform_keys = platform_keys
        self.generic_endpoints = generic_endpoints or {}
        self.bill_platform_calls = bill_platform_calls
        self.protocol = ProtocolIngestor(repository)

    async def execute(self, actor: UUID, project_id: str, run_id: str, config: dict, execution_mode: str) -> dict:
        provider_name = config.get("provider")
        if execution_mode == "disabled" or config.get("human_input"):
            return {"status": "waiting_for_user", "execution_mode": "disabled", "message": "Human input is required"}
        if execution_mode == "mock":
            return self._mock(actor, project_id, run_id, config)
        if provider_name not in PROVIDERS and provider_name != "generic":
            raise ValueError("Pipeline provider is unsupported or missing")
        if execution_mode == "local" and provider_name != "ollama":
            raise ValueError("Local execution requires the Ollama provider")

        configured_model = config.get("model")
        if provider_name == "ollama" and configured_model in {None, "", "configured-model"}:
            setting = self.repo.one("SELECT default_model FROM ollama_settings WHERE user_id=?", (str(actor),))
            configured_model = setting.get("default_model") if setting else None
        request = ProviderRequest(
            model=configured_model or self._default_model(provider_name),
            messages=config.get("messages") or [{"role": "user", "content": config.get("prompt", "")}],
            temperature=config.get("temperature", 0.2),
            max_tokens=config.get("max_tokens", 2048),
            structured_schema=config.get("structured_schema"),
            timeout_seconds=(config.get("hard_timeout_seconds") if provider_name == "ollama" else config.get("timeout_seconds", 120)),
            idempotency_key=hashlib.sha256(f"{run_id}:{config.get('pipeline_node_id', 'provider')}".encode()).hexdigest(),
        )
        api_key, credential = self.service.resolve_secret(actor, provider_name, self.platform_keys)
        if credential["source"] == "platform" and not self.bill_platform_calls:
            credential = {**credential, "billable_by_orchestra": False}
        if credential["source"] == "unavailable":
            raise ValueError(f"{provider_name} has no BYOK or platform credential configured")
        if credential["source"] == "byok":
            self.repo.execute("UPDATE provider_credentials SET last_used_at=?,updated_at=? WHERE user_id=? AND provider=?", (now(), now(), str(actor), provider_name))
        previous = self.repo.one("SELECT * FROM provider_executions WHERE run_id=? AND idempotency_key=?", (run_id, request.idempotency_key))
        if previous and previous["status"] == "completed":
            cached_node = None
            for node in self.repo.all("SELECT id,content,provenance FROM nodes WHERE run_id=? AND kind='model_output'", (run_id,)):
                if loads(node["provenance"], {}).get("provider_execution_id") == previous["id"]:
                    cached_node = node
                    break
            if cached_node:
                return {
                    "status": "completed",
                    "execution_mode": previous["execution_mode"],
                    "provider": previous["provider"],
                    "model": previous["model"],
                    "content": loads(cached_node["content"], {}).get("content", ""),
                    "usage": {"input_tokens": previous["input_tokens"], "output_tokens": previous["output_tokens"]},
                    "node_id": cached_node["id"],
                    "typed_objects": [],
                    "execution_id": previous["id"],
                    "credential_source": previous["credential_source"],
                    "cost_micros": previous["cost_micros"],
                    "idempotent_replay": True,
                }
        reservation = None
        settled = False
        maximum_cost = 0
        if credential["billable_by_orchestra"]:
            maximum_cost = self._maximum_cost(provider_name, request)
            self.billing.enforce(str(actor), maximum_cost)
            reservation = self.service.reserve_credits(actor, run_id, maximum_cost)

        execution_id, correlation = previous["id"] if previous else str(uuid4()), "cor_" + uuid4().hex
        with self.repo.database.transaction() as connection:
            if previous:
                connection.execute("UPDATE provider_executions SET status='running',error_code=NULL,completed_at=NULL WHERE id=?", (execution_id,))
            else:
                connection.execute(
                    "INSERT INTO provider_executions(id,user_id,project_id,run_id,provider,model,execution_mode,credential_source,status,created_at,idempotency_key) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                    (execution_id, str(actor), project_id, run_id, provider_name, request.model, execution_mode, credential["source"], "running", now(), request.idempotency_key),
                )
            self.repo.append_event(connection, ResearchEvent(project_id=UUID(project_id), run_id=UUID(run_id), actor_id=str(actor), event_type="PROVIDER_REQUEST_STARTED", correlation_id=correlation, payload={"execution_id": execution_id, "provider": provider_name, "model": request.model, "credential_source": credential["source"]}))
        try:
            provider = self._provider(provider_name, config, actor)
            stream_enabled = bool(config.get("stream", provider_name == "ollama"))
            if stream_enabled:
                started = time.perf_counter()
                chunks: list[str] = []
                usage: dict[str, int] = {}
                request_id = None
                sequence = 0
                async for chunk in provider.astream(request, api_key):
                    cancellation = self.repo.one(
                        "SELECT cancellation_requested FROM jobs WHERE run_id=? ORDER BY created_at DESC LIMIT 1",
                        (run_id,),
                    )
                    if cancellation and cancellation.get("cancellation_requested"):
                        raise asyncio.CancelledError
                    request_id = chunk.request_id or request_id
                    if chunk.content:
                        chunks.append(chunk.content)
                    usage.update({key: value for key, value in chunk.usage.items() if value is not None})
                    if chunk.content or chunk.done:
                        with self.repo.database.transaction() as connection:
                            self.repo.append_event(
                                connection,
                                ResearchEvent(
                                    project_id=UUID(project_id),
                                    run_id=UUID(run_id),
                                    actor_id=str(actor),
                                    actor_type="provider",
                                    event_type="PROVIDER_STREAM_CHUNK",
                                    correlation_id=correlation,
                                    payload={"execution_id": execution_id, "sequence": sequence, "content": chunk.content, "done": chunk.done},
                                ),
                            )
                        sequence += 1
                response = ProviderResponse(provider=provider_name, model=request.model, request_id=request_id, content="".join(chunks), usage=usage, latency_ms=(time.perf_counter() - started) * 1000)
            else:
                response = await provider.aexecute(request, api_key)
            input_tokens = int(response.usage.get("input_tokens", response.usage.get("prompt_tokens", 0)))
            output_tokens = int(response.usage.get("output_tokens", response.usage.get("completion_tokens", 0)))
            actual_cost = self._actual_cost(provider_name, request.model, input_tokens, output_tokens) if reservation else 0
            if actual_cost > maximum_cost:
                actual_cost = maximum_cost
            if reservation:
                self.service.settle_credits(actor, reservation["id"], actual_cost)
                settled = True
            typed_objects = [] if config.get("_defer_protocol_ingest") else self.protocol.ingest(
                actor,
                project_id,
                run_id,
                response.content,
                {"provider": provider_name, "model": request.model, "request_id": response.request_id, "execution_mode": execution_mode},
                bool(config.get("require_typed_output")),
            )
            node_id = str(uuid4())
            with self.repo.database.transaction() as connection:
                connection.execute(
                    "UPDATE provider_executions SET request_id=?,input_tokens=?,output_tokens=?,cost_micros=?,status='completed',latency_ms=?,completed_at=? WHERE id=?",
                    (response.request_id, input_tokens, output_tokens, actual_cost, response.latency_ms, now(), execution_id),
                )
                connection.execute(
                    "INSERT INTO nodes VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (node_id, project_id, None, run_id, "model_output", f"{provider_name} model output", dumps({"content": response.content}), "completed", dumps({"x": 0, "y": 0}), dumps({"provider_execution_id": execution_id, "provider": provider_name, "model": request.model, "execution_mode": execution_mode}), 1, now(), now()),
                )
                self.repo.append_event(connection, ResearchEvent(project_id=UUID(project_id), run_id=UUID(run_id), actor_id=str(actor), event_type="PROVIDER_REQUEST_COMPLETED", correlation_id=correlation, payload={"execution_id": execution_id, "node_id": node_id, "request_id": response.request_id, "usage": response.usage, "cost_micros": actual_cost}))
            return {**response.model_dump(), "status": "completed", "node_id": node_id, "typed_objects": typed_objects, "execution_id": execution_id, "credential_source": credential["source"], "cost_micros": actual_cost, "correlation_id": correlation}
        except BaseException as exc:
            error_code = "cancelled" if exc.__class__.__name__ == "CancelledError" else "provider_error"
            if reservation and not settled:
                if error_code == "cancelled":
                    self.repo.execute("UPDATE credit_reservations SET status='reconciliation_required',updated_at=? WHERE id=?", (now(), reservation["id"]))
                else:
                    self.service.settle_credits(actor, reservation["id"], 0)
            self.repo.execute("UPDATE provider_executions SET status='failed',error_code=?,completed_at=? WHERE id=?", (error_code, now(), execution_id))
            with self.repo.database.transaction() as connection:
                self.repo.append_event(connection, ResearchEvent(project_id=UUID(project_id), run_id=UUID(run_id), actor_id=str(actor), event_type="PROVIDER_REQUEST_FAILED", correlation_id=correlation, payload={"execution_id": execution_id, "error_code": error_code}))
            raise

    def _maximum_cost(self, provider: str, request: ProviderRequest) -> int:
        estimated_input = max(1, sum(len(item["content"]) for item in request.messages) // 3)
        return self._actual_cost(provider, request.model, estimated_input, request.max_tokens)

    def _actual_cost(self, provider: str, model: str, input_tokens: int, output_tokens: int) -> int:
        rule = self.repo.one(
            "SELECT * FROM pricing_rules WHERE provider=? AND active=1 AND effective_at<=? AND (model_pattern=? OR model_pattern='*') ORDER BY CASE WHEN model_pattern=? THEN 0 ELSE 1 END,effective_at DESC LIMIT 1",
            (provider, now(), model, model),
        )
        if not rule:
            raise ValueError(f"No active reviewed pricing rule exists for {provider}/{model}")
        base = (input_tokens * rule["input_micros_per_million"] + output_tokens * rule["output_micros_per_million"]) / 1_000_000
        return max(1, int(round(base * (1 + float(rule["markup"])))))

    @staticmethod
    def _default_model(provider: str) -> str:
        raise ValueError(f"Provider {provider} requires an explicit configured model")

    def _provider(self, provider_name: str, config: dict, actor: UUID | None = None):
        if provider_name == "ollama":
            setting = self.repo.one("SELECT base_url FROM ollama_settings WHERE user_id=?", (str(actor),)) if actor else None
            if setting:
                from orchestra.providers.ollama_manager import validate_ollama_url

                base = validate_ollama_url(setting["base_url"]) + "/v1"
                return OpenAICompatibleProvider("ollama", base, {urlparse(base).hostname}, cloud=False)
            return PROVIDERS[provider_name]()
        if provider_name != "generic":
            return PROVIDERS[provider_name]()
        endpoint_id = config.get("endpoint_id")
        base_url = self.generic_endpoints.get(endpoint_id)
        if not endpoint_id or not base_url:
            raise ValueError("Generic provider endpoint is not configured or allowlisted")
        host = urlparse(base_url).hostname
        return OpenAICompatibleProvider("generic", base_url, {host} if host else set())

    def _mock(self, actor: UUID, project_id: str, run_id: str, config: dict) -> dict:
        prompt = config.get("prompt") or dumps(config.get("messages", []))
        digest = hashlib.sha256(prompt.encode()).hexdigest()[:16]
        content = f"[MOCK:{digest}] This is simulated output and was not produced by a live model."
        node_id, timestamp = str(uuid4()), now()
        with self.repo.database.transaction() as connection:
            connection.execute(
                "INSERT INTO nodes VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (node_id, project_id, None, run_id, "model_output", f"Rehearsal: {config.get('label') or config.get('pipeline_node_id', 'model step')}", dumps({"content": content, "prompt": prompt}), "completed", dumps({"x": 0, "y": 0}), dumps({"provider": "mock", "model": "deterministic-fixture", "execution_mode": "mock", "pipeline_node_id": config.get("pipeline_node_id")}), 1, timestamp, timestamp),
            )
            self.repo.append_event(connection, ResearchEvent(project_id=UUID(project_id), run_id=UUID(run_id), actor_id=str(actor), event_type="PROVIDER_REQUEST_COMPLETED", payload={"node_id": node_id, "provider": "mock", "rehearsal": True}))
        return {"status": "completed", "execution_mode": "mock", "provider": "mock", "model": "deterministic-fixture", "content": content, "usage": {"input_tokens": 0, "output_tokens": 0}, "cost_micros": 0, "node_id": node_id}
