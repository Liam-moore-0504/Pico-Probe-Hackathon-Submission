"""Compile visual DAGs into assurance-aware, typed execution plans."""

from __future__ import annotations

import hashlib
from uuid import uuid4

from orchestra.pipelines.models import (
    ANY_SCHEMA,
    CompiledEdge,
    CompiledNode,
    CompiledPipeline,
    CostEstimate,
    DownstreamExpectation,
    NodeAssuranceRequirements,
    NodeInterface,
    PipelineDefinition,
    PortSpec,
)
from orchestra.pipelines.validation import schemas_compatible, validate_graph
from orchestra.protocol.contracts import AssuranceContract
from orchestra.repositories.repository import Repository, dumps, loads, now


class PipelineCompilationError(ValueError):
    def __init__(self, errors: list[str]):
        super().__init__("; ".join(errors))
        self.errors = errors


class PipelineCompiler:
    def __init__(self, repository: Repository, plugin_registry):
        self.repo = repository
        self.plugins = plugin_registry

    def compile(self, pipeline: dict, allow_default_contract: bool = False, persist: bool = True) -> CompiledPipeline:
        raw = pipeline["definition"]
        definition = PipelineDefinition.model_validate(raw)
        self._hydrate_interfaces(definition)
        self._specialize_generator_outputs(definition)
        errors, order = validate_graph(definition)
        contract, contract_source = self._contract(pipeline["project_id"], allow_default_contract)
        if contract is None:
            errors.append("An active Assurance Contract is required; explicitly select the safe default or create one")
        nodes = {node.id: node for node in definition.nodes}
        compiled_edges: list[CompiledEdge] = []
        for edge in definition.edges:
            if edge.source not in nodes or edge.target not in nodes:
                continue
            source_port = self._port(nodes[edge.source].interface.output_ports, edge.source_port)
            target_port = self._port(nodes[edge.target].interface.input_ports, edge.target_port)
            if not source_port or not target_port:
                errors.append(f"Unknown port on {edge.source}.{edge.source_port} -> {edge.target}.{edge.target_port}")
                continue
            compatible, reason = schemas_compatible(source_port, target_port)
            if not compatible and not edge.mapping:
                errors.append(f"Incompatible edge {edge.source}.{edge.source_port} -> {edge.target}.{edge.target_port}: {reason}")
            compiled_edges.append(CompiledEdge(**edge.model_dump(), compatible=compatible or bool(edge.mapping), compatibility_reason=reason))
        if errors:
            raise PipelineCompilationError(errors)
        assert contract is not None
        compiled_nodes: list[CompiledNode] = []
        for node in definition.nodes:
            incoming = [edge for edge in compiled_edges if edge.target == node.id]
            outgoing = [edge for edge in compiled_edges if edge.source == node.id]
            downstream: list[DownstreamExpectation] = []
            for edge in outgoing:
                target = nodes[edge.target]
                target_port = self._port(target.interface.input_ports, edge.target_port)
                downstream.append(
                    DownstreamExpectation(
                        target_pipeline_node_id=target.id,
                        target_node_type=target.type,
                        target_plugin_id=target.config.get("plugin"),
                        source_port=edge.source_port,
                        target_port=edge.target_port,
                        relation=edge.relation,
                        required_input_schema=target_port.json_schema if target_port else {},
                        human_description=(target_port.description if target_port else "") or f"Produce data directly consumable by {target.config.get('label') or target.id}.",
                    )
                )
            output_ports = {edge.source_port: self._port(node.interface.output_ports, edge.source_port) for edge in outgoing}
            if not outgoing:
                output_ports = {port.name: port for port in node.interface.output_ports}
            output_ports = {name: port for name, port in output_ports.items() if port is not None}
            port_schema = {
                "type": "object",
                "required": ["ports"],
                "properties": {"ports": {"type": "object", "required": list(output_ports), "properties": {name: port.json_schema for name, port in output_ports.items()}}},
            }
            assurance = self._assurance_for(node.type, node.config.get("plugin"), contract)
            compiled_nodes.append(
                CompiledNode(
                    **node.model_dump(),
                    predecessor_ids=[edge.source for edge in incoming],
                    successor_ids=[edge.target for edge in outgoing],
                    downstream=downstream,
                    assurance=assurance,
                    required_output_schema=port_schema if output_ports else dict(ANY_SCHEMA),
                    required_output_type="pico.multi_port.v1" if len(output_ports) > 1 else (next(iter(output_ports.values())).schema_id if output_ports else "pico.any.v1"),
                    required_output_ports=output_ports,
                )
            )
        encoded_contract = dumps(contract.model_dump(mode="json"))
        cost_maximum = sum(int(node.config.get("cost_cap_micros", 0)) for node in definition.nodes)
        plan = CompiledPipeline(
            compilation_id="compile_" + uuid4().hex,
            pipeline_id=pipeline["id"], pipeline_version=pipeline["version"], project_id=pipeline["project_id"],
            contract_id=contract.id, contract_version=contract.version,
            contract_hash=hashlib.sha256(encoded_contract.encode()).hexdigest(), contract=contract.model_dump(mode="json"),
            nodes=compiled_nodes, edges=compiled_edges, topological_order=order,
            warnings=["Safe default Assurance Contract selected explicitly"] if contract_source == "default" else [],
            cost_estimate=CostEstimate(expected_micros=cost_maximum // 2, maximum_micros=cost_maximum), compiled_at=now(),
        )
        if persist:
            self.repo.execute(
                "INSERT INTO pipeline_compilations VALUES(?,?,?,?,?,?,?,?,?)",
                (plan.compilation_id, plan.pipeline_id, plan.pipeline_version, plan.project_id, plan.contract_id, plan.contract_hash, dumps(plan.model_dump(mode="json")), "valid", plan.compiled_at),
            )
        return plan

    def _hydrate_interfaces(self, definition: PipelineDefinition) -> None:
        for node in definition.nodes:
            if node.interface.input_ports or node.interface.output_ports:
                continue
            plugin_id = node.config.get("plugin")
            if plugin_id:
                try:
                    manifest = self.plugins.get(plugin_id).manifest
                    node.interface = NodeInterface(
                        input_ports=[PortSpec(name="request", schema_id=f"{plugin_id}.input.v1", json_schema=manifest.input_schema or dict(ANY_SCHEMA), description=f"Input contract for {manifest.name}")],
                        output_ports=[PortSpec(name="result", schema_id=f"{plugin_id}.output.v1", json_schema=manifest.output_schema or dict(ANY_SCHEMA), description=f"Result from {manifest.name}")],
                    )
                    continue
                except KeyError:
                    pass
            node.interface = NodeInterface(
                input_ports=[] if node.type in {"question", "formalization"} else [PortSpec(name="context", required=False, accepts_multiple=True)],
                output_ports=[PortSpec(name="result")],
            )
        for edge in definition.edges:
            source = next((node for node in definition.nodes if node.id == edge.source), None)
            target = next((node for node in definition.nodes if node.id == edge.target), None)
            if source and edge.source_port == "result" and source.interface.output_ports:
                edge.source_port = source.interface.output_ports[0].name
            if target and edge.target_port == "context" and target.interface.input_ports:
                edge.target_port = target.interface.input_ports[0].name

    @staticmethod
    def _specialize_generator_outputs(definition: PipelineDefinition) -> None:
        nodes = {node.id: node for node in definition.nodes}
        for node in definition.nodes:
            outgoing = [edge for edge in definition.edges if edge.source == node.id]
            if node.config.get("plugin") or not outgoing or not node.interface.output_ports:
                continue
            legacy_port = node.interface.output_ports[0]
            if len(node.interface.output_ports) == 1 and legacy_port.schema_id == "pico.any.v1" and len(outgoing) > 1:
                node.interface.output_ports = []
                for edge in outgoing:
                    target = nodes.get(edge.target)
                    target_port = next((port for port in (target.interface.input_ports if target else []) if port.name == edge.target_port), None)
                    name = f"{edge.target}_{edge.target_port}"
                    edge.source_port = name
                    node.interface.output_ports.append(PortSpec(name=name, schema_id=target_port.schema_id if target_port else "pico.any.v1", json_schema=target_port.json_schema if target_port else dict(ANY_SCHEMA), description=f"Structured output for {edge.target}.{edge.target_port}"))
                continue
            for edge in outgoing:
                target = nodes.get(edge.target)
                target_port = next((port for port in (target.interface.input_ports if target else []) if port.name == edge.target_port), None)
                source_port = next((port for port in node.interface.output_ports if port.name == edge.source_port), None)
                if target_port and source_port and source_port.schema_id == "pico.any.v1":
                    source_port.schema_id = target_port.schema_id
                    source_port.json_schema = target_port.json_schema
                    source_port.description = f"Structured output for downstream {target.id}.{target_port.name}"

    def _contract(self, project_id: str, allow_default: bool) -> tuple[AssuranceContract | None, str]:
        row = self.repo.one("SELECT * FROM assurance_contracts WHERE project_id=? AND active=1 ORDER BY version DESC LIMIT 1", (project_id,))
        if row:
            return AssuranceContract.model_validate({"id": row["id"], "version": row["version"], **loads(row["content"], {})}), "stored"
        legacy = self.repo.one("SELECT id,version,content FROM nodes WHERE project_id=? AND kind='human_review' AND title='Epistemic Contract' ORDER BY version DESC LIMIT 1", (project_id,))
        if legacy:
            content = loads(legacy["content"], {})
            if isinstance(content.get("human_checkpoints"), str):
                content["human_checkpoints"] = [content["human_checkpoints"]]
            return AssuranceContract.model_validate({"id": legacy["id"], "version": legacy["version"], **content}), "legacy"
        return (AssuranceContract(id="default-safe-v1"), "default") if allow_default else (None, "missing")

    @staticmethod
    def _port(ports: list[PortSpec], name: str) -> PortSpec | None:
        return next((port for port in ports if port.name == name), None)

    @staticmethod
    def _assurance_for(node_type: str, plugin_id: str | None, contract: AssuranceContract) -> NodeAssuranceRequirements:
        experiment = plugin_id in {"core.python_experiment", "core.monte_carlo"} or node_type in {"experiment", "experimental_design"}
        return NodeAssuranceRequirements(
            require_assumptions=node_type in {"hypothesis", "hypothesis_generation", "synthesis", "conclusion"},
            require_falsification_conditions=node_type in {"hypothesis", "hypothesis_generation"},
            require_seed=experiment,
            require_sources=node_type in {"literature", "literature_search"},
            require_independent_check=node_type in {"synthesis", "conclusion"} and contract.minimum_independent_checks > 0,
            preserve_tool_output=bool(plugin_id),
            rules=[contract.uncertainty_policy, "A node may not self-certify its own generated claim."],
        )
