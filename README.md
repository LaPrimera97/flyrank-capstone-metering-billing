# Usage Metering & Billing Engine

FlyRank Internship · Backend Track · Capstone

A backend service that meters usage, enforces subscription quotas, calculates
AI-token cost with real-world pricing rules, and syncs subscription state from
Stripe (test mode) via signature-verified, deduplicated webhooks.

Built with **Python + FastAPI + PostgreSQL + Stripe test mode**.

## What it does

Every SaaS needs to answer three questions for every customer, every month:

1. **How much have they used?** → `POST /v1/generate` records a usage event,
   idempotently.
2. **What does it cost?** → integer microdollar math, with the AI-token
   pricing rules (cached input is cheaper, reasoning tokens bill as output).
3. **Have they hit their limit?** → quota is checked before the action is
   allowed; `402` (Free plan, upgrade fixes it) vs `429` (Pro plan, hard
   usage ceiling) are both honest, distinct answers.

## Architecture

```
Client ─► POST /v1/generate (Idempotency-Key, X-API-Key)
  │
  ▼
dependencies.get_current_tenant  ── resolves tenant from API key (401 if invalid)
  │
  ▼
services.meter_service.record_usage
  ├─ existing usage_event for (tenant, idempotency_key)?
  │     └─ YES → return the ORIGINAL stored response, no new row (idempotent replay)
  │
  ├─ services.pricing_service   → billable_quantity + cost_micros
  ├─ services.quota_service     → current period usage, enforce_quota()
  │     └─ over limit? → 402 (Free) or 429 (Pro), never reaches DB write
  │
  └─ INSERT usage_event (tenant_id, idempotency_key) UNIQUE constraint
        └─ race condition (two retries at once)? → IntegrityError caught,
           re-read the winning row, return ITS response. Still exactly one row.

GET /usage ── rollup(usage_events for this tenant + billing period) → used/limit/cost

POST /billing/checkout ── creates a Stripe Checkout session (test mode) → returns URL

POST /webhooks/stripe
  ├─ verify signature (stripe-signature header)  → forged → 400, nothing changes
  ├─ dedupe on Stripe's event id (webhook_events table) → replay → ignored
  └─ apply event → update tenant.plan / tenant.status (payment truth lives at Stripe)
```

**Layers:** `routers/` (HTTP only) → `services/` (business logic) →
`models.py` + SQLAlchemy (persistence). Swapping Postgres for another
database, or Stripe for another payment provider, touches `database.py` /
`stripe_service.py` only — never the routers.

## Data model

- **tenants** — one row per customer. `plan` (free/pro), `status`,
  `stripe_customer_id`, `stripe_subscription_id`, `api_key`.
- **usage_events** — one row per billable action. `UNIQUE(tenant_id,
  idempotency_key)` is the exactly-once guarantee. Stores a
  `response_snapshot` so retries mirror the original response exactly.
- **webhook_events** — one row per processed Stripe event, keyed by Stripe's
  own event id, for replay protection.

## Quotas & pricing (pinned, see `app/config/plans.py`)

| Plan | API calls / month | AI tokens / month |
|------|-------------------|--------------------|
| Free | 1,000             | 100,000            |
| Pro  | 100,000           | 10,000,000         |

Token pricing (per 1,000,000 tokens): input $3.00, cached input $0.75,
output $15.00. **Reasoning tokens bill at the output rate** — they are not a
separate discounted category, and they're never dropped. All money is
stored and computed as **integer microdollars** (1 microdollar = $0.000001)
— no floats touch a cost value anywhere in the codebase. See
`tests/test_pricing.py` for the pinned expected values.

## Quickstart (GitHub Codespaces — no local install needed)

1. Push this repo to your own GitHub account.
2. On the repo page: **Code → Codespaces → Create codespace on main.**
   The devcontainer installs Python deps and the Stripe CLI automatically.
3. In the Codespace terminal:
   ```bash
   cp .env.example .env
   docker compose up -d db          # starts Postgres
   alembic upgrade head             # creates tables
   uvicorn app.main:app --reload    # starts the API on :8000
   ```
4. In a second terminal tab, forward Stripe webhooks:
   ```bash
   stripe login
   stripe listen --forward-to localhost:8000/webhooks/stripe
   # paste the printed whsec_... into .env as STRIPE_WEBHOOK_SECRET, restart uvicorn
   ```
5. Seed demo data and run the tests:
   ```bash
   python -m scripts.seed
   pytest -v
   ```

### Quickstart (local machine with Docker)

Same steps as above, run in your own terminal instead of a Codespace.

### Running the whole stack in Docker

```bash
docker compose up --build
```

## API surface

| Method | Path | Purpose |
|---|---|---|
| POST | `/tenants` | Create a tenant, get back an API key |
| POST | `/v1/generate` | The billable action — requires `X-API-Key` + `Idempotency-Key` headers |
| GET | `/usage` | Monthly rollup: used / limit / cost |
| POST | `/billing/checkout` | Create a Stripe test-mode Checkout session |
| POST | `/webhooks/stripe` | Stripe webhook receiver |
| GET | `/health` | Liveness check |

Full interactive docs at `/docs` once the server is running.

## Testing

```bash
pytest -v            # all 23 tests
pytest --cov=app     # with coverage
```

Tests cover: duplicate-usage prevention (incl. a simulated race condition),
quota boundaries (at / just-under / over, both plans), the pinned token
pricing rules, forged-webhook rejection, and duplicate-webhook handling.
Quota-boundary tests seed bulk usage history directly via the DB rather than
firing tens of thousands of real HTTP calls — the boundary-crossing request
itself always goes through the real API.

## Limitations (honest, by design — see §7 of the brief)

- No invoicing, proration, or overage billing — stretch goals, not core.
- AI token counts are simulated inputs to the endpoint; no real model is
  called (the brief explicitly scopes this out).
- Tenant onboarding (`POST /tenants`) has no auth in front of it — it's the
  front door for this capstone's scope. A real deployment would put it
  behind an admin/auth layer.
- Single currency (USD) throughout.

## Stack

Python 3.12 · FastAPI · SQLAlchemy 2.0 · Alembic · PostgreSQL 16 (Docker) ·
Stripe test mode + Stripe CLI · pytest.
