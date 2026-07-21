import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

from orchestra.api.app import create_app
from orchestra.config import Settings


@pytest.fixture
def client(tmp_path):
    config = Settings(
        environment="test",
        database_path=str(tmp_path / "test.db"),
        jwt_secret="x" * 48,
        vault_key=Fernet.generate_key().decode(),
        cors_origins=["http://localhost:5173"],
        plugin_package_path=str(tmp_path / "plugins"),
    )
    with TestClient(create_app(config)) as test_client:
        yield test_client


def account(client, suffix="one"):
    username = "user_" + suffix
    password = "strongpass123"
    response = client.post("/auth/register", json={"username": username, "email": username + "@example.com", "password": password})
    assert response.status_code == 200, response.text
    tokens = client.post("/auth/login", json={"username": username, "password": password}).json()
    return response.json()["user_id"], {"Authorization": "Bearer " + tokens["access_token"]}, tokens


def project(client, headers, title="Research"):
    response = client.post("/projects", headers=headers, json={"title": title, "question": "What is true?"})
    assert response.status_code == 200, response.text
    return response.json()
