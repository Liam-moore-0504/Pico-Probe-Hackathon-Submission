def test_email_verification_password_reset_and_token_revocation(client):
    registration = client.post("/auth/register", json={"username": "secure_user", "email": "secure@example.com", "password": "password123"})
    assert registration.status_code == 200
    verification_token = registration.json()["verification"]["development_token"]
    assert client.post("/auth/email/verify", json={"token": verification_token}).json()["status"] == "verified"
    old_tokens = client.post("/auth/login", json={"username": "secure_user", "password": "password123"}).json()
    reset = client.post("/auth/password/forgot", json={"email": "secure@example.com"})
    reset_token = reset.json()["development_token"]
    assert client.post("/auth/password/reset", json={"token": reset_token, "password": "newpassword456"}).status_code == 200
    assert client.get("/projects", headers={"Authorization": "Bearer " + old_tokens["access_token"]}).status_code == 401
    assert client.post("/auth/login", json={"username": "secure_user", "password": "newpassword456"}).status_code == 200


def test_account_export_and_deletion(client):
    registration = client.post("/auth/register", json={"username": "delete_user", "email": "delete@example.com", "password": "password123"}).json()
    tokens = client.post("/auth/login", json={"username": "delete_user", "password": "password123"}).json()
    headers = {"Authorization": "Bearer " + tokens["access_token"]}
    assert client.get("/account/export", headers=headers).json()["user"]["id"] == registration["user_id"]
    assert client.request("DELETE", "/account", headers=headers, json={"password": "password123"}).status_code == 204
    assert client.post("/auth/login", json={"username": "delete_user", "password": "password123"}).status_code == 403
