# Billing design

Balances derive only from append-only ledger entries. Platform-key execution atomically locks available credit, reserves the reviewed worst-case price, settles measured token usage, and releases the remainder. Cancelled calls whose upstream cost is unknown remain reserved as `reconciliation_required` until an administrator records the actual cost. BYOK calls skip provider-token charges.

Pricing rules are versioned by provider, model pattern, effective time, source, currency, cache/input/output rates, and markup. Only active administrator-reviewed rules execute. Global or per-user quotas enforce per-run, monthly, and parallel-run limits.

Stripe Checkout uses test/live credentials supplied by deployment. Webhooks require Stripe signatures and unique event IDs. Payment amount, currency, user, transaction, and credits are cross-checked before credit issuance. Pending, confirmed, failed, verification-failed, partial/full refund, chargeback, and won-dispute restoration states are persisted. Cumulative reversal tracking prevents duplicate partial-refund deductions.
