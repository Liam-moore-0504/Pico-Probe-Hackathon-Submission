"""Durable DAG scheduler with parallel levels, cancellation, and persistent checkpoints."""

from __future__ import annotations

import asyncio
from collections import defaultdict, deque
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from orchestra.core.events import ResearchEvent
from orchestra.kernel.context_builder import ContextBuilder
from orchestra.kernel.execution_envelope import NodeExecutionEnvelope
from orchestra.kernel.prompt_assembler import ResearchPromptAssembler
from orchestra.pipelines.models import CompiledNode, CompiledPipeline
from orchestra.protocol.adapters import InputResolver
from orchestra.protocol.ingest import ProtocolIngestor
from orchestra.protocol.output_validator import OutputValidationError, OutputValidator
from orchestra.protocol.port_message import ArtifactReference as MessageArtifactReference
from orchestra.protocol.port_message import PicoPortMessage, ProvenanceRecord
from orchestra.protocol.repair import repair_messages
from orchestra.repositories.messages import PipelineMessageRepository
from orchestra.repositories.repository import Repository, dumps, loads, now
from orchestra.storage.artifacts import ArtifactStore


class RunScheduler:
    def __init__(self, repository: Repository, executor, provider_executor=None, redis_url: str = ""):
        self.repo = repository
        self.executor = executor
        self.provider_executor = provider_executor
        self.tasks: dict[str, asyncio.Task] = {}
        self.redis = None
        self.context_builder = ContextBuilder(repository)
        self.input_resolver = InputResolver()
        self.prompt_assembler = ResearchPromptAssembler()
        self.output_validator = OutputValidator()
        self.artifacts = ArtifactStore(repository)
        self.messages = PipelineMessageRepository(repository)
        self.protocol = ProtocolIngestor(repository)
        if redis_url:
            import redis

            self.redis = redis.Redis.from_url(redis_url, decode_responses=True)

    def enqueue(self, actor: UUID, run: dict, definition: dict) -> dict:
        job_id = str(uuid4())
        with self.repo.database.transaction() as connection:
            connection.execute(
                "INSERT INTO jobs VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (job_id, run["id"], run["project_id"], "queued", 0, dumps(definition), dumps({}), 0, 0, None, None, None, now(), now()),
            )
            connection.execute("UPDATE runs SET status='queued',updated_at=? WHERE id=?", (now(), run["id"]))
            self.repo.append_event(
                connection, ResearchEvent(project_id=UUID(run["project_id"]), run_id=UUID(run["id"]), actor_id=str(actor), event_type="JOB_QUEUED", payload={"job_id": job_id})
            )
        if self.redis:
            self.redis.lpush("orchestra:jobs", job_id)
        else:
            task = asyncio.create_task(self._run(job_id, actor, run, definition))
            self.tasks[job_id] = task
            task.add_done_callback(lambda _task: self.tasks.pop(job_id, None))
        return {"job_id": job_id, "run_id": run["id"], "status": "queued"}

    async def execute_persisted(self, job_id: str, worker_id: str = "worker") -> None:
        stale_before = (datetime.now(UTC) - timedelta(minutes=5)).isoformat()
        with self.repo.database.transaction() as connection:
            claimed = connection.execute(
                "UPDATE jobs SET status='claimed',locked_by=?,locked_at=?,updated_at=? WHERE id=? AND (status IN ('queued','retrying') OR (status IN ('claimed','running') AND locked_at<?))",
                (worker_id, now(), now(), job_id, stale_before),
            )
        if claimed.rowcount != 1:
            return
        job = self.repo.one("SELECT * FROM jobs WHERE id=?", (job_id,))
        if not job:
            return
        run = self.repo.one("SELECT * FROM runs WHERE id=?", (job["run_id"],))
        if not run:
            return
        await self._run(job_id, UUID(run["created_by"]), run, loads(job["payload"], {}))

    def cancel(self, job_id: str) -> bool:
        with self.repo.database.transaction() as connection:
            result = connection.execute("UPDATE jobs SET cancellation_requested=1,updated_at=? WHERE id=? AND status IN ('queued','running')", (now(), job_id))
        task = self.tasks.get(job_id)
        if task:
            task.cancel()
        return bool(result.rowcount)

    def retry(self, job_id: str) -> dict:
        with self.repo.database.transaction() as connection:
            changed = connection.execute(
                "UPDATE jobs SET status='retrying',cancellation_requested=0,locked_by=NULL,locked_at=NULL,error=NULL,updated_at=? WHERE id=? AND status IN ('failed','cancelled','paused','waiting_for_user')",
                (now(), job_id),
            )
        if changed.rowcount != 1:
            raise ValueError("Job is not retryable")
        if self.redis:
            self.redis.lpush("orchestra:jobs", job_id)
        else:
            task = asyncio.create_task(self.execute_persisted(job_id, "local"))
            self.tasks[job_id] = task
            task.add_done_callback(lambda _task: self.tasks.pop(job_id, None))
        return {"job_id": job_id, "status": "retrying"}

    def submit_human_input(self, actor: UUID, run: dict, pipeline_node_id: str, payload: dict) -> dict:
        job = self.repo.one("SELECT * FROM jobs WHERE run_id=? AND status='waiting_for_user' ORDER BY created_at DESC LIMIT 1", (run["id"],))
        if not job:
            raise ValueError("Run is not waiting for human input")
        checkpoint = loads(job["checkpoint"], {})
        completed = list(dict.fromkeys([*checkpoint.get("completed_nodes", []), pipeline_node_id]))
        contribution_type = payload.get("contribution_type", "claim")
        allowed_kinds = {"claim", "evidence", "formal_verification", "computation", "human_review", "hypothesis"}
        kind = contribution_type if contribution_type in allowed_kinds else "claim"
        node_id = str(uuid4())
        timestamp = now()
        title = str(payload.get("summary") or "Researcher contribution").strip()[:240]
        content = {
            "statement": str(payload.get("content") or payload.get("summary") or "").strip(),
            "summary": str(payload.get("summary") or "").strip(),
            "confidence": payload.get("confidence"),
            "pipeline_node_id": pipeline_node_id,
        }
        definition = loads(job["payload"], {})
        incoming = [edge for edge in definition.get("edges", []) if edge.get("target") == pipeline_node_id]
        plan = CompiledPipeline.model_validate(definition) if definition.get("compilation_id") else None
        compiled_node = next((item for item in plan.nodes if item.id == pipeline_node_id), None) if plan else None
        output_ports = compiled_node.required_output_ports if compiled_node else {}
        human_messages = [
            PicoPortMessage(
                project_id=run["project_id"], run_id=run["id"], branch_id=run.get("branch_id"), pipeline_id=run["pipeline_id"],
                pipeline_version=plan.pipeline_version if plan else 1, pipeline_node_id=pipeline_node_id, direction="output", port=port_name,
                schema_id=port.schema_id, data=payload,
                provenance=ProvenanceRecord(producer_type="human", producer_id=str(actor), assurance_contract_id=plan.contract_id if plan else None, assurance_contract_version=plan.contract_version if plan else None),
            ) for port_name, port in output_ports.items()
        ]
        human_output = {"status": "completed", "execution_mode": "disabled", "human_input": payload, "ports": {message.port: message.data for message in human_messages}, "output_messages": [message.model_dump(mode="json") for message in human_messages]}
        with self.repo.database.transaction() as connection:
            updated = connection.execute(
                "UPDATE run_steps SET status='completed',output=?,completed_at=? WHERE run_id=? AND pipeline_node_id=?",
                (dumps(human_output), now(), run["id"], pipeline_node_id),
            )
            if updated.rowcount != 1:
                raise ValueError("Human-input pipeline node was not found")
            for message in human_messages:
                self.messages.persist(message, connection)
            connection.execute(
                "INSERT INTO nodes VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    node_id, run["project_id"], None, run["id"], kind, title,
                    dumps(content), "proposed" if kind in {"claim", "hypothesis"} else "completed",
                    dumps({"x": 0, "y": 0}),
                    dumps({"actor": "researcher", "actor_id": str(actor), "pipeline_node_id": pipeline_node_id, "execution_mode": "human"}),
                    1, timestamp, timestamp,
                ),
            )
            for edge in incoming:
                upstream = connection.execute(
                    "SELECT output FROM run_steps WHERE run_id=? AND pipeline_node_id=? AND status='completed'",
                    (run["id"], edge.get("source")),
                ).fetchone()
                upstream_node_id = loads(upstream["output"], {}).get("node_id") if upstream else None
                if upstream_node_id:
                    connection.execute(
                        "INSERT INTO edges VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(project_id,source_id,target_id,edge_type) DO NOTHING",
                        (str(uuid4()), run["project_id"], None, upstream_node_id, node_id, edge.get("relation", "supports"), dumps({"pipeline_edge": True}), timestamp),
                    )
            connection.execute("UPDATE jobs SET checkpoint=?,updated_at=? WHERE id=?", (dumps({"completed_nodes": completed}), now(), job["id"]))
            connection.execute("UPDATE runs SET status='running',updated_at=? WHERE id=?", (now(), run["id"]))
            self.repo.append_event(connection, ResearchEvent(project_id=UUID(run["project_id"]), run_id=UUID(run["id"]), actor_id=str(actor), event_type="HUMAN_DECISION_RECORDED", payload={"pipeline_node_id": pipeline_node_id, "node_id": node_id, "kind": kind, "input": payload}))
        return self.retry(job["id"])

    async def _run(self, job_id: str, actor: UUID, run: dict, definition: dict) -> None:
        try:
            plan = CompiledPipeline.model_validate(definition) if definition.get("compilation_id") else None
            self._status(job_id, run["id"], "running")
            levels = self._levels(definition)
            job = self.repo.one("SELECT checkpoint FROM jobs WHERE id=?", (job_id,))
            completed = list(loads(job["checkpoint"], {}).get("completed_nodes", [])) if job else []
            for level in levels:
                while True:
                    run_state = self.repo.one("SELECT status FROM runs WHERE id=?", (run["id"],))
                    if not run_state or run_state["status"] != "paused":
                        break
                    self.repo.execute("UPDATE jobs SET status='paused',updated_at=? WHERE id=?", (now(), job_id))
                    if self._cancelled(job_id):
                        raise asyncio.CancelledError
                    await asyncio.sleep(0.5)
                level = [node for node in level if node["id"] not in completed]
                if not level:
                    continue
                if self._cancelled(job_id):
                    raise asyncio.CancelledError
                prepared = [self._prepare_compiled(actor, run, plan, node) if plan else self._with_upstream_context(run["id"], definition, node) for node in level]
                results = await asyncio.gather(*(self._step_with_retry(actor, run, node) for node in prepared), return_exceptions=True)
                for result in results:
                    if isinstance(result, BaseException):
                        raise result
                waiting = []
                for node, result in zip(level, results, strict=True):
                    if result.get("status") == "waiting_for_user":
                        waiting.append(node["id"])
                    else:
                        completed.append(node["id"])
                if waiting:
                    self.repo.execute("UPDATE jobs SET status='waiting_for_user',checkpoint=?,updated_at=? WHERE id=?", (dumps({"completed_nodes": completed, "waiting_nodes": waiting}), now(), job_id))
                    self.repo.execute("UPDATE runs SET status='waiting_for_user',updated_at=? WHERE id=?", (now(), run["id"]))
                    return
                self.repo.execute("UPDATE jobs SET checkpoint=?,updated_at=? WHERE id=?", (dumps({"completed_nodes": completed}), now(), job_id))
            self._status(job_id, run["id"], "completed")
            with self.repo.database.transaction() as connection:
                self.repo.append_event(
                    connection,
                    ResearchEvent(
                        project_id=UUID(run["project_id"]),
                        run_id=UUID(run["id"]),
                        actor_id=str(actor),
                        event_type="RUN_COMPLETED",
                        payload={"job_id": job_id, "completed_nodes": completed},
                    ),
                )
        except asyncio.CancelledError:
            self._status(job_id, run["id"], "cancelled")
        except Exception as exc:
            self.repo.execute("UPDATE jobs SET status='failed',error=?,updated_at=? WHERE id=?", (str(exc)[:1000], now(), job_id))
            self.repo.execute("UPDATE runs SET status='failed',updated_at=? WHERE id=?", (now(), run["id"]))
            with self.repo.database.transaction() as connection:
                self.repo.append_event(
                    connection,
                    ResearchEvent(
                        project_id=UUID(run["project_id"]),
                        run_id=UUID(run["id"]),
                        actor_id=str(actor),
                        event_type="RUN_FAILED",
                        payload={"job_id": job_id, "error": "Execution failed"},
                    ),
                )

    async def _step(self, actor: UUID, run: dict, node: dict) -> dict:
        step_id = str(uuid4())
        config = self._resolve_research_question(run, node.get("config", {}))
        envelope_data = config.pop("_execution_envelope", None)
        plugin_id = config.get("plugin")
        messages_to_persist: list[PicoPortMessage] = []
        with self.repo.database.transaction() as connection:
            connection.execute(
                "INSERT INTO run_steps VALUES(?,?,?,?,?,?,?,?,?,?) ON CONFLICT(run_id,pipeline_node_id) DO UPDATE SET id=excluded.id,status=excluded.status,attempt=run_steps.attempt+1,input=excluded.input,output=NULL,error=NULL,started_at=excluded.started_at,completed_at=NULL",
                (step_id, run["id"], node["id"], "running", 1, dumps(config.get("input", {})), None, None, now(), None),
            )
            self.repo.append_event(
                connection,
                ResearchEvent(
                    project_id=UUID(run["project_id"]),
                    run_id=UUID(run["id"]),
                    actor_id=str(actor),
                    event_type="RUN_STEP_STARTED",
                    payload={"step_id": step_id, "pipeline_node_id": node["id"]},
                ),
            )
        try:
            if plugin_id:
                payload = config.get("_resolved_plugin_input") or self._plugin_payload(config)
                result = await asyncio.to_thread(self.executor.execute, actor, run["project_id"], plugin_id, payload, run["id"], envelope_data)
            elif self.provider_executor and (config.get("provider") or run["execution_mode"] == "mock" or config.get("human_input")):
                result = await self.provider_executor.execute(actor, run["project_id"], run["id"], {**config, "pipeline_node_id": node["id"], "node_type": node.get("type")}, run["execution_mode"])
            else:
                result = {
                    "status": "waiting_for_user",
                    "execution_mode": run["execution_mode"],
                    "node_type": node.get("type"),
                    "message": "This node requires configured provider or human input",
                }
        except BaseException as exc:
            with self.repo.database.transaction() as connection:
                connection.execute("UPDATE run_steps SET status='failed',error=?,completed_at=? WHERE run_id=? AND pipeline_node_id=?", (exc.__class__.__name__, now(), run["id"], node["id"]))
                self.repo.append_event(connection, ResearchEvent(project_id=UUID(run["project_id"]), run_id=UUID(run["id"]), actor_id=str(actor), event_type="RUN_STEP_FAILED", payload={"step_id": step_id, "pipeline_node_id": node["id"], "error_code": exc.__class__.__name__}))
            raise
        if envelope_data and result.get("status") != "waiting_for_user":
            envelope = NodeExecutionEnvelope.model_validate(envelope_data)
            self._event(actor, run, "NODE_OUTPUT_VALIDATION_STARTED", {"pipeline_node_id": node["id"]})
            try:
                validated = self.output_validator.validate_or_repair(envelope, result)
                if validated.repaired:
                    self._event(actor, run, "NODE_OUTPUT_REPAIR_STARTED", {"pipeline_node_id": node["id"], "errors": validated.errors_before_repair})
                result = validated.result
                self._event(actor, run, "NODE_OUTPUT_VALIDATED", {"pipeline_node_id": node["id"], "repaired": validated.repaired, "schema_id": envelope.required_output_type, "message_ids": [message.message_id for message in validated.messages]})
                self._event(actor, run, "DOWNSTREAM_CONTRACT_SATISFIED", {"pipeline_node_id": node["id"]})
                self._event(actor, run, "ASSURANCE_RULE_PASSED", {"pipeline_node_id": node["id"], "requirements": envelope.node_assurance_requirements})
            except OutputValidationError as exc:
                if result.get("node_id"):
                    self.repo.execute("UPDATE nodes SET status='rejected',updated_at=? WHERE id=?", (now(), result["node_id"]))
                can_repair = envelope.execution_mode in {"live", "local"} and self.provider_executor and config.get("provider")
                if can_repair:
                    original_artifact = self.artifacts.store(actor, run["project_id"], f"{node['id']}-invalid-original.json", "application/json", dumps(result).encode(), run["id"])
                    self._event(actor, run, "NODE_OUTPUT_REPAIR_STARTED", {"pipeline_node_id": node["id"], "errors": exc.errors, "original_artifact_id": original_artifact["id"]})
                    repaired_raw = await self.provider_executor.execute(actor, run["project_id"], run["id"], {**config, "messages": repair_messages(exc.errors, envelope.required_output_schema), "pipeline_node_id": node["id"] + "__repair", "node_type": node.get("type")}, run["execution_mode"])
                    try:
                        validated = self.output_validator.validate_or_repair(envelope, repaired_raw)
                    except OutputValidationError as repair_exc:
                        if repaired_raw.get("node_id"):
                            self.repo.execute("UPDATE nodes SET status='rejected',updated_at=? WHERE id=?", (now(), repaired_raw["node_id"]))
                        self._event(actor, run, "NODE_OUTPUT_REJECTED", {"pipeline_node_id": node["id"], "errors": repair_exc.errors, "repair_attempts": 1})
                        self._event(actor, run, "DOWNSTREAM_CONTRACT_UNSATISFIED", {"pipeline_node_id": node["id"]})
                        self._event(actor, run, "ASSURANCE_RULE_FAILED", {"pipeline_node_id": node["id"], "errors": repair_exc.errors})
                        raise
                    for message in validated.messages:
                        message.provenance.repaired = True
                        message.provenance.repair_count = 1
                    result = validated.result
                    result["repair"] = {"count": 1, "original_artifact_id": original_artifact["id"]}
                    self._event(actor, run, "NODE_OUTPUT_VALIDATED", {"pipeline_node_id": node["id"], "repaired": True, "schema_id": envelope.required_output_type, "message_ids": [message.message_id for message in validated.messages]})
                    self._event(actor, run, "DOWNSTREAM_CONTRACT_SATISFIED", {"pipeline_node_id": node["id"], "repaired": True})
                    self._event(actor, run, "ASSURANCE_RULE_PASSED", {"pipeline_node_id": node["id"], "requirements": envelope.node_assurance_requirements, "after_repair": True})
                else:
                    self._event(actor, run, "NODE_OUTPUT_REJECTED", {"pipeline_node_id": node["id"], "errors": exc.errors})
                    self._event(actor, run, "DOWNSTREAM_CONTRACT_UNSATISFIED", {"pipeline_node_id": node["id"]})
                    self._event(actor, run, "ASSURANCE_RULE_FAILED", {"pipeline_node_id": node["id"], "errors": exc.errors})
                    raise
        if result.get("status") != "waiting_for_user":
            if envelope_data:
                typed_objects: list[dict] = []
                for message in validated.messages:
                    if isinstance(message.data.get("objects"), list):
                        ingested = self.protocol.ingest(
                            actor, run["project_id"], run["id"], dumps(message.data),
                            {"provider": result.get("provider"), "plugin": result.get("plugin_id"), "model": result.get("model"), "execution_mode": result.get("execution_mode"), "pipeline_node_id": node["id"], "assurance_contract_version": envelope.epistemic_contract.get("version")},
                            required=True,
                        )
                        message.object_ids = [item["id"] for item in ingested]
                        typed_objects.extend(ingested)
                result["typed_objects"] = typed_objects
                result["output_messages"] = [message.model_dump(mode="json") for message in validated.messages]
            artifact = self.artifacts.store(actor, run["project_id"], f"{node['id']}-validated-output.json", "application/json", dumps(result).encode(), run["id"])
            result["artifact_references"] = [artifact]
            if envelope_data:
                artifact_reference = MessageArtifactReference(artifact_id=artifact["id"], media_type=artifact["media_type"], sha256=artifact["sha256"], filename=artifact["filename"], size_bytes=artifact["size_bytes"])
                for message in validated.messages:
                    message.artifacts.append(artifact_reference)
                messages_to_persist = validated.messages
                result["output_messages"] = [message.model_dump(mode="json") for message in validated.messages]
        if config.get("preserve_unselected") and result.get("node_id"):
            alternatives = self.repo.all(
                "SELECT id FROM nodes WHERE run_id=? AND kind='model_output' AND id<>? AND status='completed'",
                (run["id"], result["node_id"]),
            )
            with self.repo.database.transaction() as connection:
                for alternative in alternatives:
                    connection.execute("UPDATE nodes SET status='unexplored',updated_at=? WHERE id=?", (now(), alternative["id"]))
                self.repo.append_event(
                    connection,
                    ResearchEvent(
                        project_id=UUID(run["project_id"]), run_id=UUID(run["id"]), actor_id=str(actor), event_type="ROUTE_ELECTED",
                        payload={"pipeline_node_id": node["id"], "elected_output_node_id": result["node_id"], "preserved_unexplored_node_ids": [item["id"] for item in alternatives]},
                    ),
                )
        if result.get("node_id"):
            with self.repo.database.transaction() as connection:
                graph_upstream = config.get("upstream_outputs", [])
                if envelope_data:
                    graph_upstream = [{"relation": item.get("relation", "dependency"), "output": {"node_id": item.get("source_research_node_id")}} for item in envelope_data.get("upstream", [])]
                for upstream in graph_upstream:
                    source_id = upstream.get("output", {}).get("node_id")
                    if source_id:
                        connection.execute(
                            "INSERT INTO edges VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(project_id,source_id,target_id,edge_type) DO NOTHING",
                            (str(uuid4()), run["project_id"], None, source_id, result["node_id"], upstream.get("relation", "dependency"), dumps({"pipeline_edge": True}), now()),
                        )
        final_status = "waiting_for_user" if result.get("status") == "waiting_for_user" else "completed"
        with self.repo.database.transaction() as connection:
            for message in messages_to_persist:
                self.messages.persist(message, connection)
            connection.execute("UPDATE run_steps SET status=?,output=?,completed_at=? WHERE id=?", (final_status, dumps(result), None if final_status == "waiting_for_user" else now(), step_id))
            self.repo.append_event(
                connection,
                ResearchEvent(
                    project_id=UUID(run["project_id"]),
                    run_id=UUID(run["id"]),
                    actor_id=str(actor),
                    event_type="RUN_STEP_COMPLETED",
                    payload={"step_id": step_id, "pipeline_node_id": node["id"], "status": result.get("status")},
                ),
            )
        return result

    def _prepare_compiled(self, actor: UUID, run: dict, plan: CompiledPipeline, raw_node: dict) -> dict:
        node = CompiledNode.model_validate(raw_node)
        upstream_outputs: dict[str, dict] = {}
        for source_id in node.predecessor_ids:
            step = self.repo.one("SELECT output FROM run_steps WHERE run_id=? AND pipeline_node_id=? AND status='completed'", (run["id"], source_id))
            if step:
                upstream_outputs[source_id] = loads(step["output"], {})
        resolved, provenance, input_messages = self.input_resolver.resolve_with_messages(node, plan.edges, upstream_outputs, require_messages=True)
        for message in input_messages:
            self.messages.persist(message)
        envelope = self.context_builder.build(run, plan, node, resolved, provenance, input_messages)
        self._event(actor, run, "NODE_INPUTS_RESOLVED", {"pipeline_node_id": node.id, "ports": sorted(resolved), "sources": sorted(upstream_outputs), "message_ids": [message.message_id for message in input_messages]})
        self._event(actor, run, "NODE_CONTEXT_COMPILED", {"pipeline_node_id": node.id, "contract_hash": plan.contract_hash, "upstream_count": len(provenance), "downstream_count": len(node.downstream)})
        config = {**node.config, "messages": self.prompt_assembler.assemble(envelope), "structured_schema": envelope.required_output_schema, "_execution_envelope": envelope.model_dump(mode="json"), "_defer_protocol_ingest": True}
        if node.config.get("plugin") and resolved:
            values = list(resolved.values())
            config["_resolved_plugin_input"] = values[0] if len(values) == 1 and isinstance(values[0], dict) else resolved
        return {**node.model_dump(mode="json"), "config": config}

    def _event(self, actor: UUID, run: dict, event_type: str, payload: dict) -> None:
        with self.repo.database.transaction() as connection:
            self.repo.append_event(connection, ResearchEvent(project_id=UUID(run["project_id"]), run_id=UUID(run["id"]), actor_id=str(actor), event_type=event_type, payload=payload))

    def _resolve_research_question(self, run: dict, value):
        project = self.repo.one("SELECT question FROM projects WHERE id=?", (run["project_id"],))
        question = project["question"] if project else ""

        def resolve(item):
            if isinstance(item, str):
                return item.replace("\\researchquestion", question)
            if isinstance(item, list):
                return [resolve(child) for child in item]
            if isinstance(item, dict):
                return {key: resolve(child) for key, child in item.items()}
            return item

        return resolve(value)

    def _plugin_payload(self, config: dict) -> dict:
        upstream = config.get("upstream_outputs", [])
        first_output = upstream[0].get("output", {}) if upstream else {}
        replacement = first_output.get("content") or first_output.get("proof_script") or dumps(first_output)

        def resolve(item):
            if isinstance(item, str):
                return item.replace("\\upstream", str(replacement))
            if isinstance(item, list):
                return [resolve(child) for child in item]
            if isinstance(item, dict):
                return {key: resolve(child) for key, child in item.items()}
            return item

        return {**resolve(config.get("input", {})), "_upstream": upstream}

    async def _step_with_retry(self, actor: UUID, run: dict, node: dict) -> dict:
        policy = node.get("config", {}).get("retry_policy", {})
        maximum = int(policy.get("max_attempts", 1))
        delay = float(policy.get("backoff_seconds", 0.25))
        for attempt in range(1, maximum + 1):
            try:
                return await self._step(actor, run, node)
            except asyncio.CancelledError:
                raise
            except Exception:
                if attempt == maximum:
                    self.repo.execute("UPDATE run_steps SET status='failed',error=?,completed_at=? WHERE run_id=? AND pipeline_node_id=?", ("ExecutionValidationError", now(), run["id"], node["id"]))
                    raise
                await asyncio.sleep(min(30, delay * (2 ** (attempt - 1))))
        raise RuntimeError("Retry policy exhausted")

    def _with_upstream_context(self, run_id: str, definition: dict, node: dict) -> dict:
        incoming = [edge for edge in definition.get("edges", []) if edge.get("target") == node["id"] and edge.get("relation") not in {"rejected", "preserved"}]
        rows = []
        for edge in incoming:
            step = self.repo.one("SELECT output FROM run_steps WHERE run_id=? AND pipeline_node_id=? AND status='completed'", (run_id, edge["source"]))
            if step:
                rows.append({"source": edge["source"], "relation": edge.get("relation", "dependency"), "output": loads(step["output"], {})})
        behavior = node.get("config", {}).get("branch_behavior", "all")
        if behavior == "any" and rows:
            rows = rows[:1]
        if not rows:
            return node
        enriched = {**node, "config": {**node.get("config", {}), "upstream_outputs": rows}}
        prompt = enriched["config"].get("prompt") or enriched["config"].get("instructions") or "Process the upstream research outputs."
        enriched["config"]["prompt"] = prompt + "\n\nUPSTREAM RESEARCH OUTPUTS (preserve provenance):\n" + dumps(rows)
        return enriched

    def _status(self, job_id: str, run_id: str, status: str) -> None:
        with self.repo.database.transaction() as connection:
            if status == "running":
                connection.execute("UPDATE jobs SET status=?,attempts=attempts+1,updated_at=? WHERE id=?", (status, now(), job_id))
            else:
                connection.execute("UPDATE jobs SET status=?,updated_at=? WHERE id=?", (status, now(), job_id))
            connection.execute("UPDATE runs SET status=?,updated_at=? WHERE id=?", (status, now(), run_id))

    def _cancelled(self, job_id: str) -> bool:
        row = self.repo.one("SELECT cancellation_requested FROM jobs WHERE id=?", (job_id,))
        return not row or bool(row["cancellation_requested"])

    def _levels(self, definition: dict) -> list[list[dict]]:
        nodes = {node["id"]: node for node in definition.get("nodes", [])}
        outgoing: dict[str, list[str]] = defaultdict(list)
        indegree = {key: 0 for key in nodes}
        for edge in definition.get("edges", []):
            outgoing[edge["source"]].append(edge["target"])
            indegree[edge["target"]] += 1
        queue = deque([key for key, degree in indegree.items() if degree == 0])
        levels = []
        while queue:
            current = list(queue)
            queue.clear()
            levels.append([nodes[key] for key in current])
            for key in current:
                for target in outgoing[key]:
                    indegree[target] -= 1
                    if indegree[target] == 0:
                        queue.append(target)
        if sum(map(len, levels)) != len(nodes):
            raise ValueError("Pipeline contains a cycle")
        return levels
