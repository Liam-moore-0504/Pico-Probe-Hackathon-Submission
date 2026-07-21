import json
import os
import time
from uuid import UUID

import pytest

from orchestra.kernel.execution_envelope import ExecutionBudget, NodeExecutionEnvelope
from orchestra.pipelines.models import CompiledEdge, CompiledNode, NodeInterface, PortSpec
from orchestra.protocol.adapters import InputResolutionError, InputResolver
from orchestra.protocol.ingest import ProtocolIngestor
from orchestra.protocol.output_validator import OutputValidationError, OutputValidator
from orchestra.providers.base import OpenAICompatibleProvider, ProviderRequest
from tests.conftest import account, project


def test_compile_binds_contract_and_exposes_downstream_schema(client):
    _, headers, _ = account(client, "compile_contract")
    workspace = project(client, headers, "Compiled research")
    pipeline = client.post(
        f"/projects/{workspace['id']}/pipelines",
        headers=headers,
        json={
            "name": "Generator to simulation",
            "nodes": [
                {"id": "design", "type": "experiment_design", "role": "Experimental Designer", "config": {"provider": "openai"}},
                {"id": "simulate", "type": "plugin", "role": "Numerical Analyst", "config": {"plugin": "core.monte_carlo"}},
            ],
            "edges": [{"source": "design", "target": "simulate", "relation": "produces"}],
        },
    ).json()
    rejected = client.post(f"/pipelines/{pipeline['id']}/compile", headers=headers)
    assert rejected.status_code == 422
    compiled = client.post(f"/pipelines/{pipeline['id']}/compile?allow_default_contract=true", headers=headers)
    assert compiled.status_code == 200, compiled.text
    plan = compiled.json()
    design = next(node for node in plan["nodes"] if node["id"] == "design")
    assert plan["contract_hash"]
    assert design["downstream"][0]["target_plugin_id"] == "core.monte_carlo"
    assert set(design["required_output_ports"]["result"]["json_schema"]["required"]) == {"seed", "trials"}


def test_multi_upstream_join_preserves_every_source():
    port = PortSpec(name="context", accepts_multiple=True, required=True)
    node = CompiledNode(id="compare", type="synthesis", interface=NodeInterface(input_ports=[port], output_ports=[PortSpec(name="result")]))
    edges = [
        CompiledEdge(source="a", target="compare", target_port="context"),
        CompiledEdge(source="b", target="compare", target_port="context", relation="candidate"),
    ]
    resolved, provenance = InputResolver().resolve(node, edges, {"a": {"content": "first"}, "b": {"content": "second"}})
    assert [item["content"] for item in resolved["context"]] == ["first", "second"]
    assert {item["source_pipeline_node_id"] for item in provenance} == {"a", "b"}


def test_ambiguous_join_is_rejected():
    node = CompiledNode(id="single", type="plugin", interface=NodeInterface(input_ports=[PortSpec(name="request")], output_ports=[PortSpec(name="result")]))
    edges = [CompiledEdge(source="a", target="single", target_port="request"), CompiledEdge(source="b", target="single", target_port="request")]
    with pytest.raises(InputResolutionError, match="ambiguous"):
        InputResolver().resolve(node, edges, {"a": {}, "b": {}})


