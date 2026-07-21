import os

from fastapi.testclient import TestClient

from orchestra.api.main import app


def test_flow():
    client = TestClient(app)
    username = "u" + os.urandom(4).hex()
    email = username + "@example.com"
    password = "password123"
    assert client.post("/auth/register", json={"username": username, "email": email, "password": password}).status_code == 200
    token = client.post("/auth/login", json={"username": username, "password": password}).json()["access_token"]
    headers = {"Authorization": "Bearer " + token}
    project = client.post("/projects", headers=headers, json={"title": "P", "question": "Q"})
    assert project.status_code == 200
    project_id = project.json()["id"]
    claim = client.post(f"/projects/{project_id}/claims", headers=headers, json={"statement": "H", "required_capabilities": ["symbolic_verification"]})
    assert claim.status_code == 200
    claim_id = claim.json()["id"]
    assert client.post(f"/projects/{project_id}/claims/{claim_id}/transition", headers=headers, json={"target_status": "under_test"}).status_code == 200
    assert (
        client.post(f"/projects/{project_id}/dead-ends", headers=headers, json={"approach": "Fourier route", "failure": "Diagonalization", "lesson": "Do not repeat"}).status_code
        == 200
    )
    assert len(client.get("/negative-knowledge/search?q=Fourier", headers=headers).json()) >= 1
