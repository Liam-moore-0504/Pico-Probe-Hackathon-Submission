"""Email challenges, password recovery, OAuth PKCE, and account lifecycle."""

from __future__ import annotations

import base64
import hashlib
import secrets
import smtplib
from datetime import UTC, datetime, timedelta
from email.message import EmailMessage
from uuid import UUID, uuid4

import httpx
import jwt

from orchestra.auth.security import hash_password, issue_tokens, verify_password
from orchestra.repositories.repository import Repository, dumps, loads, now

OAUTH = {
    "github": {
        "authorize": "https://github.com/login/oauth/authorize",
        "token": "https://github.com/login/oauth/access_token",
        "userinfo": "https://api.github.com/user",
        "scope": "read:user user:email",
    },
    "google": {
        "authorize": "https://accounts.google.com/o/oauth2/v2/auth",
        "token": "https://oauth2.googleapis.com/token",
        "userinfo": "https://openidconnect.googleapis.com/v1/userinfo",
        "scope": "openid email profile",
    },
    "apple": {"authorize": "https://appleid.apple.com/auth/authorize", "token": "https://appleid.apple.com/auth/token", "userinfo": "", "scope": "name email"},
}


class EmailSender:
    def __init__(self, settings):
        self.settings = settings

    def send(self, recipient: str, subject: str, body: str) -> bool:
        if not self.settings.smtp_host:
            return False
        message = EmailMessage()
        message["From"], message["To"], message["Subject"] = self.settings.email_from, recipient, subject
        message.set_content(body)
        with smtplib.SMTP(self.settings.smtp_host, self.settings.smtp_port, timeout=15) as client:
            client.starttls()
            if self.settings.smtp_username:
                client.login(self.settings.smtp_username, self.settings.smtp_password)
            client.send_message(message)
        return True


