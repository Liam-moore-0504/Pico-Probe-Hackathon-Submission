ALTER TABLE users ADD COLUMN token_version INTEGER NOT NULL DEFAULT 0;
ALTER TABLE users ADD COLUMN is_admin INTEGER NOT NULL DEFAULT 0;
CREATE TABLE login_attempts(id TEXT PRIMARY KEY, username TEXT NOT NULL, remote_hash TEXT NOT NULL, succeeded INTEGER NOT NULL, created_at TEXT NOT NULL);
CREATE INDEX ix_login_attempts_username_time ON login_attempts(username,created_at);
