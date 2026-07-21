"""Portable SQLite/PostgreSQL connections with deterministic migrations."""

from __future__ import annotations

import re
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ALEMBIC_SCHEMA_HEAD = "20260720_0005"


def sqlite_schema_head() -> str:
    migration_dir = Path(__file__).resolve().parents[2] / "migrations"
    versions = [migration.stem.split("_", 1)[0] for migration in migration_dir.glob("*.sql")]
    if not versions:
        raise RuntimeError("No packaged database migrations were found")
    return max(versions)


def _postgres_query(query: str) -> str:
    return re.sub(r"\?", "%s", query)


class Database:
    def __init__(self, target: str):
        self.target = target
        self.is_postgres = target.startswith(("postgresql://", "postgresql+psycopg://"))
        self.path = target
        if not self.is_postgres and target != ":memory:":
            Path(target).expanduser().parent.mkdir(parents=True, exist_ok=True)

    def connect(self):
        if self.is_postgres:
            import psycopg
            from psycopg.rows import dict_row

            url = self.target.replace("postgresql+psycopg://", "postgresql://", 1)
            return PostgresConnection(psycopg.connect(url, row_factory=dict_row))
        connection = sqlite3.connect(self.path, timeout=15, check_same_thread=False)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA journal_mode=WAL")
        return connection

    @contextmanager
    def transaction(self) -> Iterator[Any]:
        connection = self.connect()
        try:
            if not self.is_postgres:
                connection.execute("BEGIN IMMEDIATE")
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    @contextmanager
    def read(self) -> Iterator[Any]:
        connection = self.connect()
        try:
            yield connection
        finally:
            connection.close()

    def migrate(self) -> None:
        migration_dir = Path(__file__).resolve().parents[2] / "migrations"
        with self.connect() as connection:
            if self.is_postgres:
                connection.execute("CREATE TABLE IF NOT EXISTS schema_migrations(version TEXT PRIMARY KEY, applied_at TEXT NOT NULL)")
                applied = {row["version"] for row in connection.execute("SELECT version FROM schema_migrations").fetchall()}
            else:
                exists = connection.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='schema_migrations'").fetchone()
                applied = {row[0] for row in connection.execute("SELECT version FROM schema_migrations")} if exists else set()
            for migration in sorted(migration_dir.glob("*.sql")):
                version = migration.stem.split("_", 1)[0]
                if version in applied:
                    continue
                script = migration.read_text()
                if self.is_postgres:
                    script = script.replace("PRAGMA foreign_keys=ON;", "").replace("CREATE TABLE schema_migrations(version TEXT PRIMARY KEY, applied_at TEXT NOT NULL);", "")
                    connection.executescript(script)
                    connection.execute("INSERT INTO schema_migrations(version,applied_at) VALUES(?,?)", (version, datetime.now(UTC).isoformat()))
                else:
                    connection.executescript(script)
                    connection.execute("INSERT INTO schema_migrations(version,applied_at) VALUES(?,datetime('now'))", (version,))
                connection.commit()

    init = migrate


class PostgresConnection:
    def __init__(self, connection):
        self.connection = connection

    def execute(self, query: str, args: tuple = ()):
        return self.connection.execute(_postgres_query(query), args)

    def executescript(self, script: str) -> None:
        for statement in (part.strip() for part in script.split(";")):
            if statement:
                self.connection.execute(statement)

    def commit(self):
        self.connection.commit()

    def rollback(self):
        self.connection.rollback()

    def close(self):
        self.connection.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        if exc:
            self.rollback()
        else:
            self.commit()
        self.close()


def row_dict(row) -> dict | None:
    return dict(row) if row else None
