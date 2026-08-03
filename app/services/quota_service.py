from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.config.plans import PlanTier, UsageType, get_quota
from app.models import Tenant, UsageEvent


def current_billing_period() -> str:
    now = datetime.now(timezone.utc)
    return f"{now.year:04d}-{now.month:02d}"


def get_period_usage(db: Session, tenant_id: str, usage_type: str, billing_period: str) -> int:
    total = (
        db.query(func.coalesce(func.sum(UsageEvent.quantity), 0))
        .filter(
            UsageEvent.tenant_id == tenant_id,
            UsageEvent.usage_type == usage_type,
            UsageEvent.billing_period == billing_period,
        )
        .scalar()
    )
    return int(total or 0)


def enforce_quota(tenant: Tenant, usage_type: str, current_usage: int, requested_quantity: int) -> int:
    """
    Boundary rule (exact, documented, tested):
      - usage AT the limit is allowed (current_usage + requested <= limit)
      - usage that would go OVER the limit is rejected
      - Free plan over quota -> 402 Payment Required (an upgrade fixes it)
      - Pro plan over quota  -> 429 Too Many Requests (paying more doesn't
        raise a hard usage ceiling; this is a rate/volume limit)

    Returns the plan's limit on success. Raises HTTPException on rejection.
    """
    limit = get_quota(PlanTier(tenant.plan), UsageType(usage_type))
    projected = current_usage + requested_quantity

    if projected <= limit:
        return limit

    if tenant.plan == PlanTier.FREE.value:
        raise HTTPException(
            status_code=402,
            detail={
                "error": "payment_required",
                "message": (
                    f"This request would use {projected} of your Free plan's "
                    f"{limit} monthly {usage_type} quota. Upgrade to Pro to continue."
                ),
                "quota_used": current_usage,
                "quota_limit": limit,
            },
        )

    raise HTTPException(
        status_code=429,
        detail={
            "error": "usage_quota_exceeded",
            "message": (
                f"This request would use {projected} of your Pro plan's "
                f"{limit} monthly {usage_type} quota. Usage limit reached for this billing period."
            ),
            "quota_used": current_usage,
            "quota_limit": limit,
        },
    )
