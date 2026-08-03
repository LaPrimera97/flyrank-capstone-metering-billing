from fastapi import FastAPI

from app.database import Base, engine
from app.routers import usage, billing, webhooks, tenants

# In a real deployment, schema changes go through Alembic migrations
# (see migrations/). This create_all is a convenience for first boot /
# SQLite test runs and is a no-op once tables already exist.
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Usage Metering & Billing Engine",
    description="Meters usage, enforces quotas, calculates cost, syncs Stripe subscriptions.",
    version="1.0.0",
)

app.include_router(tenants.router)
app.include_router(usage.router)
app.include_router(billing.router)
app.include_router(webhooks.router)


@app.get("/health")
def health():
    return {"status": "ok"}
