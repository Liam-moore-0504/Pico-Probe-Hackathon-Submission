"""Password hashing and signed access/refresh tokens with rotation identifiers."""

from __future__ import annotations

import base64
import hashlib
import hmac
import os
import re
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import jwt
from cryptography.hazmat.primitives.kdf.argon2 import Argon2id

from orchestra.config import settings


def validate_password(password: str) -> None:
    if len(password) < 10 or len(password) > 256:
        raise ValueError("Password must contain between 10 and 256 characters")
    if not re.search(r"[A-Za-z]", password) or not re.search(r"\d", password):
        raise ValueError("Password must contain a letter and a number")


def hash_password(password: str) -> str:
    validate_password(password)
    salt = os.urandom(16)
    digest = Argon2id(salt=salt, length=32, iterations=3, lanes=4, memory_cost=64 * 1024).derive(password.encode())
    return f"argon2id$3$65536$4${base64.b64encode(salt).decode()}${base64.b64encode(digest).decode()}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        values = encoded.split("$")
        if values[0] == "argon2id" and len(values) == 6:
            _, iterations, memory, lanes, salt, expected = values
            actual = Argon2id(
                salt=base64.b64decode(salt),
                length=32,
                iterations=int(iterations),
                lanes=int(lanes),
                memory_cost=int(memory),
            ).derive(password.encode())
            actual_encoded = base64.b64encode(bytes(actual)).decode()
            return hmac.compare_digest(expected, actual_encoded)
        if values[0] == "pbkdf2_sha256" and len(values) == 4:
            _, rounds, salt, expected = values
            actual = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), int(rounds)).hex()
            return hmac.compare_digest(str(expected), str(actual))
        return False
    except (ValueError, TypeError):
        return False


def issue_tokens(user_id: UUID | str, token_version: int = 0, secret: str | None = None) -> dict:
    now = datetime.now(UTC)
    access_jti, refresh_jti = uuid4().hex, uuid4().hex
    key = secret or settings.jwt_secret
    common = {"sub": str(user_id), "ver": token_version, "iss": "orchestra-ai", "aud": "orchestra-api", "iat": now}
    access = jwt.encode({**common, "type": "access", "jti": access_jti, "exp": now + timedelta(minutes=30)}, key, algorithm="HS256")
    refresh = jwt.encode({**common, "type": "refresh", "jti": refresh_jti, "exp": now + timedelta(days=14)}, key, algorithm="HS256")
    return {"access_token": access, "refresh_token": refresh, "token_type": "bearer", "expires_in": 1800}


def issue_token(user_id: UUID | str, token_version: int = 0, secret: str | None = None) -> str:
    return issue_tokens(user_id, token_version, secret)["access_token"]


def decode_token(token: str, expected_type: str = "access", secret: str | None = None) -> dict | None:
    try:
        payload = jwt.decode(
            token,
            secret or settings.jwt_secret,
            algorithms=["HS256"],
            audience="orchestra-api",
            issuer="orchestra-ai",
            options={"require": ["exp", "iat", "iss", "aud", "sub", "jti", "type"]},
        )
        if payload.get("type") != expected_type:
            return None
        UUID(payload["sub"])
        return payload
    except (jwt.PyJWTError, ValueError, KeyError, TypeError):
        return None


def verify_token(token: str) -> UUID | None:
    payload = decode_token(token)
    return UUID(payload["sub"]) if payload else None
