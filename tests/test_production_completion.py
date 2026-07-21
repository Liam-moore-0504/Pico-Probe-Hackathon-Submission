import asyncio
import base64
import hashlib
import io
import json
import time
import zipfile
from types import SimpleNamespace
from uuid import UUID, uuid4

import stripe
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from orchestra.billing import BillingPolicyService
from orchestra.billing.payments import PaymentService
from orchestra.kernel.provider_executor import ProviderExecutor
from orchestra.providers import PROVIDERS, ProviderResponse
from orchestra.repositories.repository import now
from tests.conftest import account, project


def test_platform_provider_execution_settles_usage_and_ingests_typed_claim(client, monkeypatch):
    user_id, headers, _ = account(client, "provider_billing")
    workspace = project(client, headers)
    actor = UUID(user_id)
    service = client.app.state.service
    run = service.create_run(actor, workspace["id"], {"goal": "test", "execution_mode": "mock"})
    service.add_credits(actor, 1_000_000)
    repo = client.app.state.repository
    repo.execute(
        "INSERT INTO pricing_rules VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (str(uuid4()), "openai", "test-model", 1_000_000, 2_000_000, 0, "USD", now(), 0, "test fixture", 1, user_id, now()),
    )
    typed = {
        "objects": [
            {
                "id": "claim-a",
                "type": "claim",
                "statement": "The fixture claim is true.",
                "confidence": 0.25,
                "provenance": {"execution_mode": "live"},
            }
        ]
    }

    class FakeProvider:
        async def aexecute(self, request, api_key):
            assert api_key == "platform-test-key"
            return ProviderResponse(provider="openai", model=request.model, content=json.dumps(typed), usage={"input_tokens": 10, "output_tokens": 5}, latency_ms=2)

    monkeypatch.setitem(PROVIDERS, "openai", FakeProvider)
    executor = ProviderExecutor(repo, service, BillingPolicyService(repo), {"openai": "platform-test-key"})
    result = asyncio.run(
        executor.execute(
            actor,
            workspace["id"],
            run["id"],
            {"provider": "openai", "model": "test-model", "prompt": "fixture", "max_tokens": 100, "require_typed_output": True},
            "live",
        )
    )
    assert result["cost_micros"] == 20
    assert result["typed_objects"][0]["statement"] == "The fixture claim is true."
    assert service.balance(actor)["balance_micros"] == 999_980
    execution = repo.one("SELECT * FROM provider_executions WHERE id=?", (result["execution_id"],))
    assert execution["status"] == "completed" and execution["credential_source"] == "platform"
    assert repo.one("SELECT statement FROM claims WHERE node_id=?", (result["typed_objects"][0]["id"],))["statement"] == "The fixture claim is true."


def test_signed_marketplace_package_requires_admin_approval_and_executes_sandboxed(client):
    user_id, headers, _ = account(client, "publisher")
    client.app.state.repository.execute("UPDATE users SET is_admin=1 WHERE id=?", (user_id,))
    source = b"def execute(payload):\n    return {'status': 'completed', 'answer': payload['value'] * 2}\n"
    package_buffer = io.BytesIO()
    with zipfile.ZipFile(package_buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("plugin.py", source)
    package = package_buffer.getvalue()
    digest = hashlib.sha256(package).hexdigest()
    private_key = Ed25519PrivateKey.generate()
    public_key = private_key.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    signature = private_key.sign(f"fixture.signed\n1.0.0\n{digest}".encode())
    manifest = {
        "plugin_id": "fixture.signed",
        "name": "Signed fixture",
        "version": "1.0.0",
        "checksum": digest,
        "sandbox_required": True,
        "signature_algorithm": "ed25519",
        "publisher_public_key": base64.b64encode(public_key).decode(),
        "signature": base64.b64encode(signature).decode(),
    }
    installed = client.post(
        "/plugin-packages",
        headers=headers,
        data={"manifest": json.dumps(manifest), "source": "test"},
        files={"package": ("fixture.zip", package, "application/zip")},
    )
    assert installed.status_code == 201, installed.text
    package_id = installed.json()["id"]
    assert client.post(f"/admin/plugin-packages/{package_id}/approve", headers=headers).status_code == 200
    assert client.put(f"/admin/plugin-packages/{package_id}/state", headers=headers, json={"enabled": True}).status_code == 200
    workspace = project(client, headers, "Plugin sandbox")
    result = client.post(f"/projects/{workspace['id']}/tools/fixture.signed", headers=headers, json={"payload": {"value": 21}})
    assert result.status_code == 200, result.text
    assert result.json()["answer"] == 42
    assert result.json()["sandbox"] == "best_effort_local_subprocess"


def test_stripe_verified_checkout_idempotence_and_partial_refund(client, monkeypatch):
    user_id, _, _ = account(client, "stripe_user")
    actor = UUID(user_id)
    repo = client.app.state.repository
    monkeypatch.setattr(stripe.checkout.Session, "create", lambda **kwargs: SimpleNamespace(id="cs_test", url="https://checkout.stripe.test/session"))
    payments = PaymentService(repo, "sk_test_fixture", "whsec_fixture", "https://app.test/payment?ok=1", "https://app.test/payment?cancel=1")
    checkout = payments.create_checkout(actor, 5_000_000)
    completed = {
        "id": "evt_paid",
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "payment_status": "paid",
                "payment_intent": "pi_fixture",
                "amount_total": 500,
                "currency": "usd",
                "metadata": {"transaction_id": checkout["transaction_id"], "user_id": user_id, "credits_micros": "5000000"},
            }
        },
    }
    monkeypatch.setattr(stripe.Webhook, "construct_event", lambda payload, signature, secret: completed)
    assert payments.webhook(b"paid", "valid")["status"] == "processed"
    assert payments.webhook(b"paid", "valid")["status"] == "duplicate"
    refunded = {"id": "evt_refund", "type": "charge.refunded", "data": {"object": {"payment_intent": "pi_fixture", "amount_refunded": 250, "metadata": {}}}}
    monkeypatch.setattr(stripe.Webhook, "construct_event", lambda payload, signature, secret: refunded)
    assert payments.webhook(b"refund", "valid")["status"] == "processed"
    balance = repo.one("SELECT SUM(amount_micros) amount FROM ledger_entries WHERE user_id=?", (user_id,))["amount"]
    assert balance == 2_500_000
    assert repo.one("SELECT status FROM payment_transactions WHERE id=?", (checkout["transaction_id"],))["status"] == "partially_refunded"


