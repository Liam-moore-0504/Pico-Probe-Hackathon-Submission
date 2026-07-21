"""Validate provider output against the research protocol and persist typed graph objects."""

from __future__ import annotations

import json
from uuid import UUID, uuid4

from pydantic import TypeAdapter, ValidationError

from orchestra.core.events import ResearchEvent
from orchestra.protocol.models import StructuredResearchObject
from orchestra.repositories.repository import Repository, dumps, now

ADAPTER = TypeAdapter(list[StructuredResearchObject])


class ProtocolIngestor:
    def __init__(self, repository: Repository):
        self.repo = repository

    def ingest(self, actor: UUID, project_id: str, run_id: str, content: str, provenance: dict, required: bool = False) -> list[dict]:
        try:
            raw = json.loads(content)
            values = raw.get("objects") if isinstance(raw, dict) else raw
            objects = ADAPTER.validate_python(values)
        except (json.JSONDecodeError, TypeError, ValidationError) as exc:
            if required:
                raise ValueError("Provider response does not satisfy the typed research-object protocol") from exc
            return []
        rows = []
        timestamp = now()
        id_map = {item.id: str(uuid4()) for item in objects}
        for item in objects:
            for dependency in item.dependencies:
                if dependency not in id_map and self.repo.one("SELECT id FROM nodes WHERE id=? AND project_id=?", (dependency, project_id)):
                    id_map[dependency] = dependency
        with self.repo.database.transaction() as connection:
            for item in objects:
                data = item.model_dump(mode="json")
                external_id = data["id"]
                data["id"] = id_map[external_id]
                data["external_object_id"] = external_id
                unknown = [value for value in data.get("dependencies", []) if value not in id_map]
                if required and unknown:
                    raise ValueError(f"Unknown typed-object dependencies: {', '.join(unknown)}")
                data["dependencies"] = [id_map[value] for value in data.get("dependencies", []) if value in id_map]
                data["provenance"] = {**data["provenance"], **provenance, "repaired": False}
                node_id = data["id"]
                kind = self._kind(data["type"])
                status = "proposed" if data["type"] in {"claim", "hypothesis"} else "completed"
                connection.execute(
                    "INSERT INTO nodes VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (node_id, project_id, provenance.get("branch_id"), run_id, kind, data["statement"][:1000], dumps(data), status, dumps({"x": 0, "y": 0}), dumps({**data["provenance"], "pipeline_node_id": provenance.get("pipeline_node_id"), "assurance_contract_version": provenance.get("assurance_contract_version"), "artifact_ids": provenance.get("artifact_ids", [])}), 1, timestamp, timestamp),
                )
                if data["type"] == "claim":
                    claim_id = str(uuid4())
                    connection.execute(
                        "INSERT INTO claims VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                        (claim_id, project_id, node_id, data["statement"], data.get("latex"), dumps(data.get("assumptions", [])), "proposed", data.get("confidence", 0), data["provenance"].get("provider") or "provider", dumps([]), timestamp, timestamp),
                    )
                    data["claim_id"] = claim_id
                    self.repo.append_event(connection, ResearchEvent(project_id=UUID(project_id), run_id=UUID(run_id), actor_id=str(actor), actor_type="provider", event_type="CLAIM_PROPOSED", payload={"claim_id": claim_id, "node_id": node_id}))
                self.repo.append_event(connection, ResearchEvent(project_id=UUID(project_id), run_id=UUID(run_id), actor_id=str(actor), actor_type="provider", event_type="RESEARCH_NODE_CREATED", payload={"node_id": node_id, "kind": kind, "protocol_type": data["type"]}))
                rows.append(data)
            ids = {item["id"] for item in rows} | {value for key, value in id_map.items() if key not in {item.id for item in objects}}
            for item in rows:
                for dependency in item.get("dependencies", []):
                    if dependency not in ids:
                        continue
                    edge_id = str(uuid4())
                    connection.execute(
                        "INSERT INTO edges VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(project_id,source_id,target_id,edge_type) DO NOTHING",
                        (edge_id, project_id, provenance.get("branch_id"), dependency, item["id"], "depends_on", dumps({"source": "typed_provider_output", "direction": "dependency_to_dependent"}), timestamp),
                    )
                    self.repo.append_event(connection, ResearchEvent(project_id=UUID(project_id), run_id=UUID(run_id), actor_id=str(actor), actor_type="provider", event_type="RESEARCH_EDGE_CREATED", payload={"edge_id": edge_id, "source_id": dependency, "target_id": item["id"], "edge_type": "depends_on"}))
                    target_claim = connection.execute("SELECT * FROM claims WHERE node_id=?", (dependency,)).fetchone()
                    if target_claim and item["type"] == "evidence":
                        connection.execute(
                            "INSERT INTO evidence VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(node_id) DO NOTHING",
                            (str(uuid4()), project_id, item["id"], target_claim["id"], "provider_output", "supports", item["statement"][:1000], item["statement"], dumps(item["provenance"]), item.get("reliability", 0.5), dumps({}), dumps(item.get("assumptions", [])), item["provenance"].get("provider"), item["id"], timestamp),
                        )
                        connection.execute("UPDATE claims SET status='supported',confidence=?,updated_at=? WHERE id=? AND status NOT IN ('disproven','counterexample_found') AND confidence<=?", (item.get("confidence", 0.5), timestamp, target_claim["id"], item.get("confidence", 0.5)))
                        self.repo.append_event(connection, ResearchEvent(project_id=UUID(project_id), run_id=UUID(run_id), actor_id=str(actor), actor_type="provider", event_type="EVIDENCE_ATTACHED", payload={"claim_id": target_claim["id"], "node_id": item["id"]}))
                    if target_claim and item["type"] in {"counterexample", "contradiction"}:
                        new_status = "counterexample_found" if item["type"] == "counterexample" else "challenged"
                        connection.execute("UPDATE claims SET status=?,updated_at=? WHERE id=?", (new_status, timestamp, target_claim["id"]))
                        connection.execute("UPDATE nodes SET status=?,updated_at=? WHERE id=?", (new_status, timestamp, dependency))
                        event_type = "COUNTEREXAMPLE_FOUND" if item["type"] == "counterexample" else "CONTRADICTION_ATTACHED"
                        self.repo.append_event(connection, ResearchEvent(project_id=UUID(project_id), run_id=UUID(run_id), actor_id=str(actor), actor_type="provider", event_type=event_type, payload={"claim_id": target_claim["id"], "node_id": item["id"]}))
                        if item["type"] == "counterexample":
                            descendants = connection.execute(
                                "WITH RECURSIVE descendants(id) AS (SELECT target_id FROM edges WHERE project_id=? AND source_id=? UNION SELECT e.target_id FROM edges e JOIN descendants d ON e.source_id=d.id WHERE e.project_id=?) SELECT id FROM descendants",
                                (project_id, dependency, project_id),
                            ).fetchall()
                            invalidated = [row["id"] for row in descendants if row["id"] != item["id"]]
                            for descendant_id in invalidated:
                                connection.execute("UPDATE nodes SET status='invalidated',updated_at=? WHERE id=?", (timestamp, descendant_id))
                                connection.execute("UPDATE claims SET status='invalidated',updated_at=? WHERE node_id=?", (timestamp, descendant_id))
                            if invalidated:
                                self.repo.append_event(connection, ResearchEvent(project_id=UUID(project_id), run_id=UUID(run_id), actor_id=str(actor), actor_type="kernel", event_type="DESCENDANTS_INVALIDATED", payload={"counterexample_node_id": item["id"], "target_node_id": dependency, "invalidated_node_ids": invalidated, "rerun_recommended": True}))
        return rows

    @staticmethod
    def _kind(protocol_type: str) -> str:
        return {
            "research_question": "question",
            "hypothesis": "hypothesis",
            "claim": "claim",
            "evidence": "evidence",
            "contradiction": "contradiction",
            "counterexample": "counterexample",
            "experiment_design": "experiment",
            "experiment_result": "experiment",
            "verification_request": "verification",
            "verification_result": "verification",
            "dead_end": "dead_end",
        }.get(protocol_type, "note")