def test_rehearsal_executes_structured_generator_into_plugin(client):
    _, headers, _ = account(client, "compiled_run")
    workspace = project(client, headers, "Automatic simulation")
    pipeline = client.post(
        f"/projects/{workspace['id']}/pipelines",
        headers=headers,
        json={
            "name": "Automatic generator simulation",
            "nodes": [
                {"id": "design", "type": "experiment_design", "role": "Experimental Designer", "config": {"provider": "openai", "label": "Design reproducible experiment"}},
                {"id": "simulate", "type": "plugin", "config": {"plugin": "core.monte_carlo", "label": "Execute simulation"}},
                {"id": "interpret", "type": "synthesis", "role": "Scientific Researcher", "config": {"provider": "openai", "label": "Interpret uncertainty"}},
            ],
            "edges": [{"source": "design", "target": "simulate", "relation": "produces"}, {"source": "simulate", "target": "interpret", "relation": "informs"}],
        },
    ).json()
    run = client.post(f"/projects/{workspace['id']}/runs", headers=headers, json={"goal": "Run automatically", "pipeline_id": pipeline["id"], "execution_mode": "mock", "use_default_contract": True}).json()
    started = client.post(f"/runs/{run['id']}/execute", headers=headers)
    assert started.status_code == 202, started.text
    for _ in range(80):
        state = client.get(f"/jobs/{started.json()['job_id']}", headers=headers).json()
        if state["status"] in {"completed", "failed"}:
            break
        time.sleep(0.05)
    assert state["status"] == "completed", state.get("error")
    steps = client.get(f"/runs/{run['id']}/steps", headers=headers).json()
    simulation = next(step for step in steps if step["pipeline_node_id"] == "simulate")
    assert simulation["output"]["trials"] >= 100
    assert simulation["output"]["artifact_references"]
    events = client.get(f"/runs/{run['id']}/events", headers=headers).json()
    event_types = {event["event_type"] for event in events}
    assert {"ASSURANCE_CONTRACT_BOUND_TO_RUN", "NODE_CONTEXT_COMPILED", "NODE_INPUTS_RESOLVED", "NODE_OUTPUT_VALIDATED", "DOWNSTREAM_CONTRACT_SATISFIED"} <= event_types
    assurance = client.get(f"/runs/{run['id']}/assurance-status", headers=headers).json()
    assert assurance["bound"] is True


def test_protocol_dependency_edges_point_dependency_to_dependent(client):
    user_id, headers, _ = account(client, "edge_direction")
    workspace = project(client, headers, "Typed protocol")
    run = client.post(f"/projects/{workspace['id']}/runs", headers=headers, json={"goal": "Protocol ingestion", "execution_mode": "mock"}).json()
    payload = {
        "objects": [
            {"id": "claim_external", "type": "claim", "statement": "A", "confidence": 0.4, "provenance": {"execution_mode": "mock"}},
            {"id": "evidence_external", "type": "evidence", "statement": "Check A", "dependencies": ["claim_external"], "reliability": 0.8, "confidence": 0.8, "provenance": {"execution_mode": "mock"}},
        ]
    }
    rows = ProtocolIngestor(client.app.state.repository).ingest(UUID(user_id), workspace["id"], run["id"], json.dumps(payload), {"provider": "mock", "execution_mode": "mock"}, required=True)
    claim = next(item for item in rows if item["type"] == "claim")
    evidence = next(item for item in rows if item["type"] == "evidence")
    graph = client.get(f"/projects/{workspace['id']}/graph", headers=headers).json()
    assert any(edge["source_id"] == claim["id"] and edge["target_id"] == evidence["id"] for edge in graph["edges"])
    passport = client.get(f"/projects/{workspace['id']}/claim-passport", headers=headers).json()
    assert passport["claims"][0]["supporting_evidence"] == 1


def test_counterexample_invalidates_dependent_claims(client):
    user_id, headers, _ = account(client, "counterexample_invalidation")
    workspace = project(client, headers, "Invalidation traversal")
    run = client.post(f"/projects/{workspace['id']}/runs", headers=headers, json={"goal": "Find a counterexample", "execution_mode": "mock"}).json()
    payload = {"objects": [
        {"id": "root", "type": "claim", "statement": "Root claim", "provenance": {"execution_mode": "mock"}},
        {"id": "dependent", "type": "claim", "statement": "Dependent conclusion", "dependencies": ["root"], "provenance": {"execution_mode": "mock"}},
        {"id": "counter", "type": "counterexample", "statement": "A valid counterexample", "dependencies": ["root"], "provenance": {"execution_mode": "mock"}},
    ]}
    ProtocolIngestor(client.app.state.repository).ingest(UUID(user_id), workspace["id"], run["id"], json.dumps(payload), {"provider": "mock", "execution_mode": "mock"}, required=True)
    graph = client.get(f"/projects/{workspace['id']}/graph", headers=headers).json()
    dependent = next(node for node in graph["nodes"] if node["title"] == "Dependent conclusion")
    assert dependent["status"] == "invalidated"
    events = client.get(f"/runs/{run['id']}/events", headers=headers).json()
    assert any(event["event_type"] == "DESCENDANTS_INVALIDATED" for event in events)


