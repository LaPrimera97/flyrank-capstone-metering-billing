import hmac
import hashlib
import json
import time

from app.settings import settings


def _sign(payload_bytes: bytes, secret: str, timestamp: int) -> str:
    """Reproduce Stripe's own signing scheme so tests don't need a live Stripe call."""
    signed_payload = f"{timestamp}.{payload_bytes.decode()}"
    signature = hmac.new(secret.encode(), signed_payload.encode(), hashlib.sha256).hexdigest()
    return f"t={timestamp},v1={signature}"


def _stripe_event(event_id: str, event_type: str, obj: dict) -> bytes:
    return json.dumps({
        "id": event_id,
        "object": "event",
        "type": event_type,
        "data": {"object": obj},
    }).encode()


def _post_webhook(client, payload: bytes, header: str):
    return client.post(
        "/webhooks/stripe",
        data=payload,
        headers={"stripe-signature": header, "Content-Type": "application/json"},
    )


def test_forged_signature_is_rejected_with_400_and_nothing_changes(client, free_tenant):
    payload = _stripe_event(
        "evt_forged", "checkout.session.completed",
        {"customer": "cus_fake", "subscription": "sub_fake", "metadata": {"tenant_id": free_tenant["id"]}},
    )
    r = _post_webhook(client, payload, "t=1,v1=not_a_real_signature")
    assert r.status_code == 400

    usage = client.get("/usage", headers={"X-API-Key": free_tenant["api_key"]}).json()
    assert usage["plan"] == "free"  # unchanged


def test_valid_checkout_completed_event_flips_tenant_to_pro(client, free_tenant):
    payload = _stripe_event(
        "evt_checkout_1", "checkout.session.completed",
        {"customer": "cus_123", "subscription": "sub_123", "metadata": {"tenant_id": free_tenant["id"]}},
    )
    header = _sign(payload, settings.stripe_webhook_secret, int(time.time()))
    r = _post_webhook(client, payload, header)
    assert r.status_code == 200
    assert r.json()["status"] == "processed"

    usage = client.get("/usage", headers={"X-API-Key": free_tenant["api_key"]}).json()
    assert usage["plan"] == "pro"
    assert usage["ai_tokens_limit"] > 100_000  # Pro limits kicked in


def test_replayed_event_is_processed_once(client, free_tenant):
    payload = _stripe_event(
        "evt_checkout_2", "checkout.session.completed",
        {"customer": "cus_456", "subscription": "sub_456", "metadata": {"tenant_id": free_tenant["id"]}},
    )
    header = _sign(payload, settings.stripe_webhook_secret, int(time.time()))

    r1 = _post_webhook(client, payload, header)
    assert r1.json()["status"] == "processed"

    r2 = _post_webhook(client, payload, header)
    assert r2.json()["status"] == "duplicate_ignored"

    from tests.conftest import TestingSessionLocal
    from app.models import WebhookEvent
    db = TestingSessionLocal()
    count = db.query(WebhookEvent).filter(WebhookEvent.stripe_event_id == "evt_checkout_2").count()
    db.close()
    assert count == 1


def test_subscription_deleted_event_downgrades_tenant_to_free(client, pro_tenant):
    # First attach a stripe_customer_id the way checkout.session.completed would.
    checkout_payload = _stripe_event(
        "evt_checkout_3", "checkout.session.completed",
        {"customer": "cus_789", "subscription": "sub_789", "metadata": {"tenant_id": pro_tenant["id"]}},
    )
    header = _sign(checkout_payload, settings.stripe_webhook_secret, int(time.time()))
    _post_webhook(client, checkout_payload, header)

    delete_payload = _stripe_event(
        "evt_deleted_1", "customer.subscription.deleted", {"customer": "cus_789"}
    )
    header2 = _sign(delete_payload, settings.stripe_webhook_secret, int(time.time()))
    r = _post_webhook(client, delete_payload, header2)
    assert r.status_code == 200

    usage = client.get("/usage", headers={"X-API-Key": pro_tenant["api_key"]}).json()
    assert usage["plan"] == "free"
