"""Permission-scoped deterministic research-memory retrieval."""

from __future__ import annotations

from orchestra.kernel.execution_envelope import ExecutionBudget, NodeExecutionEnvelope, ResearchContextSnapshot, UpstreamValue
from orchestra.pipelines.models import CompiledNode, CompiledPipeline
from orchestra.protocol.port_message import PicoPortMessage
from orchestra.repositories.repository import Repository, loads


class ContextBuilder:
    def __init__(self, repository: Repository):
        self.repo = repository

    def build(self, run: dict, plan: CompiledPipeline, node: CompiledNode, resolved_inputs: dict, upstream: list[dict], input_messages: list[PicoPortMessage] | None = None) -> NodeExecutionEnvelope:
        project = self.repo.one("SELECT * FROM projects WHERE id=?", (run["project_id"],))
        claims = self.repo.all("SELECT id,node_id,statement,assumptions,status,confidence FROM claims WHERE project_id=? ORDER BY updated_at DESC LIMIT 12", (run["project_id"],))
        evidence = self.repo.all("SELECT id,node_id,claim_id,stance,title,reliability,reproducibility FROM evidence WHERE project_id=? ORDER BY created_at DESC LIMIT 12", (run["project_id"],))
        dead_ends = self.repo.all("SELECT id,node_id,target_id,approach,assumptions,failure,lesson FROM dead_ends WHERE project_id=? ORDER BY created_at DESC LIMIT 8", (run["project_id"],))
        literature = self.repo.all("SELECT id,title,authors,doi,arxiv_id,reliability,retrieved_at FROM literature_sources WHERE project_id=? ORDER BY retrieved_at DESC LIMIT 8", (run["project_id"],))
        events = self.repo.all("SELECT event_type,payload,timestamp FROM events WHERE run_id=? ORDER BY timestamp DESC LIMIT 10", (run["id"],))
        incoming = [edge.model_dump(mode="json") for edge in plan.edges if edge.target == node.id]
        values = [UpstreamValue(**item) for item in upstream]
        return NodeExecutionEnvelope(
            project_id=run["project_id"], run_id=run["id"], branch_id=run.get("branch_id"), pipeline_id=plan.pipeline_id,
            pipeline_version=plan.pipeline_version, pipeline_node_id=node.id, research_question=project["question"],
            project_abstract=project.get("abstract", ""), project_tags=loads(project.get("tags"), []), epistemic_contract=plan.contract,
            node_assurance_requirements=node.assurance.model_dump(mode="json"), node_type=node.type, node_role=node.role,
            node_goal=node.config.get("goal") or node.config.get("label") or node.id,
            node_instructions=node.config.get("instructions") or node.config.get("prompt") or "",
            incoming_edges=incoming, upstream=values, downstream=node.downstream,
            inputs=input_messages or [],
            context=ResearchContextSnapshot(relevant_claims=claims, relevant_evidence=evidence, relevant_dead_ends=dead_ends, literature_context=literature, recent_events=[{**event, "payload": loads(event["payload"], {})} for event in events]),
            resolved_inputs=resolved_inputs, required_output_schema=node.required_output_schema, required_output_type=node.required_output_type,
            output_port_contracts={port.name: port.json_schema for port in node.interface.output_ports},
            output_port_schema_ids={port.name: port.schema_id for port in node.interface.output_ports},
            budget=ExecutionBudget(max_output_tokens=node.config.get("max_tokens", 2048), max_cost_micros=node.config.get("cost_cap_micros"), timeout_seconds=node.config.get("hard_timeout_seconds") if node.config.get("provider") == "ollama" else node.config.get("timeout_seconds", 120), max_retries=node.config.get("retry_policy", {}).get("max_attempts", 1)),
            execution_mode=run["execution_mode"], provenance_requirements={"project_id": run["project_id"], "run_id": run["id"], "pipeline_node_id": node.id, "contract_hash": plan.contract_hash, "no_secret_material": True},
        )
