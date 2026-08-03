import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Column, String, Integer, DateTime, ForeignKey, UniqueConstraint, JSON, Index
)
from sqlalchemy.orm import relationship

from app.database import Base


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Tenant(Base):
    """One customer organization. All usage/subscription data is scoped to a tenant."""
    __tablename__ = "tenants"

    id = Column(String, primary_key=True, default=_uuid)
    name = Column(String, nullable=False)
    api_key = Column(String, unique=True, nullable=False, default=_uuid)

    plan = Column(String, nullable=False, default="free")          # free | pro
    status = Column(String, nullable=False, default="active")      # active | past_due | canceled

    stripe_customer_id = Column(String, unique=True, nullable=True)
    stripe_subscription_id = Column(String, unique=True, nullable=True)

    created_at = Column(DateTime(timezone=True), default=_now)

    usage_events = relationship("UsageEvent", back_populates="tenant")


class UsageEvent(Base):
    """
    One recorded row of billable activity.

    Exactly-once guarantee: (tenant_id, idempotency_key) is unique. A retried
    request with the same key hits this constraint and the API returns the
    original stored response instead of creating a new row.
    """
    __tablename__ = "usage_events"
    __table_args__ = (
        UniqueConstraint("tenant_id", "idempotency_key", name="uq_tenant_idempotency_key"),
        Index("ix_usage_events_tenant_period", "tenant_id", "billing_period"),
    )

    id = Column(String, primary_key=True, default=_uuid)
    tenant_id = Column(String, ForeignKey("tenants.id"), nullable=False)
    idempotency_key = Column(String, nullable=False)

    usage_type = Column(String, nullable=False)   # api_call | ai_tokens
    quantity = Column(Integer, nullable=False)     # billable units (calls, or total billable tokens)
    token_breakdown = Column(JSON, nullable=True)  # {input, cached_input, output, reasoning} for ai_tokens

    cost_micros = Column(Integer, nullable=False, default=0)  # integer microdollars, never float

    # billing_period = "YYYY-MM", the calendar month this event counts against
    billing_period = Column(String, nullable=False)

    # snapshot of the API response returned for this event, so a retried
    # request can be mirrored byte-for-byte without recomputation.
    response_snapshot = Column(JSON, nullable=True)

    created_at = Column(DateTime(timezone=True), default=_now)

    tenant = relationship("Tenant", back_populates="usage_events")


class WebhookEvent(Base):
    """
    Every processed Stripe webhook event, keyed by Stripe's own event id.
    Prevents double-processing when Stripe (correctly) retries delivery.
    """
    __tablename__ = "webhook_events"

    id = Column(String, primary_key=True, default=_uuid)
    stripe_event_id = Column(String, unique=True, nullable=False)
    event_type = Column(String, nullable=False)
    payload = Column(JSON, nullable=True)
    processed_at = Column(DateTime(timezone=True), default=_now)
