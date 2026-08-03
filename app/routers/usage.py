from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.orm import Session

from app.config.plans import PLAN_QUOTAS, PlanTier, UsageType
from app.database import get_db
from app.dependencies import get_current_tenant
from app.models import Tenant
from app.schemas import GenerateRequest, GenerateResponse, UsageSummaryResponse
from app.services import meter_service, pricing_service, quota_service

router = APIRouter(tags=["usage"])


@router.post("/v1/generate", response_model=GenerateResponse)
def generate(
    body: GenerateRequest,
    idempotency_key: str = Header(..., alias="Idempotency-Key"),
    tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
):
    """
    The one dummy billable endpoint. Records a usage event, enforces quota,
    computes cost. Same Idempotency-Key retried -> exactly one usage event.
    """
    if not idempotency_key.strip():
        raise HTTPException(status_code=422, detail="Idempotency-Key header must not be empty.")
    return meter_service.record_usage(db, tenant, body, idempotency_key)


@router.get("/usage", response_model=UsageSummaryResponse)
def get_usage(
    tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
):
    """Monthly rollup: used / limit / cost per tenant, current billing period."""
    period = quota_service.current_billing_period()

    api_used = quota_service.get_period_usage(db, tenant.id, UsageType.API_CALL.value, period)
    tokens_used = quota_service.get_period_usage(db, tenant.id, UsageType.AI_TOKENS.value, period)

    plan = PlanTier(tenant.plan)
    api_limit = PLAN_QUOTAS[plan][UsageType.API_CALL]
    tokens_limit = PLAN_QUOTAS[plan][UsageType.AI_TOKENS]

    from sqlalchemy import func
    from app.models import UsageEvent
    total_cost = (
        db.query(func.coalesce(func.sum(UsageEvent.cost_micros), 0))
        .filter(UsageEvent.tenant_id == tenant.id, UsageEvent.billing_period == period)
        .scalar()
    )
    total_cost = int(total_cost or 0)

    return UsageSummaryResponse(
        tenant_id=tenant.id,
        plan=tenant.plan,
        billing_period=period,
        api_calls_used=api_used,
        api_calls_limit=api_limit,
        ai_tokens_used=tokens_used,
        ai_tokens_limit=tokens_limit,
        total_cost_micros=total_cost,
        total_cost_usd=pricing_service.micros_to_usd_string(total_cost),
    )
