"""Assurance checks that must pass before an output can cross an edge."""

from __future__ import annotations

from typing import Any

from orchestra.kernel.execution_envelope import NodeExecutionEnvelope


class AssuranceOutputValidator:
    @staticmethod
    def validate(envelope: NodeExecutionEnvelope, port: str, data: Any, raw: dict) -> list[str]:
        if not isinstance(data, dict):
            return []
        requirements = envelope.node_assurance_requirements
        errors: list[str] = []
        if requirements.get("require_seed") and data.get("seed") is None:
            errors.append(f"{port}: Assurance rule requires a deterministic seed")
        if data.get("verified") is True and not (raw.get("formal") or raw.get("engine") == "lean"):
            errors.append(f"{port}: A model output cannot self-certify formal verification")
        if raw.get("provider") and data.get("artifacts"):
            errors.append(f"{port}: A provider cannot claim artifact creation without kernel-issued artifact references")

        research_objects = data.get("objects", [])
        if isinstance(research_objects, list):
            for index, item in enumerate(research_objects):
                if not isinstance(item, dict):
                    errors.append(f"{port}.objects[{index}] must be an object")
                    continue
                if item.get("id") is not None and (not isinstance(item["id"], str) or not item["id"].strip()):
                    errors.append(f"{port}.objects[{index}].id must be a non-empty string")
                dependencies = item.get("dependencies", [])
                if not isinstance(dependencies, list) or any(not isinstance(value, str) or not value for value in dependencies):
                    errors.append(f"{port}.objects[{index}].dependencies must contain non-empty object IDs")
                if requirements.get("require_assumptions") and item.get("type") in {"claim", "hypothesis", "conclusion"} and not item.get("assumptions"):
                    errors.append(f"{port}.objects[{index}] requires explicit assumptions")
                if requirements.get("require_falsification_conditions") and item.get("type") in {"claim", "hypothesis"} and not item.get("falsification_conditions"):
                    errors.append(f"{port}.objects[{index}] requires falsification conditions")
                if requirements.get("require_sources") and item.get("type") in {"literature", "evidence"} and not item.get("sources"):
                    errors.append(f"{port}.objects[{index}] requires source identifiers")
        return errors