def test_multi_output_generator_compiles_every_downstream_contract(client):
    _, headers, _ = account(client, "multi_output")
    workspace = project(client, headers, "Multi-output compilation")
    pipeline = client.post(f"/projects/{workspace['id']}/pipelines", headers=headers, json={
        "name": "Three typed outputs",
        "nodes": [
            {"id": "generator", "type": "experimental_design", "config": {"provider": "openai"}},
            {"id": "simulation", "type": "plugin", "config": {"plugin": "core.monte_carlo"}},
            {"id": "symbolic", "type": "plugin", "config": {"plugin": "core.sympy"}},
            {"id": "review", "type": "independent_review", "config": {"provider": "openai"}},
        ],
        "edges": [{"source": "generator", "target": "simulation"}, {"source": "generator", "target": "symbolic"}, {"source": "generator", "target": "review"}],
    }).json()
    response = client.post(f"/pipelines/{pipeline['id']}/compile?allow_default_contract=true", headers=headers)
    assert response.status_code == 200, response.text
    generator = next(node for node in response.json()["nodes"] if node["id"] == "generator")
    assert set(generator["required_output_ports"]) == {"simulation_request", "symbolic_request", "review_context"}
    assert {item["target_pipeline_node_id"] for item in generator["downstream"]} == {"simulation", "symbolic", "review"}


def test_canonical_messages_are_persisted_with_lineage(client):
    _, headers, _ = account(client, "message_lineage")
    workspace = project(client, headers, "Message lineage")
    pipeline = client.post(f"/projects/{workspace['id']}/pipelines", headers=headers, json={
        "name": "Message pipeline",
        "nodes": [{"id": "design", "type": "experiment_design", "config": {"provider": "openai"}}, {"id": "simulate", "type": "plugin", "config": {"plugin": "core.monte_carlo"}}],
        "edges": [{"source": "design", "target": "simulate"}],
    }).json()
    run = client.post(f"/projects/{workspace['id']}/runs", headers=headers, json={"goal": "Persist messages", "pipeline_id": pipeline["id"], "execution_mode": "mock", "use_default_contract": True}).json()
    started = client.post(f"/runs/{run['id']}/execute", headers=headers).json()
    for _ in range(80):
        state = client.get(f"/jobs/{started['job_id']}", headers=headers).json()
        if state["status"] in {"completed", "failed"}:
            break
        time.sleep(0.05)
    assert state["status"] == "completed", state.get("error")
    messages = client.get(f"/runs/{run['id']}/messages", headers=headers).json()
    output = next(item for item in messages if item["pipeline_node_id"] == "design" and item["direction"] == "output")
    input_message = next(item for item in messages if item["pipeline_node_id"] == "simulate" and item["direction"] == "input")
    assert output["message_id"].startswith("msg_")
    assert input_message["provenance"]["source_message_ids"] == [output["message_id"]]
    assert input_message["data"] == output["data"]
    assert output["provenance"]["assurance_contract_version"] == 1


def test_ollama_unavailable_is_honest(client, monkeypatch):
    _, headers, _ = account(client, "ollama_status")
    import httpx

    def unavailable(*_args, **_kwargs):
        raise httpx.ConnectError("offline")

    monkeypatch.setattr(httpx, "get", unavailable)
    status = client.get("/providers/ollama/status", headers=headers)
    assert status.status_code == 200
    assert status.json()["reachable"] is False
    assert status.json()["running"] is False
    tested = client.post("/providers/ollama/test", headers=headers, json={"model": "qwen3:8b"})
    assert tested.status_code == 503


def test_one_output_port_can_feed_two_compatible_consumers(client):
    _, headers, _ = account(client, "compatible_fanout")
    workspace = project(client, headers, "Compatible fanout")
    schema = {"type": "object", "required": ["value"], "properties": {"value": {"type": "number"}}}
    pipeline = client.post(f"/projects/{workspace['id']}/pipelines", headers=headers, json={
        "name": "Compatible fanout",
        "nodes": [
            {"id": "source", "type": "synthesis", "config": {"provider": "openai"}, "interface": {"output_ports": [{"name": "result", "schema_id": "pico.value.v1", "json_schema": schema}]}},
            {"id": "left", "type": "synthesis", "config": {"provider": "openai"}, "interface": {"input_ports": [{"name": "context", "schema_id": "pico.value.v1", "json_schema": schema}], "output_ports": [{"name": "result"}]}},
            {"id": "right", "type": "synthesis", "config": {"provider": "openai"}, "interface": {"input_ports": [{"name": "context", "schema_id": "pico.value.v1", "json_schema": schema}], "output_ports": [{"name": "result"}]}},
        ],
        "edges": [{"source": "source", "source_port": "result", "target": "left", "target_port": "context"}, {"source": "source", "source_port": "result", "target": "right", "target_port": "context"}],
    }).json()
    response = client.post(f"/pipelines/{pipeline['id']}/compile?allow_default_contract=true", headers=headers)
    assert response.status_code == 200, response.text
    source = next(node for node in response.json()["nodes"] if node["id"] == "source")
    assert set(source["required_output_ports"]) == {"result"}
    assert len(source["downstream"]) == 2


