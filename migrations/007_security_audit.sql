CREATE TABLE security_audit(id TEXT PRIMARY KEY, user_id TEXT, event_type TEXT NOT NULL, remote_hash TEXT, detail TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE INDEX ix_security_audit_user_time ON security_audit(user_id,created_at);
