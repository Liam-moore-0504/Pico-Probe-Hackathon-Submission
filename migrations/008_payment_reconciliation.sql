ALTER TABLE payment_transactions ADD COLUMN charge_id TEXT;
ALTER TABLE payment_transactions ADD COLUMN reversed_micros INTEGER NOT NULL DEFAULT 0;
CREATE INDEX ix_payment_transactions_charge ON payment_transactions(charge_id);
