import hashlib
import json

from tests.conftest import account, project


def test_auth_refresh_and_cross_user_isolation(client):
    _, owner, tokens = account(client, "owner")
    _, stranger, _ = account(client, "stranger")
    item = project(client, owner)
    assert client.get(f"/projects/{item['id']}", headers=stranger).status_code == 404
    refreshed = client.post("/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert refreshed.status_code == 200
    assert client.post("/auth/refresh", json={"refresh_token": tokens["refresh_token"]}).status_code == 403
    assert client.get(f"/projects/{item['id']}", headers={"Authorization": "Bearer broken"}).status_code == 401


def test_graph_cycle_claim_evidence_and_invalidation(client):
    _, headers, _ = account(client, "graph")
    item = project(client, headers)
    pid = item["id"]
    first = client.post(f"/projects/{pid}/claims", headers=headers, json={"statement": "Foundational claim"}).json()
    second = client.post(f"/projects/{pid}/claims", headers=headers, json={"statement": "Dependent claim"}).json()
    edge = client.post(f"/projects/{pid}/graph/edges", headers=headers, json={"source_id": second["node_id"], "target_id": first["node_id"], "edge_type": "depends_on"})
    assert edge.status_code == 200, edge.text
    cycle = client.post(f"/projects/{pid}/graph/edges", headers=headers, json={"source_id": first["node_id"], "target_id": second["node_id"], "edge_type": "depends_on"})
    assert cycle.status_code == 422
    guarded = client.post(f"/projects/{pid}/claims/{first['id']}/transition", headers=headers, json={"target_status": "supported"})
    assert guarded.status_code == 422
    assert client.post(f"/projects/{pid}/claims/{first['id']}/transition", headers=headers, json={"target_status": "under_test"}).status_code == 200
    assert client.post(f"/projects/{pid}/claims/{first['id']}/transition", headers=headers, json={"target_status": "tested"}).status_code == 200
    evidence = client.post(
        f"/projects/{pid}/claims/{first['id']}/evidence",
        headers=headers,
        json={"title": "Replication", "evidence_type": "numerical_test", "source": "experiment-a", "reliability": 0.9, "independence_group": "lab-a"},
    )
    assert evidence.status_code == 200, evidence.text
    assert client.post(f"/projects/{pid}/claims/{first['id']}/transition", headers=headers, json={"target_status": "supported"}).status_code == 200
    counterexample = client.post(
        f"/projects/{pid}/claims/{first['id']}/counterexamples", headers=headers, json={"title": "x=0 falsifies it", "source": "skeptic", "reliability": 1.0}
    )
    assert counterexample.status_code == 200
    disproved = client.post(f"/projects/{pid}/claims/{first['id']}/transition", headers=headers, json={"target_status": "disproven"})
    assert disproved.status_code == 200, disproved.text
    graph = client.get(f"/projects/{pid}/graph", headers=headers).json()
    assert next(n for n in graph["nodes"] if n["id"] == second["node_id"])["status"] == "invalidated"
    explanation = client.get(f"/projects/{pid}/claims/{first['id']}/explanation", headers=headers).json()
    assert explanation["confidence"]["disclaimer"]
    assert explanation["contradicting_evidence"]


def test_negative_knowledge_privacy_and_similarity(client):
    _, first, _ = account(client, "dead_one")
    _, second, _ = account(client, "dead_two")
    p1, p2 = project(client, first), project(client, second)
    client.post(
        f"/projects/{p1['id']}/dead-ends",
        headers=first,
        json={"approach": "Fourier diagonal expansion", "method": "spectral diagonalization", "failure": "divergent coefficients", "lesson": "check convergence"},
    )
    assert client.get("/negative-knowledge/search?q=Fourier%20diagonal", headers=second).json() == []
    client.post(
        f"/projects/{p2['id']}/dead-ends",
        headers=second,
        json={"approach": "Fourier diagonal method", "method": "spectral decomposition", "failure": "boundary fails", "lesson": "use compact support"},
    )
    matches = client.get("/negative-knowledge/search?q=Fourier%20diagonal%20spectral", headers=second).json()
    assert len(matches) == 1 and matches[0]["project_id"] == p2["id"]


def test_credentials_are_encrypted_and_never_returned(client):
    _, headers, _ = account(client, "keys")
    secret = "sk-super-secret-value"
    saved = client.post("/user/api-key", headers=headers, json={"provider": "openai", "api_key": secret})
    assert saved.status_code == 200 and secret not in saved.text
    listed = client.get("/user/api-keys", headers=headers)
    assert secret not in listed.text and "encrypted_key" not in listed.text
    database = client.app.state.database
    with database.read() as connection:
        encrypted = connection.execute("SELECT encrypted_key FROM provider_credentials").fetchone()[0]
    assert secret not in encrypted
    assert client.delete("/user/api-key/openai", headers=headers).status_code == 204


def test_pipeline_run_billing_replay_and_snapshot(client):
    _, headers, _ = account(client, "workflow")
    item = project(client, headers)
    pid = item["id"]
    templates = client.get("/pipeline-templates").json()
    assert len(templates) >= 10
    assert any(template["id"] == "independent-route-election" for template in templates)
    pipeline = client.post(f"/pipeline-templates/math-conjecture/instantiate?project_id={pid}", headers=headers)
    assert pipeline.status_code == 200, pipeline.text
    invalid = client.post(
        "/pipelines/validate",
        headers=headers,
        json={"name": "cycle", "nodes": [{"id": "a"}, {"id": "b"}], "edges": [{"source": "a", "target": "b"}, {"source": "b", "target": "a"}]},
    )
    assert invalid.json()["valid"] is False
    run = client.post(f"/projects/{pid}/runs", headers=headers, json={"goal": "Investigate", "pipeline_id": pipeline.json()["id"], "execution_mode": "mock"}).json()
    assert client.post(f"/runs/{run['id']}/start", headers=headers).json()["status"] == "running"
    assert client.post(f"/runs/{run['id']}/pause", headers=headers).json()["status"] == "paused"
    assert client.post(f"/runs/{run['id']}/resume", headers=headers).json()["status"] == "running"
    assert client.post("/billing/test-credits", headers=headers, json={"amount_micros": 10000}).status_code == 200
    reservation = client.post("/billing/reservations", headers=headers, json={"run_id": run["id"], "maximum_micros": 4000}).json()
    settled = client.post(f"/billing/reservations/{reservation['id']}/settle", headers=headers, json={"actual_micros": 1500}).json()
    assert settled["balance_micros"] == 8500 and settled["reserved_micros"] == 0
    client.post(f"/projects/{pid}/claims", headers=headers, json={"statement": "A publishable claim"})
    published = client.post(f"/projects/{pid}/publish", headers=headers).json()
    snapshot_response = client.get(f"/public/snapshots/{published['snapshot_id']}")
    assert snapshot_response.status_code == 200
    snapshot = snapshot_response.json()
    payload = snapshot["payload"]
    serialized = json.dumps(payload)
    assert "provider_credentials" not in serialized and "encrypted_key" not in serialized and "ledger" not in serialized
    assert snapshot["integrity_hash"] == hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    replay = client.get(f"/projects/{pid}/replay", headers=headers).json()
    assert replay["event_count"] >= 8 and replay["chronological"] is True


def test_local_plugins_have_honest_execution_modes(client):
    _, headers, _ = account(client, "plugins")
    item = project(client, headers)
    pid = item["id"]
    symbolic = client.post(f"/projects/{pid}/tools/core.sympy", headers=headers, json={"payload": {"expression": "(x+1)**2-(x**2+2*x+1)", "symbols": ["x"], "action": "simplify"}})
    assert symbolic.status_code == 200 and symbolic.json()["result"] == "0" and symbolic.json()["execution_mode"] == "local"
    lean = client.post(f"/projects/{pid}/tools/core.lean", headers=headers, json={"payload": {"theorem": "theorem t : 1 = 1 := by rfl"}}).json()
    assert (lean["formal"] and lean["verification_status"] in {"compiler_verified", "compiler_rejected"}) or (not lean["formal"] and lean["status"] == "unavailable")
    mock = client.post(f"/projects/{pid}/tools/core.mock_llm", headers=headers, json={"payload": {"prompt": "test"}}).json()
    assert mock["mock"] is True and mock["execution_mode"] == "mock" and mock["output"].startswith("MOCK OUTPUT")