def test_conflicting_consumers_require_an_explicit_adapter(client):
    _, headers, _ = account(client, "conflicting_fanout")
    workspace = project(client, headers, "Conflicting fanout")
    number_schema = {"type": "object", "required": ["value"], "properties": {"value": {"type": "number"}}}
    text_schema = {"type": "object", "required": ["text"], "properties": {"text": {"type": "string"}}}
    pipeline = client.post(f"/projects/{workspace['id']}/pipelines", headers=headers, json={
        "name": "Conflicting fanout",
        "nodes": [
            {"id": "source", "type": "synthesis", "config": {"provider": "openai"}, "interface": {"output_ports": [{"name": "result", "schema_id": "pico.value.v1", "json_schema": number_schema}]}},
            {"id": "number", "type": "synthesis", "config": {"provider": "openai"}, "interface": {"input_ports": [{"name": "context", "schema_id": "pico.value.v1", "json_schema": number_schema}], "output_ports": [{"name": "result"}]}},
            {"id": "text", "type": "synthesis", "config": {"provider": "openai"}, "interface": {"input_ports": [{"name": "context", "schema_id": "pico.text.v1", "json_schema": text_schema}], "output_ports": [{"name": "result"}]}},
        ],
        "edges": [{"source": "source", "source_port": "result", "target": "number", "target_port": "context"}, {"source": "source", "source_port": "result", "target": "text", "target_port": "context"}],
    }).json()
    response = client.post(f"/pipelines/{pipeline['id']}/compile?allow_default_contract=true", headers=headers)
    assert response.status_code == 422
    assert "Incompatible edge" in response.text


def _validation_envelope(output_contracts: dict[str, dict], assurance: dict | None = None) -> NodeExecutionEnvelope:
    return NodeExecutionEnvelope(
        project_id="00000000-0000-0000-0000-000000000001", run_id="00000000-0000-0000-0000-000000000002",
        pipeline_id="00000000-0000-0000-0000-000000000003", pipeline_version=1, pipeline_node_id="generator",
        research_question="What follows?", epistemic_contract={"id": "contract", "version": 1}, node_assurance_requirements=assurance or {},
        node_type="synthesis", node_role="researcher", node_goal="generate", node_instructions="",
        required_output_schema={"type": "object"}, required_output_type="pico.multi_port.v1",
        output_port_contracts=output_contracts, output_port_schema_ids={name: f"pico.{name}.v1" for name in output_contracts},
        budget=ExecutionBudget(), execution_mode="live", provenance_requirements={"no_secret_material": True},
    )


def test_missing_output_port_and_missing_assurance_seed_are_rejected():
    contracts = {
        "simulation": {"type": "object", "required": ["seed", "trials"], "properties": {"seed": {"type": "integer"}, "trials": {"type": "integer"}}},
        "review": {"type": "object", "required": ["summary"], "properties": {"summary": {"type": "string"}}},
    }
    envelope = _validation_envelope(contracts, {"require_seed": True})
    with pytest.raises(OutputValidationError) as rejected:
        OutputValidator().validate_or_repair(envelope, {"execution_mode": "live", "provider": "openai", "content": '{"ports":{"simulation":{"trials":100}}}'})
    assert "simulation: $.seed is required" in rejected.value.errors
    assert "Required output port review is missing" in rejected.value.errors


