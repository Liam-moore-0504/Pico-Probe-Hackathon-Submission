"""Validated runtime configuration."""

from __future__ import annotations

import json
import os
from pathlib import Path

from dotenv import load_dotenv
from pydantic import BaseModel, Field, model_validator

load_dotenv()


class Settings(BaseModel):
    environment: str = Field(default_factory=lambda: os.getenv("ORCHESTRA_ENV", "development"))
    database_path: str = Field(default_factory=lambda: os.getenv("ORCHESTRA_DATABASE_PATH", "orchestra_v2.db"))
    database_url: str = Field(default_factory=lambda: os.getenv("ORCHESTRA_DATABASE_URL", ""))
    auto_migrate: bool = Field(default_factory=lambda: os.getenv("ORCHESTRA_AUTO_MIGRATE", "true").lower() == "true")
    redis_url: str = Field(default_factory=lambda: os.getenv("ORCHESTRA_REDIS_URL", ""))
    stripe_secret_key: str = Field(default_factory=lambda: os.getenv("STRIPE_SECRET_KEY", ""))
    stripe_webhook_secret: str = Field(default_factory=lambda: os.getenv("STRIPE_WEBHOOK_SECRET", ""))
    stripe_success_url: str = Field(default_factory=lambda: os.getenv("STRIPE_SUCCESS_URL", "http://127.0.0.1:8000/?payment=success"))
    stripe_cancel_url: str = Field(default_factory=lambda: os.getenv("STRIPE_CANCEL_URL", "http://127.0.0.1:8000/?payment=cancelled"))
    public_base_url: str = Field(default_factory=lambda: os.getenv("ORCHESTRA_PUBLIC_BASE_URL", "http://127.0.0.1:8000"))
    smtp_host: str = Field(default_factory=lambda: os.getenv("SMTP_HOST", ""))
    smtp_port: int = Field(default_factory=lambda: int(os.getenv("SMTP_PORT", "587")))
    smtp_username: str = Field(default_factory=lambda: os.getenv("SMTP_USERNAME", ""))
    smtp_password: str = Field(default_factory=lambda: os.getenv("SMTP_PASSWORD", ""))
    email_from: str = Field(default_factory=lambda: os.getenv("EMAIL_FROM", "noreply@picoprobe.local"))
    oauth_clients: dict[str, dict[str, str]] = Field(
        default_factory=lambda: {
            provider: {"client_id": os.getenv(f"{prefix}_CLIENT_ID", ""), "client_secret": os.getenv(f"{prefix}_CLIENT_SECRET", "")}
            for provider, prefix in {"github": "GITHUB_OAUTH", "google": "GOOGLE_OAUTH", "apple": "APPLE_OAUTH"}.items()
        }
    )
    admin_emails: set[str] = Field(default_factory=lambda: {email.strip().lower() for email in os.getenv("ORCHESTRA_ADMIN_EMAILS", "").split(",") if email.strip()})
    jwt_secret: str = Field(default_factory=lambda: os.getenv("ORCHESTRA_JWT_SECRET", "picoprobe-development-only-secret-change-me"))
    vault_key: str = Field(default_factory=lambda: os.getenv("ORCHESTRA_VAULT_KEY", ""))
    secret_backend: str = Field(default_factory=lambda: os.getenv("ORCHESTRA_SECRET_BACKEND", "local"))
    secret_prefix: str = Field(default_factory=lambda: os.getenv("ORCHESTRA_SECRET_PREFIX", "orchestra"))
    sandbox_backend: str = Field(default_factory=lambda: os.getenv("ORCHESTRA_SANDBOX_BACKEND", "subprocess"))
    sandbox_python_image: str = Field(default_factory=lambda: os.getenv("ORCHESTRA_SANDBOX_PYTHON_IMAGE", "python:3.13-slim"))
    plugin_package_path: str = Field(default_factory=lambda: os.getenv("ORCHESTRA_PLUGIN_PACKAGE_PATH", "orchestra_plugin_packages"))
    aws_region: str = Field(default_factory=lambda: os.getenv("AWS_REGION", ""))
    gcp_project_id: str = Field(default_factory=lambda: os.getenv("GCP_PROJECT_ID", ""))
    azure_key_vault_url: str = Field(default_factory=lambda: os.getenv("AZURE_KEY_VAULT_URL", ""))
    cors_origins: list[str] = Field(default_factory=lambda: [x for x in os.getenv("ORCHESTRA_CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",") if x])
    allowed_hosts: list[str] = Field(default_factory=lambda: [x for x in os.getenv("ORCHESTRA_ALLOWED_HOSTS", "localhost,127.0.0.1,testserver").split(",") if x])
    max_request_bytes: int = Field(default_factory=lambda: int(os.getenv("ORCHESTRA_MAX_REQUEST_BYTES", "1048576")))
    rate_limit_per_minute: int = Field(default_factory=lambda: int(os.getenv("ORCHESTRA_RATE_LIMIT_PER_MINUTE", "120")))
    auth_rate_limit_per_minute: int = Field(default_factory=lambda: int(os.getenv("ORCHESTRA_AUTH_RATE_LIMIT_PER_MINUTE", "20")))
    platform_keys: dict[str, str] = Field(
        default_factory=lambda: {
            name: value
            for name, value in {
                "openai": os.getenv("OPENAI_API_KEY", ""),
                "anthropic": os.getenv("ANTHROPIC_API_KEY", ""),
                "google": os.getenv("GOOGLE_API_KEY", ""),
                "deepseek": os.getenv("DEEPSEEK_API_KEY", ""),
                "xai": os.getenv("XAI_API_KEY", ""),
            }.items()
            if value
        }
    )
    generic_provider_endpoints: dict[str, str] = Field(default_factory=lambda: json.loads(os.getenv("ORCHESTRA_GENERIC_PROVIDER_ENDPOINTS", "{}")))

    @model_validator(mode="after")
    def validate_production(self) -> Settings:
        if self.environment == "production":
            if self.jwt_secret in {"development-only-change-me", "picoprobe-development-only-secret-change-me", "replace-with-a-long-random-secret"} or len(self.jwt_secret) < 32:
                raise ValueError("Production requires ORCHESTRA_JWT_SECRET with at least 32 characters")
            if self.secret_backend == "local" and not self.vault_key:
                raise ValueError("Production local secret backend requires ORCHESTRA_VAULT_KEY")
            if self.sandbox_backend != "docker":
                raise ValueError("Production requires ORCHESTRA_SANDBOX_BACKEND=docker")
            if not self.database_url.startswith(("postgresql://", "postgresql+psycopg://")):
                raise ValueError("Production requires a PostgreSQL ORCHESTRA_DATABASE_URL")
            if self.auto_migrate:
                raise ValueError("Production requires ORCHESTRA_AUTO_MIGRATE=false and an explicit Alembic deployment step")
            if not self.redis_url.startswith(("redis://", "rediss://")):
                raise ValueError("Production requires ORCHESTRA_REDIS_URL")
            if "*" in self.cors_origins or "*" in self.allowed_hosts:
                raise ValueError("Production CORS origins and allowed hosts must be explicit")
            if self.secret_backend == "gcp" and not self.gcp_project_id:
                raise ValueError("GCP secret storage requires GCP_PROJECT_ID")
            if self.secret_backend == "azure" and not self.azure_key_vault_url.startswith("https://"):
                raise ValueError("Azure secret storage requires an HTTPS AZURE_KEY_VAULT_URL")
        return self


settings = Settings()


def ensure_parent(path: str) -> None:
    Path(path).expanduser().parent.mkdir(parents=True, exist_ok=True)
