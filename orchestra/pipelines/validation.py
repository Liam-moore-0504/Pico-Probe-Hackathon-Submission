"""Graph and port-level validation for research pipelines."""

from __future__ import annotations

from collections import deque

from orchestra.pipelines.models import PipelineDefinition, PortSpec


def schemas_compatible(source: PortSpec, target: PortSpec) -> tuple[bool, str]:
    if "pico.any.v1" in {source.schema_id, target.schema_id}:
        return True, "compatible"
    compatible, detail = _schema_assignable(source.json_schema, target.json_schema)
    if compatible:
        return True, "structurally compatible JSON schema"
    if detail:
        return False, f"{source.schema_id} cannot feed {target.schema_id}: {detail}"
    return False, f"{source.schema_id} cannot feed {target.schema_id}"


def _schema_assignable(source: dict, target: dict, path: str = "$") -> tuple[bool, str]:
    """Return whether every value guaranteed by source is accepted by target."""
    source_type, target_type = source.get("type"), target.get("type")
    if source_type == "integer" and target_type == "number":
        return True, ""
    if source_type != target_type:
        return False, f"{path} emits {source_type or 'unspecified'} but requires {target_type or 'unspecified'}"
    if target.get("enum") and not set(source.get("enum", [])) <= set(target["enum"]):
        return False, f"{path} enum is not a subset of the target enum"
    if target_type == "object":
        source_properties = source.get("properties", {})
        target_properties = target.get("properties", {})
        for name in target.get("required", []):
            if name not in source.get("required", []) or name not in source_properties:
                return False, f"{path}.{name} is not guaranteed by the source"
        for name in source_properties.keys() & target_properties.keys():
            compatible, detail = _schema_assignable(source_properties[name], target_properties[name], f"{path}.{name}")
            if not compatible:
                return False, detail
        if target.get("additionalProperties") is False:
            if source.get("additionalProperties", True) is not False or not set(source_properties) <= set(target_properties):
                return False, f"{path} may emit properties forbidden by the target"
    if target_type == "array" and target.get("items") and source.get("items"):
        return _schema_assignable(source["items"], target["items"], f"{path}[]")
    return True, ""


def validate_graph(definition: PipelineDefinition) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    nodes = {node.id: node for node in definition.nodes}
    if len(nodes) != len(definition.nodes):
        errors.append("Pipeline node IDs must be unique")
    indegree = {node_id: 0 for node_id in nodes}
    outgoing = {node_id: [] for node_id in nodes}
    seen_edges: set[tuple[str, str, str, str]] = set()
    for edge in definition.edges:
        if edge.source not in nodes or edge.target not in nodes:
            errors.append(f"Edge {edge.source} -> {edge.target} references a missing node")
            continue
        if edge.source == edge.target:
            errors.append(f"Node {edge.source} cannot connect to itself")
        key = (edge.source, edge.source_port, edge.target, edge.target_port)
        if key in seen_edges:
            errors.append(f"Duplicate port edge {edge.source}.{edge.source_port} -> {edge.target}.{edge.target_port}")
        seen_edges.add(key)
        outgoing[edge.source].append(edge.target)
        indegree[edge.target] += 1
    queue = deque(sorted(node_id for node_id, count in indegree.items() if count == 0))
    order: list[str] = []
    while queue:
        node_id = queue.popleft()
        order.append(node_id)
        for target in outgoing[node_id]:
            indegree[target] -= 1
            if indegree[target] == 0:
                queue.append(target)
    if len(order) != len(nodes):
        errors.append("Pipeline contains a cycle or unreachable cyclic component")
    return errors, order
