"""
Seed demo data: a Free-plan tenant sitting one call away from its quota
(for the boundary demo) and a fresh Pro-plan tenant.

Run with:  python -m scripts.seed
"""
from app.database import Base, engine, SessionLocal
from app.models import Tenant, UsageEvent
from app.services import quota_service

Base.metadata.create_all(bind=engine)


def run():
    db = SessionLocal()
    try:
        period = quota_service.current_billing_period()

        free_tenant = Tenant(name="Demo Free Co.", plan="free", status="active")
        db.add(free_tenant)
        db.flush()

        # 999 of 1,000 API calls already used — one call from the boundary.
        for i in range(999):
            db.add(
                UsageEvent(
                    tenant_id=free_tenant.id,
                    idempotency_key=f"seed-api-{i}",
                    usage_type="api_call",
                    quantity=1,
                    cost_micros=1_000,
                    billing_period=period,
                    response_snapshot={},
                )
            )

        pro_tenant = Tenant(name="Demo Pro Co.", plan="pro", status="active")
        db.add(pro_tenant)

        db.commit()

        print("Seeded tenants:")
        print(f"  Free tenant (999/1000 API calls used): id={free_tenant.id} api_key={free_tenant.api_key}")
        print(f"  Pro tenant  (fresh):                    id={pro_tenant.id} api_key={pro_tenant.api_key}")
        print("\nTry the boundary:")
        print(f'  curl -X POST localhost:8000/v1/generate -H "X-API-Key: {free_tenant.api_key}" '
              '-H "Idempotency-Key: demo-1" -H "Content-Type: application/json" '
              '-d \'{"usage_type": "api_call", "quantity": 1}\'   # allowed, hits exactly 1000')
        print(f'  curl -X POST localhost:8000/v1/generate -H "X-API-Key: {free_tenant.api_key}" '
              '-H "Idempotency-Key: demo-2" -H "Content-Type: application/json" '
              '-d \'{"usage_type": "api_call", "quantity": 1}\'   # rejected, 402')
    finally:
        db.close()


if __name__ == "__main__":
    run()
