import uuid

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Tenant, UsageEvent
from app.schemas import GenerateRequest, GenerateResponse
from app.services import pricing_service, quota_service


def _existing_event(db: Session, tenant_id: str, idempotency_key: str) -> UsageEvent | None:
    return (
        db.query(UsageEvent)
        .filter(UsageEvent.tenant_id == tenant_id, UsageEvent.idempotency_key == idempotency_key)
        .first()
    )


def record_usage(db: Session, tenant: Tenant, request: GenerateRequest, idempotency_key: str) -> GenerateResponse:
    """
    Exactly-once metering.

    Same (tenant, idempotency_key) retried -> the ORIGINAL stored response is
    returned, no new usage_event is created, no additional cost is charged.
    This holds even under concurrent retries: a DB-level unique constraint
    is the real guarantee, not just the pre-check below (which closes the
    common case fast and cheaply).
    """
    existing = _existing_event(db, tenant.id, idempotency_key)
    if existing is not None:
        snapshot = dict(existing.response_snapshot)
        snapshot["idempotent_replay"] = True
        return GenerateResponse(**snapshot)

    billing_period = quota_service.current_billing_period()

    if request.usage_type == "api_call":
        billable_quantity = request.quantity
        cost_micros = pricing_service.calculate_api_call_cost_micros(billable_quantity)
    else:
        tokens = request.tokens
        if tokens is None:
            from fastapi import HTTPException
            raise HTTPException(status_code=422, detail="ai_tokens usage requires a 'tokens' breakdown.")
        billable_quantity = pricing_service.total_tokens_for_quota(tokens)
        cost_micros = pricing_service.calculate_token_cost_micros(tokens)

    current_usage = quota_service.get_period_usage(db, tenant.id, request.usage_type, billing_period)
    limit = quota_service.enforce_quota(tenant, request.usage_type, current_usage, billable_quantity)

    event = UsageEvent(
        id=str(uuid.uuid4()),
        tenant_id=tenant.id,
        idempotency_key=idempotency_key,
        usage_type=request.usage_type,
        quantity=billable_quantity,
        token_breakdown=request.tokens.model_dump() if request.tokens else None,
        cost_micros=cost_micros,
        billing_period=billing_period,
    )

    response = GenerateResponse(
        usage_event_id=event.id,
        tenant_id=tenant.id,
        usage_type=request.usage_type,
        billable_quantity=billable_quantity,
        cost_micros=cost_micros,
        cost_usd=pricing_service.micros_to_usd_string(cost_micros),
        quota_used=current_usage + billable_quantity,
        quota_limit=limit,
        idempotent_replay=False,
    )
    event.response_snapshot = response.model_dump()

    db.add(event)
    try:
        db.commit()
    except IntegrityError:
        # Race condition: two identical retried requests hit the unique
        # constraint at the same time. Whoever loses the race just reads
        # back the winner's row — still exactly one usage_event.
        db.rollback()
        existing = _existing_event(db, tenant.id, idempotency_key)
        if existing is None:
            raise
        snapshot = dict(existing.response_snapshot)
        snapshot["idempotent_replay"] = True
        return GenerateResponse(**snapshot)

    return response
