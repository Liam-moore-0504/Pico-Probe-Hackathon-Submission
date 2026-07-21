"""Explicit port mappings and deterministic schema adapters."""

from __future__ import annotations

from typing import Any

from orchestra.pipelines.models import CompiledEdge, CompiledNode
from orchestra.protocol.port_message import PicoPortMessage, ProvenanceRecord


class InputResolutionError(ValueError):
    pass


def json_path(value: Any, path: str) -> Any:
    if path in {"$", "$."}:
        return value
    current = value
    for part in path.removeprefix("$.").split("."):
        if not part:
            continue
        if not isinstance(current, dict) or part not in current:
            raise InputResolutionError(f"Mapping path {path} does not exist")
        current = current[part]
    return current


def validate_minimal(value: Any, schema: dict[str, Any], path: str = "$") -> list[str]:
    errors: list[str] = []
    expected = schema.get("type")
    checks = {"object": dict, "array": list, "string": str, "integer": int, "number": (int, float), "boolean": bool}
    if expected in checks and not isinstance(value, checks[expected]):
        return [f"{path} must be {expected}"]
    if isinstance(value, dict):
        for name in schema.get("required", []):
            if name not in value:
                errors.append(f"{path}.{name} is required")
        if schema.get("additionalProperties") is False:
            extras = set(value) - set(schema.get("properties", {}))
            errors.extend(f"{path}.{name} is not allowed" for name in sorted(extras))
        for name, child_schema in schema.get("properties", {}).items():
            if name in value:
                errors.extend(validate_minimal(value[name], child_schema, f"{path}.{name}"))
    if isinstance(value, list) and schema.get("items"):
        for index, item in enumerate(value):
            errors.extend(validate_minimal(item, schema["items"], f"{path}[{index}]"))
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if schema.get("minimum") is not None and value < schema["minimum"]:
            errors.append(f"{path} must be at least {schema['minimum']}")
        if schema.get("maximum") is not None and value > schema["maximum"]:
            errors.append(f"{path} must be at most {schema['maximum']}")
    if isinstance(value, str):
        if schema.get("minLength") is not None and len(value) < schema["minLength"]:
            errors.append(f"{path} must contain at least {schema['minLength']} characters")
        if schema.get("maxLength") is not None and len(value) > schema["maxLength"]:
            errors.append(f"{path} must contain at most {schema['maxLength']} characters")
    if schema.get("enum") is not None and value not in schema["enum"]:
        errors.append(f"{path} must be one of {schema['enum']}")
    return errors


class InputResolver:
    """Resolve every incoming edge by named ports without discarding joins."""

    def resolve(self, node: CompiledNode, edges: list[CompiledEdge], upstream_step_outputs: dict[str, dict]) -> tuple[dict, list[dict]]:
        resolved, provenance, _messages = self.resolve_with_messages(node, edges, upstream_step_outputs)
        return resolved, provenance

    def resolve_with_messages(self, node: CompiledNode, edges: list[CompiledEdge], upstream_step_outputs: dict[str, dict], require_messages: bool = False) -> tuple[dict, list[dict], list[PicoPortMessage]]:
        incoming = [edge for edge in edges if edge.target == node.id]
        resolved: dict[str, Any] = {}
        provenance: list[dict] = []
        input_messages: list[PicoPortMessage] = []
        target_ports = {port.name: port for port in node.interface.input_ports}
        grouped: dict[str, list[Any]] = {}
        for edge in incoming:
            if edge.source not in upstream_step_outputs:
                raise InputResolutionError(f"Required upstream step {edge.source} is not completed")
            raw = upstream_step_outputs[edge.source]
            source_messages = [PicoPortMessage.model_validate(item) for item in raw.get("output_messages", [])]
            source_message = next((message for message in source_messages if message.port == edge.source_port), None)
            if require_messages and source_message is None:
                raise InputResolutionError(f"Upstream edge {edge.source}.{edge.source_port} did not provide a canonical PicoPortMessage")
            ports = raw.get("ports", {})
            source_value = source_message.data if source_message else ports.get(edge.source_port, raw)
            mapped = {key: json_path(source_value, path) for key, path in edge.mapping.items()} if edge.mapping else source_value
            grouped.setdefault(edge.target_port, []).append(mapped)
            provenance.append({"source_pipeline_node_id": edge.source, "source_port": edge.source_port, "target_port": edge.target_port, "relation": edge.relation, "schema_id": source_message.schema_id if source_message else None, "source_message_id": source_message.message_id if source_message else None, "output": raw, "source_research_node_id": raw.get("node_id")})
            if source_message:
                input_messages.append(PicoPortMessage(
                    project_id=source_message.project_id, run_id=source_message.run_id, branch_id=source_message.branch_id,
                    pipeline_id=source_message.pipeline_id, pipeline_version=source_message.pipeline_version, pipeline_node_id=node.id,
                    direction="input", port=edge.target_port, schema_id=target_ports[edge.target_port].schema_id, object_ids=source_message.object_ids,
                    data=mapped if isinstance(mapped, dict) else {"value": mapped}, artifacts=source_message.artifacts,
                    provenance=ProvenanceRecord(producer_type="kernel", producer_id="input_resolver", source_message_ids=[source_message.message_id], source_object_ids=source_message.object_ids, assurance_contract_id=source_message.provenance.assurance_contract_id, assurance_contract_version=source_message.provenance.assurance_contract_version),
                ))
        for port_name, values in grouped.items():
            port = target_ports.get(port_name)
            if not port:
                raise InputResolutionError(f"Target port {node.id}.{port_name} does not exist")
            if len(values) > 1 and not port.accepts_multiple:
                raise InputResolutionError(f"Target port {node.id}.{port_name} received an ambiguous multi-source join")
            value = values if port.accepts_multiple and len(values) > 1 else values[0]
            errors = []
            if port.accepts_multiple and len(values) > 1:
                for index, item in enumerate(values):
                    errors.extend(validate_minimal(item, port.json_schema, f"$.{port_name}[{index}]"))
            else:
                errors = validate_minimal(value, port.json_schema)
            if errors:
                raise InputResolutionError("; ".join(errors))
            resolved[port_name] = value
        for port in node.interface.input_ports:
            if port.required and incoming and port.name not in resolved:
                raise InputResolutionError(f"Required input port {node.id}.{port.name} is missing")
        return resolved, provenance, input_messages
