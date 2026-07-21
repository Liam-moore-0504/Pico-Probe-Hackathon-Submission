"""Validate every output port and emit canonical lineage-preserving messages."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from orchestra.kernel.execution_envelope import NodeExecutionEnvelope
from orchestra.protocol.adapters import validate_minimal
from orchestra.protocol.assurance_validation import AssuranceOutputValidator
from orchestra.protocol.port_message import PicoPortMessage, ProvenanceRecord


class OutputValidationError(ValueError):
    def __init__(self, errors: list[str], raw: dict):
        super().__init__("; ".join(errors))
        self.errors, self.raw = errors, raw


@dataclass
class ValidatedOutput:
    result: dict
    messages: list[PicoPortMessage]
    repaired: bool
    errors_before_repair: list[str]


class OutputValidator:
    def validate_or_repair(self, envelope: NodeExecutionEnvelope, raw_result: dict) -> ValidatedOutput:
        if raw_result.get("status") == "waiting_for_user":
            return ValidatedOutput(raw_result, [], False, [])
        ports = self._candidate_ports(envelope, raw_result)
        errors = self._errors(envelope, ports, raw_result)
        repaired = False
        original_errors = list(errors)
        if errors and raw_result.get("execution_mode") == "mock":
            ports = {name: self.fixture(schema, envelope.research_question) for name, schema in envelope.output_port_contracts.items()}
            errors = self._errors(envelope, ports, raw_result)
            repaired = True
        if errors:
            raise OutputValidationError(errors, raw_result)
        messages = self._messages(envelope, raw_result, ports, repaired)
        result = {**raw_result, "ports": ports, "output_messages": [message.model_dump(mode="json") for message in messages], "validated": True, "output_schema_id": envelope.required_output_type}
        return ValidatedOutput(result, messages, repaired, original_errors)

    @staticmethod
    def _decoded(raw: dict) -> Any:
        if raw.get("ports"):
            return {"ports": raw["ports"]}
        content = raw.get("content")
        if isinstance(content, dict):
            return content
        if isinstance(content, str):
            try:
                return json.loads(content)
            except json.JSONDecodeError:
                return content
        return raw.get("result") if isinstance(raw.get("result"), dict) else raw

    def _candidate_ports(self, envelope: NodeExecutionEnvelope, raw: dict) -> dict[str, Any]:
        decoded = self._decoded(raw)
        if isinstance(decoded, dict) and isinstance(decoded.get("ports"), dict):
            values = decoded["ports"]
            return {name: value.get("data", value) if isinstance(value, dict) else value for name, value in values.items()}
        names = list(envelope.output_port_contracts)
        return {names[0]: decoded} if len(names) == 1 else {}

    @staticmethod
    def _errors(envelope: NodeExecutionEnvelope, ports: dict[str, Any], raw: dict) -> list[str]:
        errors: list[str] = []
        for name, schema in envelope.output_port_contracts.items():
            if name not in ports:
                errors.append(f"Required output port {name} is missing")
                continue
            errors.extend(f"{name}: {error}" for error in validate_minimal(ports[name], schema))
            errors.extend(AssuranceOutputValidator.validate(envelope, name, ports[name], raw))
        extras = set(ports) - set(envelope.output_port_contracts)
        errors.extend(f"Unexpected output port {name}" for name in sorted(extras))
        return errors

    @classmethod
    def fixture(cls, schema: dict, question: str) -> Any:
        if "default" in schema:
            return schema["default"]
        if schema.get("enum"):
            return schema["enum"][0]
        expected = schema.get("type", "object")
        if expected == "object":
            result = {name: cls.fixture(child, question) for name, child in schema.get("properties", {}).items() if name in schema.get("required", [])}
            if "research_question" in schema.get("properties", {}):
                result["research_question"] = question
            return result
        return {"string": "rehearsal fixture", "integer": 1000, "number": 0.0, "boolean": False, "array": []}.get(expected)

    @staticmethod
    def _messages(envelope: NodeExecutionEnvelope, raw: dict, ports: dict[str, Any], repaired: bool) -> list[PicoPortMessage]:
        producer_type = "provider" if raw.get("provider") else ("plugin" if raw.get("plugin_id") or raw.get("engine") else "kernel")
        source_ids = [message.message_id for message in envelope.inputs]
        return [
            PicoPortMessage(
                project_id=envelope.project_id, run_id=envelope.run_id, branch_id=envelope.branch_id,
                pipeline_id=envelope.pipeline_id, pipeline_version=envelope.pipeline_version, pipeline_node_id=envelope.pipeline_node_id,
                direction="output", port=name, schema_id=envelope.output_port_schema_ids.get(name, "pico.any.v1"), data=data,
                provenance=ProvenanceRecord(
                    producer_type=producer_type, producer_id=raw.get("provider") or raw.get("plugin_id") or raw.get("engine") or envelope.pipeline_node_id,
                    producer_version=raw.get("model") or raw.get("plugin_version") or raw.get("engine_version"), provider_execution_id=raw.get("execution_id"),
                    source_message_ids=source_ids, source_object_ids=[object_id for message in envelope.inputs for object_id in message.object_ids],
                    repaired=repaired, repair_count=1 if repaired else 0,
                    assurance_contract_id=envelope.epistemic_contract.get("id"), assurance_contract_version=envelope.epistemic_contract.get("version"),
                ),
            )
            for name, data in ports.items()
        ]
