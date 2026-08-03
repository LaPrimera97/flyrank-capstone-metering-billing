from app.config.plans import PLAN_QUOTAS, PlanTier, UsageType
from app.models import UsageEvent
from app.services import quota_service
from tests.conftest import TestingSessionLocal


def _headers(tenant, key):
    return {"X-API-Key": tenant["api_key"], "Idempotency-Key": key, "Content-Type": "application/json"}


def _bulk_seed_api_calls(tenant_id: str, count: int):
    """
    Insert `count` already-billed api_call usage events directly, bypassing
    the HTTP layer. This is test setup, not the thing under test — the
    behavior under test is always exercised through a real API call at the
    boundary. Doing 100,000 real HTTP round-trips per test would make the
    suite unusably slow without adding any additional coverage.
    """
    period = quota_service.current_billing_period()
    db = TestingSessionLocal()
    try:
        db.bulk_insert_mappings(
            UsageEvent,
            [
                {
                    "id": f"seed-{tenant_id}-{i}",
                    "tenant_id": tenant_id,
                    "idempotency_key": f"seed-key-{i}",
                    "usage_type": "api_call",
                    "quantity": 1,
                    "cost_micros": 1_000,
                    "billing_period": period,
                    "response_snapshot": {},
                }
                for i in range(count)
            ],
        )
        db.commit()
    finally:
        db.close()


def test_request_exactly_at_the_limit_is_allowed(client, free_tenant):
    limit = PLAN_QUOTAS[PlanTier.FREE][UsageType.API_CALL]  # 1000
    _bulk_seed_api_calls(free_tenant["id"], limit - 1)  # 999 already used

    r = client.post(
        "/v1/generate",
        json={"usage_type": "api_call", "quantity": 1},
        headers=_headers(free_tenant, "boundary-call"),
    )
    assert r.status_code == 200

    usage = client.get("/usage", headers={"X-API-Key": free_tenant["api_key"]}).json()
    assert usage["api_calls_used"] == limit


def test_request_one_over_the_limit_is_rejected_with_402_on_free_plan(client, free_tenant):
    limit = PLAN_QUOTAS[PlanTier.FREE][UsageType.API_CALL]
    _bulk_seed_api_calls(free_tenant["id"], limit)  # already at the limit

    r = client.post(
        "/v1/generate",
        json={"usage_type": "api_call", "quantity": 1},
        headers=_headers(free_tenant, "over-the-limit"),
    )
    assert r.status_code == 402
    body = r.json()["detail"]
    assert body["error"] == "payment_required"
    assert "quota_used" in body and "quota_limit" in body


def test_request_over_the_limit_is_rejected_with_429_on_pro_plan(client, pro_tenant):
    limit = PLAN_QUOTAS[PlanTier.PRO][UsageType.API_CALL]
    _bulk_seed_api_calls(pro_tenant["id"], limit)  # already at the limit

    r = client.post(
        "/v1/generate",
        json={"usage_type": "api_call", "quantity": 1},
        headers=_headers(pro_tenant, "over-the-limit-pro"),
    )
    assert r.status_code == 429
    assert r.json()["detail"]["error"] == "usage_quota_exceeded"


def test_request_just_under_the_limit_is_allowed(client, free_tenant):
    limit = PLAN_QUOTAS[PlanTier.FREE][UsageType.API_CALL]
    _bulk_seed_api_calls(free_tenant["id"], limit - 2)  # 998 used, room for one more

    r = client.post(
        "/v1/generate",
        json={"usage_type": "api_call", "quantity": 1},
        headers=_headers(free_tenant, "under-the-limit"),
    )
    assert r.status_code == 200


def test_ai_token_quota_enforced_on_total_tokens(client, free_tenant):
    limit = PLAN_QUOTAS[PlanTier.FREE][UsageType.AI_TOKENS]  # 100,000
    r = client.post(
        "/v1/generate",
        json={
            "usage_type": "ai_tokens",
            "tokens": {
                "input_tokens": limit,
                "cached_input_tokens": 0,
                "output_tokens": 0,
                "reasoning_tokens": 0,
            },
        },
        headers=_headers(free_tenant, "tok-1"),
    )
    assert r.status_code == 200  # exactly at limit -> allowed

    r2 = client.post(
        "/v1/generate",
        json={
            "usage_type": "ai_tokens",
            "tokens": {"input_tokens": 1, "cached_input_tokens": 0, "output_tokens": 0, "reasoning_tokens": 0},
        },
        headers=_headers(free_tenant, "tok-2"),
    )
    assert r2.status_code == 402
