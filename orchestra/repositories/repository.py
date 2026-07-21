"""The persistence boundary used by domain services."""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from uuid import UUID

from orchestra.core.events import ResearchEvent
from orchestra.storage.db import Database


def now() -> str:
    return datetime.now(UTC).isoformat()


def dumps(value: object) -> str:
    return json.dumps(value, sort_keys=True, default=str, separators=(",", ":"))


def loads(value: str | None, fallback: object | None = None):
    if not value:
        return fallback
    return json.loads(value)


class Repository:
    def __init__(self, database: Database):
        self.database = database

    def one(self, query: str, args: tuple = ()) -> dict | None:
        with self.database.read() as connection:
            row = connection.execute(query, args).fetchone()
            return dict(row) if row else None

    def all(self, query: str, args: tuple = ()) -> list[dict]:
        with self.database.read() as connection:
            return [dict(row) for row in connection.execute(query, args).fetchall()]

    def execute(self, query: str, args: tuple = ()) -> None:
        with self.database.transaction() as connection:
            connection.execute(query, args)

    def append_event(self, connection: sqlite3.Connection, event: ResearchEvent) -> None:
        connection.execute(
            """INSERT INTO events(id,project_id,run_id,branch_id,actor_id,actor_type,event_type,payload,parent_event_id,correlation_id,idempotency_key,schema_version,integrity_hash,timestamp)
               VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                event.id,
                str(event.project_id) if event.project_id else None,
                str(event.run_id) if event.run_id else None,
                str(event.branch_id) if event.branch_id else None,
                event.actor_id,
                event.actor_type,
                event.event_type,
                dumps(event.payload),
                event.parent_event_id,
                event.correlation_id,
                event.idempotency_key,
                event.schema_version,
                event.integrity_hash,
                event.timestamp.isoformat(),
            ),
        )

    def accessible_project(self, project_id: UUID | str, user_id: UUID | str, write: bool = False) -> dict | None:
        query = (
            """SELECT p.*, CASE WHEN p.owner_id=? THEN 'owner' ELSE pm.role END AS role
            FROM projects p LEFT JOIN project_members pm ON pm.project_id=p.id AND pm.user_id=?
            WHERE p.id=? AND (p.owner_id=? OR pm.role IN (?,?))"""
            if write
            else """SELECT p.*, CASE WHEN p.owner_id=? THEN 'owner' ELSE pm.role END AS role
            FROM projects p LEFT JOIN project_members pm ON pm.project_id=p.id AND pm.user_id=?
            WHERE p.id=? AND (p.owner_id=? OR pm.role IN (?,?,?,?))"""
        )
        allowed = ("owner", "editor") if write else ("owner", "editor", "reviewer", "viewer")
        return self.one(query, (str(user_id), str(user_id), str(project_id), str(user_id), *allowed))

    def events(self, project_id: str | UUID | None = None, run_id: str | UUID | None = None) -> list[dict]:
        if run_id:
            rows = self.all("SELECT * FROM events WHERE run_id=? ORDER BY timestamp,id", (str(run_id),))
        else:
            rows = self.all("SELECT * FROM events WHERE project_id=? ORDER BY timestamp,id", (str(project_id),))
        for row in rows:
            row["payload"] = loads(row["payload"], {})
        return rows
