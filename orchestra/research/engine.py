from orchestra.core.enums import NodeKind
from orchestra.core.events import ResearchEvent
from orchestra.core.models import ResearchNode


class ResearchEngine:
    def __init__(self, pid, db, registry):
        self.pid = pid
        self.db = db
        self.registry = registry

    def claim(self, x):
        self.db.save_claim(self.pid, x)
        n = ResearchNode(kind=NodeKind.CLAIM, title=x.statement, content=x.model_dump(mode="json"), status=x.status.value, provenance={"proposed_by": x.proposed_by})
        self.db.save_node(self.pid, n)
        self.db.event(ResearchEvent(project_id=self.pid, event_type="CLAIM_CREATED", actor=x.proposed_by, payload=x.model_dump(mode="json")))
        return x

    def evidence(self, x):
        self.db.save_evidence(self.pid, x)
        n = ResearchNode(kind=NodeKind.EVIDENCE, title=x.title, content=x.model_dump(mode="json"), status="completed", provenance={"source": x.source})
        self.db.save_node(self.pid, n)
        self.db.event(ResearchEvent(project_id=self.pid, event_type="EVIDENCE_RECORDED", actor=x.source, payload=x.model_dump(mode="json")))
        return x

    def dead_end(self, x):
        x.fingerprint = self.db.save_dead_end(self.pid, x)
        n = ResearchNode(kind=NodeKind.DEAD_END, title=x.approach, content=x.model_dump(mode="json"), status="failed", provenance={"discovered_by": x.discovered_by})
        self.db.save_node(self.pid, n)
        self.db.event(ResearchEvent(project_id=self.pid, event_type="DEAD_END_RECORDED", actor=x.discovered_by, payload=x.model_dump(mode="json")))
        return x

    def experiment(self, x):
        self.db.save_experiment(self.pid, x)
        n = ResearchNode(kind=NodeKind.EXPERIMENT, title=x.name, content=x.model_dump(mode="json"), status="completed")
        self.db.save_node(self.pid, n)
        self.db.event(ResearchEvent(project_id=self.pid, event_type="EXPERIMENT_RECORDED", actor="kernel", payload=x.model_dump(mode="json")))
        return x

    def tool(self, k, payload, actor):
        p = self.registry.get(k)
        r = p.execute(payload)
        n = ResearchNode(
            kind=NodeKind.COMPUTATION,
            title=k + " execution",
            content={"plugin": k, "input": payload, "result": r},
            status=r.get("status", "completed"),
            provenance={"plugin_version": p.manifest.version, "actor": actor},
        )
        self.db.save_node(self.pid, n)
        self.db.event(ResearchEvent(project_id=self.pid, event_type="PLUGIN_EXECUTED", actor=actor, payload={"plugin": k, "result": r}))
        return r
