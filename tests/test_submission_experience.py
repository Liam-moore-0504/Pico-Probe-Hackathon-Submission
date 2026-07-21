import hashlib
import json
import time

from orchestra.providers import PROVIDERS, ProviderResponse
from tests.conftest import account, project


def test_clean_install_includes_privacy_safe_signed_monomial_public_snapshot(client):
    repository = client.app.state.repository
    assert repository.one("SELECT COUNT(*) AS count FROM projects")["count"] == 0

    projects = client.get("/public/projects")
    assert projects.status_code == 200, projects.text
    showcase = next(item for item in projects.json() if item["id"] == "demo-signed-monomials")
    assert showcase["title"] == "Which monomials survive signed multinomial cancellation?"
    assert showcase["bundled_demo"] is True

    response = client.get(f"/public/snapshots/{showcase['snapshot_id']}")
    assert response.status_code == 200, response.text
    snapshot = response.json()
    payload = snapshot["payload"]
    assert len(payload["graph"]["nodes"]) == 12
    assert len(payload["graph"]["edges"]) == 11
    assert any(node["kind"] == "unexplored_branch" for node in payload["graph"]["nodes"])
    assert any(node["kind"] == "formal_verification" for node in payload["graph"]["nodes"])
    assert any(node["kind"] == "conclusion" for node in payload["graph"]["nodes"])
    encoded = json.dumps(payload, sort_keys=True, default=str, separators=(",", ":"))
    assert snapshot["integrity_hash"] == hashlib.sha256(encoded.encode()).hexdigest()
    assert "e5831e84-a488-46ba-a5e9-c7f5b1364cfc" not in response.text
    assert repository.one("SELECT COUNT(*) AS count FROM projects")["count"] == 0


def test_epistemic_contract_and_claim_passport(client):
    _user_id, headers, _tokens = account(client, "passport")
    investigation = project(client, headers, "Assurance demo")
    project_id = investigation["id"]
    contract = {
        "evidence_standard": "Require directly relevant evidence.",
        "falsification_criteria": "Search for counterexamples and incompatible assumptions.",
        "source_requirements": "Prefer primary sources with stable identifiers.",
        "verification_requirements": "Use an independent deterministic check where applicable.",
        "human_checkpoints": "The researcher approves all material conclusions.",
    }
    saved = client.put(f"/projects/{project_id}/epistemic-contract", headers=headers, json=contract)
    assert saved.status_code == 200, saved.text
    fetched = client.get(f"/projects/{project_id}/epistemic-contract", headers=headers)
    assert fetched.status_code == 200
    assert fetched.json()["content"]["falsification_criteria"] == contract["falsification_criteria"]

    claim = client.post(
        f"/projects/{project_id}/graph/nodes",
        headers=headers,
        json={"kind": "claim", "title": "A testable claim", "content": {"statement": "A testable claim"}, "status": "proposed"},
    ).json()
    check = client.post(
        f"/projects/{project_id}/graph/nodes",
        headers=headers,
        json={"kind": "formal_verification", "title": "Independent check", "content": {"verified": True}, "status": "formally_verified"},
    ).json()
    edge = client.post(
        f"/projects/{project_id}/graph/edges",
        headers=headers,
        json={"source_id": check["id"], "target_id": claim["id"], "edge_type": "verifies"},
    )
    assert edge.status_code == 200, edge.text

    passport = client.get(f"/projects/{project_id}/claim-passport", headers=headers)
    assert passport.status_code == 200, passport.text
    payload = passport.json()
    assert payload["contract"] == contract
    assert payload["assurance"]["total_claims"] == 1
    assert payload["claims"][0]["independent_checks"] == 1
    assert "does not convert model output into truth" in payload["disclaimer"]


def test_openai_byok_key_runs_end_to_end_through_compiled_pipeline(client, monkeypatch):
    """Exercise the real live-mode path without contacting or billing OpenAI."""

    raw_key = "sk-test-picoprobe-end-to-end-not-a-real-key"
    _user_id, headers, _tokens = account(client, "openai_byok_e2e")
    saved = client.post("/user/api-key", headers=headers, json={"provider": "openai", "api_key": raw_key})
    assert saved.status_code == 200, saved.text
    assert raw_key not in saved.text

    provider_calls = []

    class FakeOpenAIProvider:
        async def aexecute(self, request, api_key):
            provider_calls.append({"model": request.model, "api_key": api_key, "messages": request.messages})
            return ProviderResponse(
                provider="openai",
                model=request.model,
                request_id="req_mock_openai_byok_e2e",
                content=json.dumps({"ports": {"result": {"statement": "The mocked transport completed the compiled OpenAI path."}}}),
                usage={"input_tokens": 24, "output_tokens": 12},
                latency_ms=1,
            )

    monkeypatch.setitem(PROVIDERS, "openai", FakeOpenAIProvider)
    investigation = project(client, headers, "OpenAI BYOK end-to-end")
    pipeline_response = client.post(
        f"/projects/{investigation['id']}/pipelines",
        headers=headers,
        json={
            "name": "OpenAI BYOK validation",
            "nodes": [
                {
                    "id": "formalize",
                    "type": "formalization",
                    "role": "Formalizer",
                    "config": {"provider": "openai", "model": "gpt-5.6", "label": "Formalize with GPT-5.6", "stream": False},
                }
            ],
            "edges": [],
        },
    )
    assert pipeline_response.status_code == 200, pipeline_response.text
    pipeline = pipeline_response.json()
    run_response = client.post(
        f"/projects/{investigation['id']}/runs",
        headers=headers,
        json={"goal": "Validate the OpenAI BYOK route", "pipeline_id": pipeline["id"], "execution_mode": "live", "use_default_contract": True},
    )
    assert run_response.status_code == 200, run_response.text
    run = run_response.json()
    started = client.post(f"/runs/{run['id']}/execute", headers=headers)
    assert started.status_code == 202, started.text

    state = None
    for _ in range(80):
        state = client.get(f"/jobs/{started.json()['job_id']}", headers=headers).json()
        if state["status"] in {"completed", "failed"}:
            break
        time.sleep(0.05)
    assert state is not None and state["status"] == "completed", state
    assert len(provider_calls) == 1
    assert provider_calls[0]["api_key"] == raw_key
    assert provider_calls[0]["model"] == "gpt-5.6"
    credential_row = client.app.state.repository.one(
        "SELECT encrypted_key,last_used_at FROM provider_credentials WHERE provider='openai'"
    )
    assert credential_row is not None
    assert raw_key not in credential_row["encrypted_key"]
    assert credential_row["last_used_at"] is not None

    steps = client.get(f"/runs/{run['id']}/steps", headers=headers)
    assert steps.status_code == 200, steps.text
    output = steps.json()[0]["output"]
    assert output["credential_source"] == "byok"
    assert output["validated"] is True
    assert output["model"] == "gpt-5.6"
    assert output["ports"]["result"]["statement"].startswith("The mocked transport")

    messages = client.get(f"/runs/{run['id']}/messages", headers=headers)
    events = client.get(f"/runs/{run['id']}/events", headers=headers)
    replay = client.get(f"/runs/{run['id']}/replay", headers=headers)
    assert messages.status_code == events.status_code == replay.status_code == 200
    serialized_results = json.dumps({"steps": steps.json(), "messages": messages.json(), "events": events.json(), "replay": replay.json()})
    assert raw_key not in serialized_results
    assert "PROVIDER_REQUEST_STARTED" in serialized_results
    assert "PROVIDER_REQUEST_COMPLETED" in serialized_results