class AccountService:
    def __init__(self, repository: Repository, vault, settings):
        self.repo, self.vault, self.settings = repository, vault, settings
        self.email = EmailSender(settings)

    def challenge(self, user_id: str, kind: str, ttl_minutes: int = 30) -> str:
        token = secrets.token_urlsafe(32)
        self.repo.execute(
            "INSERT INTO auth_challenges VALUES(?,?,?,?,?,?,?,?)",
            (str(uuid4()), user_id, kind, hashlib.sha256(token.encode()).hexdigest(), dumps({}), (datetime.now(UTC) + timedelta(minutes=ttl_minutes)).isoformat(), None, now()),
        )
        return token

    def request_verification(self, user_id: str) -> dict:
        user = self.repo.one("SELECT email,email_verified FROM users WHERE id=?", (user_id,))
        if not user or user["email_verified"]:
            return {"status": "already_verified"}
        token = self.challenge(user_id, "email_verification", 1440)
        sent = self.email.send(user["email"], "Verify your Pico Probe email", f"Verify: {self.settings.public_base_url}/?verify_token={token}")
        result = {"status": "sent" if sent else "delivery_not_configured"}
        if self.settings.environment in {"development", "test"}:
            result["development_token"] = token
        return result

    def verify_email(self, token: str) -> dict:
        challenge = self._consume(token, "email_verification")
        self.repo.execute("UPDATE users SET email_verified=1 WHERE id=?", (challenge["user_id"],))
        return {"status": "verified"}

    def request_reset(self, email: str) -> dict:
        user = self.repo.one("SELECT id,email FROM users WHERE email=?", (email.lower(),))
        if user:
            token = self.challenge(user["id"], "password_reset", 30)
            sent = self.email.send(user["email"], "Reset your Pico Probe password", f"Reset: {self.settings.public_base_url}/?reset_token={token}")
            if not sent and self.settings.environment in {"development", "test"}:
                return {"status": "accepted", "development_token": token}
        return {"status": "accepted"}

    def reset_password(self, token: str, password: str) -> dict:
        challenge = self._consume(token, "password_reset")
        with self.repo.database.transaction() as connection:
            connection.execute("UPDATE users SET password_hash=?,token_version=token_version+1 WHERE id=?", (hash_password(password), challenge["user_id"]))
        return {"status": "password_updated"}

    def oauth_start(self, provider: str) -> dict:
        config = self._oauth_config(provider)
        state, verifier, nonce = secrets.token_urlsafe(24), secrets.token_urlsafe(48), secrets.token_urlsafe(24)
        challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip("=")
        self.repo.execute(
            "INSERT INTO auth_challenges VALUES(?,?,?,?,?,?,?,?)",
            (
                str(uuid4()),
                None,
                "oauth_state",
                hashlib.sha256(state.encode()).hexdigest(),
                dumps({"provider": provider, "verifier": verifier, "nonce": nonce}),
                (datetime.now(UTC) + timedelta(minutes=10)).isoformat(),
                None,
                now(),
            ),
        )
        redirect = f"{self.settings.public_base_url}/auth/oauth/{provider}/callback"
        params = {
            "client_id": config["client_id"],
            "redirect_uri": redirect,
            "scope": OAUTH[provider]["scope"],
            "state": state,
            "response_type": "code",
            "code_challenge": challenge,
            "code_challenge_method": "S256",
            "nonce": nonce,
        }
        return {"authorization_url": str(httpx.URL(OAUTH[provider]["authorize"], params=params)), "state_expires_in": 600}

    def oauth_callback(self, provider: str, code: str, state: str) -> dict:
        config = self._oauth_config(provider)
        challenge = self._consume(state, "oauth_state")
        payload = loads(challenge["payload"], {})
        if payload.get("provider") != provider:
            raise ValueError("OAuth provider mismatch")
        redirect = f"{self.settings.public_base_url}/auth/oauth/{provider}/callback"
        response = httpx.post(
            OAUTH[provider]["token"],
            data={
                "client_id": config["client_id"],
                "client_secret": config["client_secret"],
                "code": code,
                "redirect_uri": redirect,
                "grant_type": "authorization_code",
                "code_verifier": payload["verifier"],
            },
            headers={"Accept": "application/json"},
            timeout=20,
        )
        response.raise_for_status()
        token_data = response.json()
        if provider == "apple":
            jwks = jwt.PyJWKClient("https://appleid.apple.com/auth/keys", cache_jwk_set=True, lifespan=3600)
            signing_key = jwks.get_signing_key_from_jwt(token_data["id_token"])
            claims = jwt.decode(
                token_data["id_token"],
                signing_key.key,
                algorithms=["RS256"],
                audience=config["client_id"],
                issuer="https://appleid.apple.com",
                options={"require": ["exp", "iat", "iss", "aud", "sub"]},
            )
            if not secrets.compare_digest(str(claims.get("nonce", "")), payload["nonce"]):
                raise ValueError("Apple OAuth nonce validation failed")
            profile = {"id": claims["sub"], "email": claims.get("email"), "email_verified": claims.get("email_verified", False)}
        else:
            profile_response = httpx.get(OAUTH[provider]["userinfo"], headers={"Authorization": f"Bearer {token_data['access_token']}"}, timeout=20)
            profile_response.raise_for_status()
            profile = profile_response.json()
            if provider == "github":
                emails_response = httpx.get("https://api.github.com/user/emails", headers={"Authorization": f"Bearer {token_data['access_token']}"}, timeout=20)
                emails_response.raise_for_status()
                verified = [item for item in emails_response.json() if item.get("verified") and item.get("email")]
                preferred = next((item for item in verified if item.get("primary")), verified[0] if verified else None)
                profile["email"] = preferred["email"] if preferred else None
                profile["email_verified"] = bool(preferred)
        subject = str(profile.get("sub") or profile.get("id"))
        email = profile.get("email")
        verified_value = profile.get("email_verified")
        email_verified = verified_value is True or str(verified_value).lower() == "true"
        if not subject or not email or not email_verified:
            raise ValueError("OAuth provider did not return a verified identity")
        identity = self.repo.one("SELECT user_id FROM oauth_identities WHERE provider=? AND subject=?", (provider, subject))
        if identity:
            user = self.repo.one("SELECT token_version FROM users WHERE id=?", (identity["user_id"],))
            return issue_tokens(identity["user_id"], user["token_version"], self.settings.jwt_secret)
        user = self.repo.one("SELECT id FROM users WHERE email=?", (email.lower(),))
        user_id = user["id"] if user else str(uuid4())
        with self.repo.database.transaction() as connection:
            if not user:
                stem = f"{provider}_{subject}"[:55]
                username = stem
                suffix = 0
                while connection.execute("SELECT 1 FROM users WHERE username=?", (username,)).fetchone():
                    suffix += 1
                    username = f"{stem}_{suffix}"[:64]
                connection.execute(
                    "INSERT INTO users(id,username,email,password_hash,email_verified,created_at,token_version,is_admin) VALUES(?,?,?,?,?,?,0,0)",
                    (user_id, username, email.lower(), hash_password(secrets.token_urlsafe(32) + "1a"), 1, now()),
                )
            connection.execute("INSERT INTO oauth_identities VALUES(?,?,?,?,?,?)", (str(uuid4()), user_id, provider, subject, email.lower(), now()))
        version = self.repo.one("SELECT token_version FROM users WHERE id=?", (user_id,))["token_version"]
        return issue_tokens(user_id, version, self.settings.jwt_secret)

    def export(self, actor: UUID) -> dict:
        user_id = str(actor)
        return {
            "schema_version": "1.0",
            "user": self.repo.one("SELECT id,username,email,email_verified,created_at FROM users WHERE id=?", (user_id,)),
            "projects": self.repo.all("SELECT * FROM projects WHERE owner_id=?", (user_id,)),
            "memberships": self.repo.all("SELECT * FROM project_members WHERE user_id=?", (user_id,)),
            "credentials": self.repo.all("SELECT provider,status,key_fingerprint,last_used_at,created_at FROM provider_credentials WHERE user_id=?", (user_id,)),
            "ledger": self.repo.all("SELECT * FROM ledger_entries WHERE user_id=?", (user_id,)),
            "security_audit": self.repo.all("SELECT event_type,remote_hash,detail,created_at FROM security_audit WHERE user_id=? ORDER BY created_at", (user_id,)),
        }

    def delete(self, actor: UUID, password: str) -> None:
        user_id = str(actor)
        user = self.repo.one("SELECT username,password_hash FROM users WHERE id=?", (user_id,))
        if not user or not verify_password(password, user["password_hash"]):
            raise ValueError("Password confirmation failed")
        credentials = self.repo.all("SELECT encrypted_key FROM provider_credentials WHERE user_id=?", (user_id,))
        for credential in credentials:
            self.vault.delete(credential["encrypted_key"])
        with self.repo.database.transaction() as connection:
            connection.execute("INSERT INTO security_audit VALUES(?,?,?,?,?,?)", (str(uuid4()), user_id, "account_deleted", None, dumps({}), now()))
            project_ids = [row["id"] for row in connection.execute("SELECT id FROM projects WHERE owner_id=?", (user_id,)).fetchall()]
            for project_id in project_ids:
                connection.execute("DELETE FROM public_snapshots WHERE project_id=?", (project_id,))
                connection.execute("DELETE FROM literature_sources WHERE project_id=?", (project_id,))
                connection.execute("DELETE FROM projects WHERE id=?", (project_id,))
            package_ids = [row["id"] for row in connection.execute("SELECT id FROM plugin_packages WHERE installed_by=?", (user_id,)).fetchall()]
            for package_id in package_ids:
                connection.execute("DELETE FROM plugin_audit WHERE package_id=?", (package_id,))
                connection.execute("DELETE FROM plugin_packages WHERE id=?", (package_id,))
            connection.execute("DELETE FROM plugin_audit WHERE actor_id=?", (user_id,))
            connection.execute("DELETE FROM pricing_rules WHERE created_by=?", (user_id,))
            connection.execute("DELETE FROM invitations WHERE invited_by=?", (user_id,))
            for table in (
                "ledger_entries",
                "credit_reservations",
                "payment_transactions",
                "payment_events",
                "benchmark_runs",
                "provider_credentials",
                "oauth_identities",
                "auth_challenges",
                "project_members",
                "quota_policies",
            ):
                connection.execute(f"DELETE FROM {table} WHERE user_id=?", (user_id,))
            connection.execute("DELETE FROM login_attempts WHERE username=?", (user["username"],))
            connection.execute("DELETE FROM users WHERE id=?", (user_id,))

    def _consume(self, token: str, kind: str) -> dict:
        with self.repo.database.transaction() as connection:
            challenge = connection.execute(
                "SELECT * FROM auth_challenges WHERE token_hash=? AND challenge_type=? AND consumed_at IS NULL",
                (hashlib.sha256(token.encode()).hexdigest(), kind),
            ).fetchone()
            if not challenge or challenge["expires_at"] < now():
                raise ValueError("Challenge is invalid or expired")
            consumed = connection.execute("UPDATE auth_challenges SET consumed_at=? WHERE id=? AND consumed_at IS NULL", (now(), challenge["id"]))
            if consumed.rowcount != 1:
                raise ValueError("Challenge is invalid or expired")
            return dict(challenge)

    def _oauth_config(self, provider: str) -> dict:
        if provider not in OAUTH:
            raise ValueError("Unsupported OAuth provider")
        config = self.settings.oauth_clients[provider]
        if not config.get("client_id") or not config.get("client_secret"):
            raise RuntimeError(f"{provider} OAuth is not configured")
        return config