def test_branch_merge_copies_authoritative_claim_and_applies_resolution(client):
    _, headers, _ = account(client, "merge_claim")
    workspace = project(client, headers)
    claim = client.post(f"/projects/{workspace['id']}/claims", headers=headers, json={"statement": "Original branch claim"}).json()
    repo = client.app.state.repository
    main_id = repo.one("SELECT id FROM branches WHERE project_id=? AND name='main'", (workspace["id"],))["id"]
    branch = client.post(f"/projects/{workspace['id']}/branches", headers=headers, json={"name": "alternative", "parent_id": main_id}).json()
    source_graph = client.get(f"/projects/{workspace['id']}/graph?branch_id={branch['id']}", headers=headers).json()
    source_node = next(node for node in source_graph["nodes"] if node["title"] == "Original branch claim")
    assert repo.one("SELECT id FROM claims WHERE node_id=?", (source_node["id"],))
    patched = client.patch(
        f"/projects/{workspace['id']}/graph/nodes/{source_node['id']}",
        headers=headers,
        json={"content": {"branch_result": "source wins"}},
    )
    assert patched.status_code == 200
    proposal = client.post(
        f"/projects/{workspace['id']}/merges",
        headers=headers,
        json={"source_branch_id": branch["id"], "target_branch_id": main_id},
    ).json()
    assert proposal["status"] == "conflicted"
    resolved = client.post(f"/merges/{proposal['id']}/resolve", headers=headers, json={"resolutions": {claim["statement"]: "source"}})
    assert resolved.status_code == 200, resolved.text
    main_graph = client.get(f"/projects/{workspace['id']}/graph?branch_id={main_id}", headers=headers).json()
    merged = next(node for node in main_graph["nodes"] if node["title"] == claim["statement"])
    assert merged["content"] == {"branch_result": "source wins"}


def test_human_gate_resumes_from_checkpoint_and_benchmark_is_derived(client):
    _, headers, _ = account(client, "human_gate")
    workspace = project(client, headers)
    pipeline = client.post(
        f"/projects/{workspace['id']}/pipelines",
        headers=headers,
        json={
            "name": "Human checkpoint",
            "nodes": [
                {"id": "prepare", "type": "model", "config": {"prompt": "prepare"}},
                {"id": "approve", "type": "human_review", "config": {"human_input": True}},
                {"id": "finish", "type": "model", "config": {"prompt": "finish"}},
            ],
            "edges": [{"source": "prepare", "target": "approve"}, {"source": "approve", "target": "finish"}],
        },
    )
    assert pipeline.status_code == 200, pipeline.text
    run = client.post(
        f"/projects/{workspace['id']}/runs",
        headers=headers,
        json={"goal": "Review the checkpoint", "pipeline_id": pipeline.json()["id"], "execution_mode": "mock"},
    ).json()
    job = client.post(f"/runs/{run['id']}/execute", headers=headers).json()
    state = None
    for _ in range(40):
        state = client.get(f"/jobs/{job['job_id']}", headers=headers).json()
        if state["status"] == "waiting_for_user":
            break
        time.sleep(0.05)
    assert state["status"] == "waiting_for_user"
    resumed = client.post(f"/runs/{run['id']}/human-input", headers=headers, json={"pipeline_node_id": "approve", "payload": {"summary": "Researcher conclusion", "content": "The independently checked conclusion.", "contribution_type": "claim", "confidence": 0.8}})
    assert resumed.status_code == 202, resumed.text
    for _ in range(40):
        state = client.get(f"/jobs/{job['job_id']}", headers=headers).json()
        if state["status"] == "completed":
            break
        time.sleep(0.05)
    assert state["status"] == "completed"
    graph = client.get(f"/projects/{workspace['id']}/graph", headers=headers).json()
    human_claim = next(node for node in graph["nodes"] if node["title"] == "Researcher conclusion")
    assert human_claim["kind"] == "claim"
    passport = client.get(f"/projects/{workspace['id']}/claim-passport", headers=headers).json()
    assert any(claim["statement"] == "The independently checked conclusion." for claim in passport["claims"])
    benchmark = client.post(
        "/benchmarks/execute",
        headers=headers,
        json={"task_id": "symbolic-counterexample-v1", "mode": "orchestra", "run_id": run["id"]},
    )
    assert benchmark.status_code == 201, benchmark.text
    metrics = benchmark.json()["metrics"]
    assert metrics["measurement_source"] == "persisted_run"
    assert metrics["source_run_id"] == run["id"]
    assert metrics["human_interventions"] == 1
