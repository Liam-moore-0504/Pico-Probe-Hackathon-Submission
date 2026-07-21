from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from orchestra.repositories.repository import Repository, now


class BillingPolicyService:
    def __init__(self, repository: Repository):
        self.repo = repository

    def add_pricing(self, actor: UUID, data: dict) -> dict:
        rule_id = str(uuid4())
        self.repo.execute(
            "INSERT INTO pricing_rules VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                rule_id,
                data["provider"],
                data["model_pattern"],
                data["input_micros_per_million"],
                data["output_micros_per_million"],
                data.get("cache_micros_per_million", 0),
                data.get("currency", "USD"),
                data["effective_at"],
                data.get("markup", 0),
                data["source"],
                int(data.get("active", False)),
                str(actor),
                now(),
            ),
        )
        return self.repo.one("SELECT * FROM pricing_rules WHERE id=?", (rule_id,))

    def set_quota(self, user_id: str | None, data: dict) -> dict:
        quota_id = str(uuid4())
        self.repo.execute(
            "INSERT INTO quota_policies VALUES(?,?,?,?,?,?,?)",
            (quota_id, user_id, data["monthly_micros"], data["per_run_micros"], data["max_parallel_runs"], data.get("effective_at", now()), now()),
        )
        return self.repo.one("SELECT * FROM quota_policies WHERE id=?", (quota_id,))

    def enforce(self, user_id: str, maximum_micros: int) -> None:
        policy = self.repo.one(
            "SELECT * FROM quota_policies WHERE user_id=? OR user_id IS NULL ORDER BY CASE WHEN user_id=? THEN 0 ELSE 1 END,effective_at DESC LIMIT 1", (user_id, user_id)
        )
        if not policy:
            return
        if maximum_micros > policy["per_run_micros"]:
            raise ValueError("Run exceeds the configured cost quota")
        month = datetime.now(UTC).strftime("%Y-%m")
        usage = self.repo.one(
            "SELECT COALESCE(-SUM(amount_micros),0) used FROM ledger_entries WHERE user_id=? AND entry_type='usage' AND substr(created_at,1,7)=?", (user_id, month)
        )["used"]
        if usage + maximum_micros > policy["monthly_micros"]:
            raise ValueError("Monthly usage quota would be exceeded")
        parallel = self.repo.one("SELECT COUNT(*) count FROM runs WHERE created_by=? AND status IN ('queued','running')", (user_id,))["count"]
        if parallel >= policy["max_parallel_runs"]:
            raise ValueError("Parallel run quota has been reached")
