# EVIDENCE.md

One pasted proof per Definition-of-Done checkbox (§6 of the brief). All
output below is real, captured from a live Codespace running against real
PostgreSQL and real Stripe test mode — not simulated.

---

## METERING

### A billable action creates exactly one usage event, even under retries

Live transcript via `/docs`, same tenant, same `Idempotency-Key: demo-key-1`
sent twice:

-- first call --
{"usage_event_id":"155f8fff-b652-4389-8d2f-d05d28150a33", "quota_used":1,
"quota_limit":1000,"idempotent_replay":false}

-- retry, same key --
{"usage_event_id":"155f8fff-b652-4389-8d2f-d05d28150a33", "quota_used":1,
"quota_limit":1000,"idempotent_replay":true}

Same `usage_event_id` both times; `quota_used` stayed at 1, not 2.

A follow-up request with a different Idempotency-Key correctly created a
new event: `usage_event_id: 9ee2dd95-73a7-47f2-a6e6-75a9c63f5f0d`,
`quota_used: 2`.

### A test proves double-counting cannot happen

All 6 tests in `tests/test_idempotency.py` passed — see full output below.

---

## QUOTAS

### Usage checked against plan; correct 402/429 status codes with clear messages

A Free-plan tenant at exactly 1,000 calls is allowed; the 1,001st call is
rejected:

```json
{"detail":{"error":"payment_required",
 "message":"This request would use 1001 of your Free plan's 1000 monthly api_call quota. Upgrade to Pro to continue.",
 "quota_used":1000,"quota_limit":1000}}
```

HTTP 402. A Pro-plan tenant over its (higher) limit gets HTTP 429 instead.
All 5 tests in `tests/test_quota.py` passed — see full output below.

---

## COST CALCULATION

### Monthly rollup, AI token pricing rules, pinned constants

Pinned example: 1,000 input + 500 cached-input + 200 output + 100 reasoning
tokens → cost = 3000 + 375 + 4500 = **7875 microdollars ($0.007875)**,
computed via integer arithmetic only. All 8 tests in `tests/test_pricing.py`
passed — see full output below.

---

## STRIPE INTEGRATION

### Real Checkout completed, webhooks verified and processed

Real Stripe Checkout completed with test card `4242 4242 4242 4242` against
the live Stripe test dashboard (account `FlyRank Capstone Demo sandbox`,
`acct_1U0GBZ2UOVwri9JX`). `stripe listen` confirmed every event type Stripe
sent — `invoice.created`, `invoice.payment_succeeded`,
`checkout.session.completed`, `invoice_payment.paid` — was received,
signature-verified, and processed with a 200.

`GET /usage` for the checked-out tenant afterward:

```json
{
  "tenant_id": "a9dd934d-9df2-4477-8ad0-8e4ca23f92fb",
  "plan": "pro",
  "billing_period": "2026-08",
  "api_calls_limit": 100000,
  "ai_tokens_limit": 10000000
}
```

`plan: "pro"` confirms the webhook correctly flipped the tenant from Free
to Pro.

A real bug was found and fixed during this live test: newer Stripe API
responses represent some invoice amounts as Python `Decimal` objects, which
crashed webhook payload storage with a 500 on `invoice.created` and
`invoice.payment_succeeded` (though `checkout.session.completed` itself
always succeeded). See `BUILDLOG.md` for the full story. All 4 tests in
`tests/test_webhooks.py` passed — see full output below.

---

## DATA MODEL, TESTS & DOCUMENTATION

Schema: see `app/models.py` and `migrations/versions/0001_initial_schema.py`.
Every usage/webhook query is filtered by `tenant_id`.

### Full test suite, all green

collected 23 items

tests/test_idempotency.py::test_same_idempotency_key_creates_exactly_one_usage_event PASSED
tests/test_idempotency.py::test_retry_mirrors_original_response_even_with_different_body PASSED
tests/test_idempotency.py::test_different_idempotency_keys_create_separate_events PASSED
tests/test_idempotency.py::test_missing_idempotency_key_is_rejected PASSED
tests/test_idempotency.py::test_missing_api_key_header_is_a_validation_error PASSED
tests/test_idempotency.py::test_invalid_api_key_is_rejected_with_401 PASSED
tests/test_pricing.py::test_api_call_cost_is_flat_and_linear PASSED
tests/test_pricing.py::test_token_categories_priced_independently_then_summed PASSED
tests/test_pricing.py::test_cached_input_tokens_are_cheaper_than_fresh_input PASSED
tests/test_pricing.py::test_reasoning_tokens_billed_at_output_rate_not_a_separate_category PASSED
tests/test_pricing.py::test_categories_are_not_simply_added_as_one_token_count PASSED
tests/test_pricing.py::test_rounding_is_half_up_and_integer_only PASSED
tests/test_pricing.py::test_total_tokens_for_quota_sums_every_category PASSED
tests/test_pricing.py::test_micros_to_usd_string_is_exact_no_float_drift PASSED
tests/test_quota.py::test_request_exactly_at_the_limit_is_allowed PASSED
tests/test_quota.py::test_request_one_over_the_limit_is_rejected_with_402_on_free_plan PASSED
tests/test_quota.py::test_request_over_the_limit_is_rejected_with_429_on_pro_plan PASSED
tests/test_quota.py::test_request_just_under_the_limit_is_allowed PASSED
tests/test_quota.py::test_ai_token_quota_enforced_on_total_tokens PASSED
tests/test_webhooks.py::test_forged_signature_is_rejected_with_400_and_nothing_changes PASSED
tests/test_webhooks.py::test_valid_checkout_completed_event_flips_tenant_to_pro PASSED
tests/test_webhooks.py::test_replayed_event_is_processed_once PASSED
tests/test_webhooks.py::test_subscription_deleted_event_downgrades_tenant_to_free PASSED

======================== 23 passed, 6 warnings in 7.87s ========================

### README + architecture diagram + setup instructions

See `README.md`.

### Submission-pack files present

`README.md`, `capstone.yaml`, `EVIDENCE.md`, `BUILDLOG.md`, `.env.example`
— all present at repo root.