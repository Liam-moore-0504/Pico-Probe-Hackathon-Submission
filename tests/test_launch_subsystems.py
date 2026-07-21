import json

from orchestra.kernel.scheduler import RunScheduler
from tests.conftest import account, project


def test_invitation_acceptance_revocation_and_branch_compare(client):
    _, owner, _ = account(client, "collab_owner")
    guest_id, guest, _ = account(client, "collab_guest")
    workspace = project(client, owner)
    invitation = client.post(f"/projects/{workspace['id']}/invitations", headers=owner, json={"email": "user_collab_guest@example.com", "role": "editor"})
    assert invitation.status_code == 201, invitation.text
    accepted = client.post("/invitations/accept", headers=guest, json={"token": invitation.json()["token"]})
    assert accepted.status_code == 200
    assert client.get(f"/projects/{workspace['id']}", headers=guest).status_code == 200
    assert client.delete(f"/projects/{workspace['id']}/members/{guest_id}", headers=owner).status_code == 204
    assert client.get(f"/projects/{workspace['id']}", headers=guest).status_code == 404


def test_artifact_policy_and_content_addressing(client):
    _, headers, _ = account(client, "artifacts")
    workspace = project(client, headers)
    response = client.post(f"/projects/{workspace['id']}/artifacts", headers=headers, files={"file": ("result.json", b'{"result":42}', "application/json")})
    assert response.status_code == 201, response.text
    artifact = response.json()
    listing = client.get(f"/projects/{workspace['id']}/artifacts", headers=headers).json()
    assert listing[0]["sha256"] == artifact["sha256"]
    download = client.get(f"/projects/{workspace['id']}/artifacts/{artifact['id']}", headers=headers)
    assert download.content == b'{"result":42}'
    rejected = client.post(f"/projects/{workspace['id']}/artifacts", headers=headers, files={"file": ("bad.exe", b"x", "application/x-msdownload")})
    assert rejected.status_code == 422


def test_plugin_package_checksum_is_enforced(client):
    _, headers, _ = account(client, "marketplace")
    package = b"safe package fixture"
    manifest = {"plugin_id": "fixture.tool", "name": "Fixture", "version": "1.0.0", "capabilities": ["test"], "checksum": "0" * 64}
    response = client.post(
        "/plugin-packages", headers=headers, data={"manifest": json.dumps(manifest), "source": "test"}, files={"package": ("fixture.zip", package, "application/zip")}
    )
    assert response.status_code == 422


def test_scheduler_builds_parallel_dag_levels():
    scheduler = object.__new__(RunScheduler)
    levels = scheduler._levels({"nodes": [{"id": "a"}, {"id": "b"}, {"id": "c"}], "edges": [{"source": "a", "target": "c"}, {"source": "b", "target": "c"}]})
    assert {node["id"] for node in levels[0]} == {"a", "b"}
    assert [node["id"] for node in levels[1]] == ["c"]
