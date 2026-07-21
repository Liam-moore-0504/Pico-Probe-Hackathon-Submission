"""Derive benchmark measurements from persisted runs without model-authored scores."""

from __future__ import annotations

import json
from pathlib import Path
from uuid import UUID, uuid4

from orchestra.repositories.repository import Repository, dumps, loads, now


class BenchmarkService:
    def __init__(self, repository: Repository, research_service):
        self.repo, self.research = repository, research_service
        self._load_tasks()

    def tasks(self) -> list[dict]:
        rows = self.repo.all("SELECT * FROM benchmark_tasks ORDER BY name")
        for row in rows:
            row["fixture"] = loads(row["fixture"], {})
            row["metrics_schema"] = loads(row["metrics_schema"], [])
        return rows

    def execute(self, actor: UUID, task_id: str, mode: str, run_id: str) -> dict:
        task = self.repo.one("SELECT id FROM benchmark_tasks WHERE id=?", (task_id,))
        if not task:
            raise ValueError("Benchmark task not found")
        run = self.research.run(actor, run_id)
        project_id = run["project_id"]

        def scalar(query: str, args: tuple = ()):
            return self.repo.one(query, args)["value"]

        claims = scalar("SELECT COUNT(*) value FROM claims WHERE project_id=?", (project_id,))
        covered = scalar("SELECT COUNT(DISTINCT claim_id) value FROM evidence WHERE project_id=?", (project_id,))
        nodes = self.repo.all("SELECT version,provenance,content,kind FROM nodes WHERE run_id=?", (run_id,))
        complete_provenance = sum(bool(loads(node["provenance"], {})) for node in nodes)
        reproducible = sum(
            node["kind"] in {"experiment", "simulation"} and any(key in loads(node["content"], {}) for key in ("seed", "reproducibility", "environment_hash")) for node in nodes
        )
        duplicate_dead_ends = scalar(
            "SELECT COALESCE(SUM(count-1),0) value FROM (SELECT COUNT(*) count FROM dead_ends WHERE run_id=? GROUP BY fingerprint HAVING COUNT(*)>1) duplicates",
            (run_id,),
        )
        metrics = {
            "measurement_source": "persisted_run",
            "source_run_id": run_id,
            "correct_counterexamples": scalar("SELECT COUNT(*) value FROM evidence WHERE project_id=? AND evidence_type='counterexample'", (project_id,)),
            "algebra_verified": scalar("SELECT COUNT(*) value FROM evidence WHERE project_id=? AND evidence_type='symbolic_verification'", (project_id,)),
            "formal_proof_success": scalar("SELECT COUNT(*) value FROM evidence WHERE project_id=? AND evidence_type='formal_verification' AND stance='supports'", (project_id,)),
            "repeated_dead_ends": duplicate_dead_ends,
            "reproducibility": reproducible,
            "evidence_coverage": covered / claims if claims else 0,
            "provenance_completeness": complete_provenance / len(nodes) if nodes else 0,
            "cost_micros": -scalar("SELECT COALESCE(SUM(amount_micros),0) value FROM ledger_entries WHERE run_id=? AND entry_type='usage'", (run_id,)),
            "latency_ms": float(scalar("SELECT COALESCE(SUM(latency_ms),0) value FROM provider_executions WHERE run_id=?", (run_id,))),
            "revisions": sum(max(0, int(node["version"]) - 1) for node in nodes),
            "human_interventions": scalar("SELECT COUNT(*) value FROM events WHERE run_id=? AND event_type='HUMAN_DECISION_RECORDED'", (run_id,)),
        }
        benchmark_id = str(uuid4())
        self.repo.execute("INSERT INTO benchmark_runs VALUES(?,?,?,?,?,?)", (benchmark_id, str(actor), task_id, mode, dumps(metrics), now()))
        return {"id": benchmark_id, "task_id": task_id, "mode": mode, "metrics": metrics}

    def _load_tasks(self) -> None:
        tasks = json.loads((Path(__file__).with_name("tasks.json")).read_text())
        for task in tasks:
            self.repo.execute(
                "INSERT INTO benchmark_tasks VALUES(?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET name=excluded.name,fixture=excluded.fixture,metrics_schema=excluded.metrics_schema",
                (task["id"], task["name"], dumps(task["fixture"]), dumps(task["metrics_schema"]), now()),
            )
