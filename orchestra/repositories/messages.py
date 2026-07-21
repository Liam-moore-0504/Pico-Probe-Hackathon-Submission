"""Persistence boundary for canonical pipeline messages."""

from __future__ import annotations

from orchestra.protocol.port_message import PicoPortMessage
from orchestra.repositories.repository import Repository, dumps, loads


class PipelineMessageRepository:
    def __init__(self, repository: Repository):
        self.repo = repository

    def persist(self, message: PicoPortMessage, connection=None) -> None:
        values = (
            message.message_id, message.project_id, message.run_id, message.branch_id, message.pipeline_id,
            message.pipeline_version, message.pipeline_node_id, message.direction, message.port, message.schema_id,
            dumps(message.data), dumps([item.model_dump(mode="json") for item in message.artifacts]),
            dumps(message.provenance.model_dump(mode="json")), message.status, message.provenance.created_at.isoformat(),
        )
        query = "INSERT INTO pipeline_messages VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(message_id) DO NOTHING"
        if connection is not None:
            connection.execute(query, values)
        else:
            self.repo.execute(query, values)

    def for_node(self, run_id: str, node_id: str, direction: str | None = None) -> list[PicoPortMessage]:
        query = "SELECT * FROM pipeline_messages WHERE run_id=? AND pipeline_node_id=?"
        args: tuple = (run_id, node_id)
        if direction:
            query += " AND direction=?"
            args += (direction,)
        query += " ORDER BY created_at,message_id"
        return [self._model(row) for row in self.repo.all(query, args)]

    @staticmethod
    def _model(row: dict) -> PicoPortMessage:
        return PicoPortMessage.model_validate({
            "message_id": row["message_id"], "project_id": row["project_id"], "run_id": row["run_id"],
            "branch_id": row["branch_id"], "pipeline_id": row["pipeline_id"], "pipeline_version": row["pipeline_version"],
            "pipeline_node_id": row["pipeline_node_id"], "direction": row["direction"], "port": row["port"],
            "schema_id": row["schema_id"], "data": loads(row["data_json"], {}), "artifacts": loads(row["artifact_ids_json"], []),
            "provenance": loads(row["provenance_json"], {}), "status": row["status"],
        })
