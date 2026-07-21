ALTER TABLE provider_executions ADD COLUMN idempotency_key TEXT;
CREATE UNIQUE INDEX ix_provider_execution_idempotency ON provider_executions(run_id,idempotency_key);
