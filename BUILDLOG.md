# BUILDLOG.md

Honest log of where AI (Claude) helped, where it was wrong, and what got
changed. This capstone was built collaboratively with Claude end-to-end,
including running the actual test suite and fixing real bugs it produced —
not just generating code that was never executed.

## Where AI helped

- Full project scaffold: layered architecture (routers → services → models),
  Alembic migration setup, Docker Compose + devcontainer config for a
  browser-only/Codespaces workflow.
- Idempotency design: the DB-level `UNIQUE(tenant_id, idempotency_key)`
  constraint as the real correctness guarantee, with an `IntegrityError`
  recovery path for the race-condition case (two identical retries landing
  at the same instant).
- The 402-vs-429 boundary rule (Free plan over quota → 402 since upgrading
  fixes it; Pro plan over quota → 429, a hard ceiling) and writing it down
  explicitly rather than picking one status code for everything.
- Token pricing math using integer "microdollar" arithmetic throughout, with
  round-half-up on the final division, to satisfy the "money as integers,
  never floats" rule.
- The full pytest suite, including a live curl-based smoke test used to
  produce the evidence pasted into `EVIDENCE.md`.

## Where AI was wrong, and what changed

1. **`UsageEvent.id` was `None` at response-build time.** The model defines
   `id = Column(String, default=_uuid)`, but SQLAlchemy only applies
   Python-side column defaults on flush/insert — not the moment the object
   is constructed. The first draft of `meter_service.record_usage` built the
   `GenerateResponse` (which needs `usage_event_id`) *before* the row was
   flushed, so it was `None` and failed Pydantic validation. **Fix:**
   generate the UUID explicitly with `id=str(uuid.uuid4())` at construction
   time, before building the response.

2. **Wrong assumption about `stripe.Webhook.construct_event`'s return type.**
   The installed Stripe SDK (15.4.0 — newer than the `10.12.0` first pinned
   in `requirements.txt`) returns `StripeObject`s whose `__getattr__`
   doesn't reliably expose dict-style `.get()` on nested objects the way
   older SDK versions did, causing an `AttributeError: get` deep inside
   `handle_event`. **Fix:** convert the verified event to a plain dict with
   `.to_dict()` immediately after signature verification, so every
   downstream function works with a boring plain dict instead of an SDK
   object. Also re-pinned `requirements.txt` to the version actually tested
   against (15.4.0).

3. **Performance bug in my own quota boundary tests.** The first draft of
   `test_quota.py` drove a Pro-plan tenant to its 100,000-call limit by
   firing 100,000 real HTTP requests through the FastAPI TestClient in a
   loop — which hung the test run entirely. **Fix:** rewrote the setup to
   bulk-insert the "already used" usage history directly via
   `db.bulk_insert_mappings`, and only send the actual boundary-crossing
   request through the real API (which is the thing under test anyway —
   the other 99,999 rows are just fixture data).

4. **Wrong assumption about missing-header behavior.** A first-draft test
   assumed a missing `X-API-Key` header would hit the app's own 401 logic.
   In FastAPI, a required `Header(...)` parameter that's entirely absent
   fails at the framework's request-validation layer first, returning 422 —
   the app-level 401 only fires for a header that's *present but wrong*.
   **Fix:** split into two tests — missing header → 422, present-but-invalid
   key → 401 — and documented the distinction.

## What a reviewer should verify themselves

- `docker compose up --build` boots cleanly against real Postgres (this log
  covers the SQLite-based dev/test path only — Postgres via Docker was not
  exercised in the environment this was built in, and should be your first
  smoke test on Codespaces).
- A real Stripe Checkout flow end-to-end with `stripe listen` forwarding to
  a live server (the webhook *tests* use hand-signed payloads to avoid
  needing live Stripe calls in CI; a real Checkout session should be run at
  least once for the demo).
