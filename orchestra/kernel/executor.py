"""Kernel-owned plugin execution and immutable audit recording."""

from __future__ import annotations

import time
from uuid import UUID, uuid4

from orchestra.core.events import ResearchEvent
from orchestra.repositories.repository import Repository, dumps, now


class PluginExecutor:
    def __init__(self, repository: Repository, registry):
        self.repo, self.registry = repository, registry

    def execute(self, actor: UUID, project_id: str, plugin_id: str, payload: dict, run_id: str | None = None, execution_envelope: dict | None = None) -> dict:
        plugin = self.registry.get(plugin_id)
        correlation = "cor_" + uuid4().hex
        started = time.perf_counter()
        with self.repo.database.transaction() as connection:
            self.repo.append_event(
                connection,
                ResearchEvent(
                    project_id=UUID(project_id),
                    run_id=UUID(run_id) if run_id else None,
                    actor_id=str(actor),
                    event_type="PLUGIN_STARTED",
                    correlation_id=correlation,
                    payload={
                        "plugin_id": plugin_id,
                        "version": plugin.manifest.version,
                        "pipeline_node_id": execution_envelope.get("pipeline_node_id") if execution_envelope else None,
                        "input_message_ids": [message["message_id"] for message in execution_envelope.get("inputs", [])] if execution_envelope else [],
                        "assurance_contract_id": execution_envelope.get("epistemic_contract", {}).get("id") if execution_envelope else None,
                    },
                ),
            )
        try:
            result = plugin.execute(payload)
            if result.get("execution_mode") not in {"live", "local", "mock", "disabled"}:
                raise ValueError("Plugin omitted explicit execution_mode")
            node_id = str(uuid4())
            timestamp = now()
            with self.repo.database.transaction() as connection:
                connection.execute(
                    "INSERT INTO nodes VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (
                        node_id,
                        project_id,
                        None,
                        run_id,
                        "computation",
                        plugin_id + " execution",
                        dumps({"input": payload, "result": result}),
                        result.get("status", "completed"),
                        dumps({"x": 0, "y": 0}),
                        dumps({"plugin": plugin_id, "version": plugin.manifest.version, "execution_mode": result["execution_mode"], "pipeline_node_id": execution_envelope.get("pipeline_node_id") if execution_envelope else None}),
                        1,
                        timestamp,
                        timestamp,
                    ),
                )
                self.repo.append_event(
                    connection,
                    ResearchEvent(
                        project_id=UUID(project_id),
                        run_id=UUID(run_id) if run_id else None,
                        actor_id=str(actor),
                        event_type="PLUGIN_COMPLETED",
                        correlation_id=correlation,
                        payload={"plugin_id": plugin_id, "node_id": node_id, "result": result, "duration_ms": (time.perf_counter() - started) * 1000},
                    ),
                )
            return {**result, "plugin_id": plugin_id, "plugin_version": plugin.manifest.version, "node_id": node_id, "correlation_id": correlation}
        except Exception:
            with self.repo.database.transaction() as connection:
                self.repo.append_event(
                    connection,
                    ResearchEvent(
                        project_id=UUID(project_id),
                        run_id=UUID(run_id) if run_id else None,
                        actor_id=str(actor),
                        event_type="PLUGIN_FAILED",
                        correlation_id=correlation,
                        payload={"plugin_id": plugin_id, "error": "Plugin execution failed"},
                    ),
                )
            raise
