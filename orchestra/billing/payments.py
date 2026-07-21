"""Stripe Checkout and verified idempotent payment lifecycle."""

from __future__ import annotations

import hashlib
from uuid import UUID, uuid4

import stripe

from orchestra.repositories.repository import Repository, dumps, now


class PaymentService:
    def __init__(self, repository: Repository, secret_key: str, webhook_secret: str, success_url: str, cancel_url: str):
        self.repo = repository
        self.secret_key = secret_key
        self.webhook_secret = webhook_secret
        self.success_url = success_url
        self.cancel_url = cancel_url

    def create_checkout(self, actor: UUID, amount_micros: int) -> dict:
        if not self.secret_key:
            raise RuntimeError("Stripe is not configured")
        if amount_micros < 5_000_000 or amount_micros % 10_000:
            raise ValueError("Checkout amount must be at least $5.00 and use whole cents")
        transaction_id = str(uuid4())
        payment_metadata = {"transaction_id": transaction_id, "user_id": str(actor), "credits_micros": str(amount_micros)}
        session = stripe.checkout.Session.create(
            api_key=self.secret_key,
            mode="payment",
            line_items=[{"price_data": {"currency": "usd", "unit_amount": amount_micros // 10_000, "product_data": {"name": "Orchestra Credits"}}, "quantity": 1}],
            success_url=self.success_url + ("&" if "?" in self.success_url else "?") + "session_id={CHECKOUT_SESSION_ID}",
            cancel_url=self.cancel_url,
            metadata=payment_metadata,
            payment_intent_data={"metadata": payment_metadata},
        )
        self.repo.execute(
            "INSERT INTO payment_transactions(id,user_id,provider,checkout_session_id,payment_intent_id,status,amount_micros,credits_micros,currency,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
            (transaction_id, str(actor), "stripe", session.id, None, "pending", amount_micros, amount_micros, "USD", now(), now()),
        )
        return {"transaction_id": transaction_id, "checkout_session_id": session.id, "checkout_url": session.url, "status": "pending"}

    def webhook(self, payload: bytes, signature: str) -> dict:
        if not self.webhook_secret:
            raise RuntimeError("Stripe webhook verification is not configured")
        event = stripe.Webhook.construct_event(payload, signature, self.webhook_secret)
        event_id = event["id"]
        event_type = event["type"]
        obj = event["data"]["object"]
        metadata = obj.get("metadata", {})
        transaction_id = metadata.get("transaction_id")
        payload_hash = hashlib.sha256(payload).hexdigest()
        with self.repo.database.transaction() as connection:
            transaction = None
            if transaction_id:
                transaction = connection.execute("SELECT * FROM payment_transactions WHERE id=?", (transaction_id,)).fetchone()
            elif obj.get("payment_intent"):
                transaction = connection.execute("SELECT * FROM payment_transactions WHERE payment_intent_id=?", (obj.get("payment_intent"),)).fetchone()
            elif obj.get("charge"):
                transaction = connection.execute("SELECT * FROM payment_transactions WHERE charge_id=?", (obj.get("charge"),)).fetchone()
            elif event_type.startswith("charge.") and obj.get("id"):
                transaction = connection.execute("SELECT * FROM payment_transactions WHERE charge_id=?", (obj.get("id"),)).fetchone()
            supported = {
                "checkout.session.completed",
                "checkout.session.expired",
                "payment_intent.payment_failed",
                "charge.succeeded",
                "charge.refunded",
                "charge.dispute.created",
                "charge.dispute.closed",
            }
            if event_type not in supported or not transaction:
                return {"status": "ignored", "event_id": event_id, "event_type": event_type}
            user_id = transaction["user_id"] if transaction else metadata.get("user_id")
            recorded = connection.execute(
                "INSERT INTO payment_events VALUES(?,?,?,?,?,?) ON CONFLICT(provider_event_id) DO NOTHING",
                (event_id, user_id or "unattributed", event_type, int(metadata.get("credits_micros", 0)), payload_hash, now()),
            )
            if recorded.rowcount != 1:
                return {"status": "duplicate", "event_id": event_id}
            if event_type == "checkout.session.completed" and obj.get("payment_status") == "paid" and transaction_id:
                valid_amount = int(obj.get("amount_total", -1)) * 10_000 == transaction["amount_micros"] if transaction else False
                valid_currency = str(obj.get("currency", "")).upper() == transaction["currency"] if transaction else False
                valid_owner = metadata.get("user_id") == transaction["user_id"] if transaction else False
                valid_credits = int(metadata.get("credits_micros", -1)) == transaction["credits_micros"] if transaction else False
                if transaction and transaction["status"] == "pending" and valid_amount and valid_currency and valid_owner and valid_credits:
                    connection.execute(
                        "UPDATE payment_transactions SET status='confirmed',payment_intent_id=?,updated_at=? WHERE id=?", (obj.get("payment_intent"), now(), transaction_id)
                    )
                    connection.execute(
                        "INSERT INTO ledger_entries VALUES(?,?,?,?,?,?,?,?)",
                        (
                            str(uuid4()),
                            transaction["user_id"],
                            None,
                            "payment_credit",
                            transaction["credits_micros"],
                            "USD",
                            dumps({"transaction_id": transaction_id, "stripe_event_id": event_id}),
                            now(),
                        ),
                    )
                elif transaction and transaction["status"] == "pending":
                    connection.execute("UPDATE payment_transactions SET status='verification_failed',updated_at=? WHERE id=?", (now(), transaction_id))
            elif event_type in {"checkout.session.expired", "payment_intent.payment_failed"} and transaction["status"] == "pending":
                connection.execute("UPDATE payment_transactions SET status='failed',updated_at=? WHERE id=?", (now(), transaction["id"]))
            elif event_type == "charge.succeeded":
                connection.execute(
                    "UPDATE payment_transactions SET charge_id=?,payment_intent_id=COALESCE(payment_intent_id,?),updated_at=? WHERE id=?",
                    (obj.get("id"), obj.get("payment_intent"), now(), transaction["id"]),
                )
            elif event_type in {"charge.refunded", "charge.dispute.created"}:
                if transaction["status"] in {"confirmed", "partially_refunded"}:
                    event_amount_cents = int(obj.get("amount_refunded", 0) if event_type == "charge.refunded" else obj.get("amount", 0))
                    cumulative = min(transaction["credits_micros"], max(0, event_amount_cents * 10_000))
                    reversal = max(0, cumulative - int(transaction.get("reversed_micros", 0))) if isinstance(transaction, dict) else max(0, cumulative - transaction["reversed_micros"])
                    full = cumulative >= transaction["credits_micros"]
                    status = ("refunded" if full else "partially_refunded") if event_type == "charge.refunded" else "chargeback"
                    connection.execute("UPDATE payment_transactions SET status=?,reversed_micros=reversed_micros+?,updated_at=? WHERE id=?", (status, reversal, now(), transaction["id"]))
                    if reversal:
                        connection.execute(
                            "INSERT INTO ledger_entries VALUES(?,?,?,?,?,?,?,?)",
                            (str(uuid4()), transaction["user_id"], None, status, -reversal, "USD", dumps({"transaction_id": transaction["id"], "stripe_event_id": event_id}), now()),
                        )
            elif event_type == "charge.dispute.closed" and obj.get("status") == "won" and transaction["status"] == "chargeback":
                restoration = int(transaction["reversed_micros"])
                connection.execute("UPDATE payment_transactions SET status='confirmed',reversed_micros=0,updated_at=? WHERE id=?", (now(), transaction["id"]))
                if restoration:
                    connection.execute(
                        "INSERT INTO ledger_entries VALUES(?,?,?,?,?,?,?,?)",
                        (str(uuid4()), transaction["user_id"], None, "chargeback_reversed", restoration, "USD", dumps({"transaction_id": transaction["id"], "stripe_event_id": event_id}), now()),
                    )
        return {"status": "processed", "event_id": event_id, "event_type": event_type}
