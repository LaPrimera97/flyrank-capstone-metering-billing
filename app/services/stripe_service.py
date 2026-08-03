import stripe
from fastapi import HTTPException
from sqlalchemy.orm import Session
from decimal import Decimal
from app.settings import settings
from app.models import Tenant, WebhookEvent

stripe.api_key = settings.stripe_secret_key


def create_checkout_session(db: Session, tenant: Tenant) -> str:
    """Tenant picks Pro -> Stripe Checkout session -> subscription created on success."""
    if tenant.stripe_customer_id is None:
        customer = stripe.Customer.create(name=tenant.name, metadata={"tenant_id": tenant.id})
        tenant.stripe_customer_id = customer.id
        db.commit()

    session = stripe.checkout.Session.create(
        customer=tenant.stripe_customer_id,
        mode="subscription",
        line_items=[{"price": settings.stripe_pro_price_id, "quantity": 1}],
        success_url=f"{settings.app_base_url}/billing/success?session_id={{CHECKOUT_SESSION_ID}}",
        cancel_url=f"{settings.app_base_url}/billing/cancel",
        metadata={"tenant_id": tenant.id},
    )
    return session.url


def verify_and_parse_event(payload: bytes, sig_header: str) -> dict:
    """Signature verification. A forged/invalid signature must never reach handling logic.
    Returns a plain dict (not a StripeObject) so downstream code has a stable, boring interface."""
    try:
        event = stripe.Webhook.construct_event(payload, sig_header, settings.stripe_webhook_secret)
    except (ValueError, stripe.error.SignatureVerificationError):
        raise HTTPException(status_code=400, detail="Invalid Stripe webhook signature.")
    return event.to_dict()


def is_duplicate_event(db: Session, stripe_event_id: str) -> bool:
    return db.query(WebhookEvent).filter(WebhookEvent.stripe_event_id == stripe_event_id).first() is not None


def _json_safe(value):
    """Stripe payloads can contain Decimal amounts, which Python's default
    JSON encoder can't serialize. Recursively convert them before storing."""
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, dict):
        return {k: _json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_safe(v) for v in value]
    return value


def record_event(db: Session, event: dict) -> None:
    db.add(
        WebhookEvent(
            stripe_event_id=event["id"],
            event_type=event["type"],
            payload=_json_safe(event["data"]["object"]),
        )
    )
    db.commit()


def _tenant_by_customer(db: Session, customer_id: str) -> Tenant | None:
    return db.query(Tenant).filter(Tenant.stripe_customer_id == customer_id).first()


def handle_event(db: Session, event: dict) -> None:
    """
    Payment truth lives at Stripe; our DB mirrors it through verified,
    deduplicated events only. Never trust a client-provided plan change.
    """
    event_type = event["type"]
    obj = event["data"]["object"]

    if event_type == "checkout.session.completed":
        tenant_id = obj.get("metadata", {}).get("tenant_id")
        customer_id = obj.get("customer")
        subscription_id = obj.get("subscription")
        tenant = db.query(Tenant).filter(Tenant.id == tenant_id).first() if tenant_id else _tenant_by_customer(db, customer_id)
        if tenant:
            tenant.plan = "pro"
            tenant.status = "active"
            tenant.stripe_customer_id = customer_id or tenant.stripe_customer_id
            tenant.stripe_subscription_id = subscription_id
            db.commit()

    elif event_type == "customer.subscription.updated":
        customer_id = obj.get("customer")
        tenant = _tenant_by_customer(db, customer_id)
        if tenant:
            status = obj.get("status")  # active | past_due | canceled | ...
            tenant.status = status
            tenant.plan = "pro" if status in ("active", "trialing", "past_due") else "free"
            db.commit()

    elif event_type == "customer.subscription.deleted":
        customer_id = obj.get("customer")
        tenant = _tenant_by_customer(db, customer_id)
        if tenant:
            tenant.plan = "free"
            tenant.status = "canceled"
            tenant.stripe_subscription_id = None
            db.commit()
    # Unrecognized event types are recorded (via record_event) but otherwise ignored.
