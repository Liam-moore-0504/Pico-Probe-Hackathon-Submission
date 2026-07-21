"""Grounded opportunity detection over authorized project records."""

from __future__ import annotations

from uuid import uuid4

from orchestra.discovery.models import ResearchOpportunity
from orchestra.repositories.repository import Repository, dumps, loads, now


class DiscoveryEngine:
    def __init__(self, repository: Repository):
        self.repo = repository

    def scan(self, project_id: str) -> list[dict]:
        claims = self.repo.all("SELECT c.*,n.kind FROM claims c JOIN nodes n ON n.id=c.node_id WHERE c.project_id=?", (project_id,))
        dead_ends = self.repo.all("SELECT * FROM dead_ends WHERE project_id=?", (project_id,))
        existing = self.repo.all("SELECT * FROM research_opportunities WHERE project_id=?", (project_id,))
        if existing:
            return [self._decode(row) for row in existing]
        opportunities: list[ResearchOpportunity] = []
        for claim in claims:
            checks = self.repo.one("SELECT COUNT(*) count FROM edges e JOIN nodes n ON n.id=e.source_id WHERE e.target_id=? AND n.kind IN ('formal_verification','computation','simulation','evidence')", (claim["node_id"],))
            if not checks or checks["count"] == 0:
                opportunities.append(self._opportunity(project_id, "missing_proof", f"Verify: {claim['statement'][:120]}", "A recorded claim has no independent verification edge.", [claim["node_id"]], ["symbolic_verification", "formal_verification"]))
        for dead_end in dead_ends:
            opportunities.append(self._opportunity(project_id, "unresolved_dead_end", f"Revisit with changed assumptions: {dead_end['approach'][:100]}", dead_end["lesson"], [dead_end["node_id"]], ["counterexample_search"]))
        if not opportunities:
            opportunities.append(self._opportunity(project_id, "formalization_opportunity", "Formalize the project question", "No typed claim is yet available for verification.", [], ["formalization"]))
        for item in opportunities:
            self.repo.execute("INSERT INTO research_opportunities VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (item.id, project_id, item.opportunity_type, item.title, item.description, dumps(item.source_nodes), item.why_gap, item.novelty_scope, item.feasibility, item.expected_impact, dumps(item.required_capabilities), dumps(item.suggested_pipeline), item.uncertainty, dumps(item.known_risks), "open", now()))
        return [item.model_dump(mode="json") for item in opportunities]

    @staticmethod
    def _opportunity(project_id: str, kind: str, title: str, reason: str, sources: list[str], capabilities: list[str]) -> ResearchOpportunity:
        return ResearchOpportunity(id="opp_" + uuid4().hex, project_id=project_id, opportunity_type=kind, title=title, description=reason, source_nodes=sources, why_gap=reason, novelty_scope="No close match was found within this project's indexed records; no global novelty claim is made.", feasibility=0.7, expected_impact=0.6, required_capabilities=capabilities, suggested_pipeline={"template": "assurance-research-loop"}, uncertainty="Literature coverage and semantic retrieval may be incomplete.", known_risks=["Scope may be underspecified", "Indexed evidence may be incomplete"])

    @staticmethod
    def _decode(row: dict) -> dict:
        return {**row, "source_nodes": loads(row["source_nodes"], []), "required_capabilities": loads(row["required_capabilities"], []), "suggested_pipeline": loads(row["suggested_pipeline"], {}), "known_risks": loads(row["risks"], [])}
