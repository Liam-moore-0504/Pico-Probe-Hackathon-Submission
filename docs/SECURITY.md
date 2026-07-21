# Security

- Passwords use Argon2id. JWT access/refresh tokens use PyJWT with HS256, issuer/audience validation, required claims, rotation IDs, token versions, and revocation.
- Login throttling, Redis-capable API rate limits, trusted-host/CORS allowlists, request-size limits, CSP/frame/MIME/referrer headers, correlation IDs, and security audit records are enabled.
- OAuth uses state, nonce, and PKCE. Apple ID tokens are verified against Apple JWKS; account linking requires a provider-verified email. Reset and verification challenges are hashed, expiring, atomic one-time tokens.
- Credentials are stored through local Fernet, AWS Secrets Manager, GCP Secret Manager, or Azure Key Vault and are never returned or logged. Cloud provider URLs are HTTPS/hostname allowlisted.
- Production startup requires PostgreSQL, Redis, explicit Alembic migration, a non-development JWT secret, explicit hosts/origins, and the Docker sandbox. Third-party plugin containers are non-root, read-only, network-disabled, capability-free, PID/CPU/memory-limited, and `no-new-privileges`.
- Public snapshots are allowlist-built and exclude credentials, billing records, private account data, and unpublished state.

Terminate TLS at a trusted reverse proxy, limit access to the Docker/rootless-container socket, encrypt backups, test restoration, and configure log retention. The local subprocess sandbox is development-only and is rejected in production.