def test_ollama_adapter_reports_local_zero_cost_semantics(monkeypatch):
    class Response:
        headers = {"x-request-id": "local-request"}

        def raise_for_status(self):
            return None

        def json(self):
            return {"id": "local-request", "choices": [{"message": {"content": '{"status":"ok"}'}}], "usage": {"prompt_tokens": 3, "completion_tokens": 2}}

    monkeypatch.setattr("httpx.post", lambda *_args, **_kwargs: Response())
    provider = OpenAICompatibleProvider("ollama", "http://127.0.0.1:11434/v1", {"127.0.0.1"}, cloud=False)
    result = provider.execute(ProviderRequest(model="llama3.1:8b", messages=[{"role": "user", "content": "Return JSON"}]), None)
    assert result.execution_mode == "local"
    assert result.provider == "ollama"


@pytest.mark.ollama_live
@pytest.mark.skipif(not os.getenv("OLLAMA_LIVE_BASE_URL"), reason="Set OLLAMA_LIVE_BASE_URL to opt into local Ollama execution")
def test_live_ollama_generator_to_monte_carlo(client):
    _, headers, _ = account(client, "ollama_live")
    workspace = project(client, headers, "Live Ollama protocol")
    base_url = os.environ["OLLAMA_LIVE_BASE_URL"]
    model = os.getenv("OLLAMA_LIVE_MODEL", "llama3.1:8b")
    configured = client.post("/providers/ollama/configure", headers=headers, json={"base_url": base_url, "default_model": model})
    assert configured.status_code == 200, configured.text
    tested = client.post("/providers/ollama/test", headers=headers, json={"model": model})
    assert tested.status_code == 200, tested.text
    assert tested.json()["execution_mode"] == "local"
    assert tested.json()["cost_micros"] == 0
    pipeline = client.post(f"/projects/{workspace['id']}/pipelines", headers=headers, json={
        "name": "Live local generator and simulation",
        "nodes": [
            {"id": "design", "type": "experiment_design", "role": "Experimental Designer", "config": {"provider": "ollama", "model": model, "max_tokens": 256}},
            {"id": "simulate", "type": "plugin", "config": {"plugin": "core.monte_carlo"}},
        ],
        "edges": [{"source": "design", "target": "simulate"}],
    }).json()
    run = client.post(f"/projects/{workspace['id']}/runs", headers=headers, json={"goal": "Generate and execute a reproducible simulation", "pipeline_id": pipeline["id"], "execution_mode": "local", "use_default_contract": True}).json()
    started_response = client.post(f"/runs/{run['id']}/execute", headers=headers)
    assert started_response.status_code == 202, started_response.text
    started = started_response.json()
    for _ in range(180):
        state_response = client.get(f"/jobs/{started['job_id']}", headers=headers)
        if state_response.status_code == 429:
            time.sleep(0.5)
            continue
        assert state_response.status_code == 200, state_response.text
        state = state_response.json()
        if state["status"] in {"completed", "failed"}:
            break
        time.sleep(0.5)
    assert state["status"] == "completed", state.get("error")
    steps = client.get(f"/runs/{run['id']}/steps", headers=headers).json()
    design = next(step for step in steps if step["pipeline_node_id"] == "design")
    simulation = next(step for step in steps if step["pipeline_node_id"] == "simulate")
    assert design["output"]["execution_mode"] == "local"
    assert design["output"]["cost_micros"] == 0
    assert simulation["output"]["trials"] >= 100
    messages = client.get(f"/runs/{run['id']}/messages", headers=headers).json()
    source = next(message for message in messages if message["pipeline_node_id"] == "design" and message["direction"] == "output")
    consumed = next(message for message in messages if message["pipeline_node_id"] == "simulate" and message["direction"] == "input")
    assert consumed["provenance"]["source_message_ids"] == [source["message_id"]]

def test_ollama_start_endpoint_reports_backend_local_start(client, monkeypatch):
    _, headers, _ = account(client, "ollama_start")
    from orchestra.providers.ollama_manager import OllamaManager

    monkeypatch.setattr(
        OllamaManager,
        "start_local",
        lambda self: {
            "reachable": True,
            "running": True,
            "installed": True,
            "binary_found": True,
            "models": ["qwen3:8b"],
            "started": True,
            "message": "Ollama started",
        },
    )
    response = client.post("/providers/ollama/start", headers=headers)
    assert response.status_code == 200, response.text
    assert response.json()["reachable"] is True
    assert response.json()["started"] is True
