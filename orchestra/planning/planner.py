from pydantic import BaseModel, Field


class WorkflowStep(BaseModel):
    capability: str
    plugin_id: str
    reason: str


class WorkflowPlan(BaseModel):
    goal: str
    steps: list[WorkflowStep] = Field(default_factory=list)
    missing_capabilities: list[str] = Field(default_factory=list)


class CapabilityPlanner:
    def __init__(self, r):
        self.r = r

    def plan(self, goal, required):
        steps = []
        missing = []
        for c in required:
            m = sorted(self.r.by_capability(c), key=lambda p: (-p.manifest.reliability, p.manifest.plugin_id))
            if not m:
                missing.append(c)
            else:
                steps.append(WorkflowStep(capability=c, plugin_id=m[0].manifest.plugin_id, reason="Highest reliability available plugin"))
        return WorkflowPlan(goal=goal, steps=steps, missing_capabilities=missing)
