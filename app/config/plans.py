"""
Pinned plan + pricing constants.

MONEY RULE: every price here is an integer number of MICRODOLLARS
(1 microdollar = $0.000001 = 1e-6 USD). We never use floats for money.
Integer math avoids the classic "$0.1 + $0.2 != $0.3" float bug and keeps
per-token pricing (which is often a tiny fraction of a cent) exact.

To convert to display cents:  cents = round(microdollars / 10_000)
To convert to display dollars: dollars = microdollars / 1_000_000
"""

from enum import Enum


class PlanTier(str, Enum):
    FREE = "free"
    PRO = "pro"


class UsageType(str, Enum):
    API_CALL = "api_call"
    AI_TOKENS = "ai_tokens"


# ---------------------------------------------------------------------------
# Quotas — monthly allowance per plan, per usage type.
# ---------------------------------------------------------------------------
PLAN_QUOTAS = {
    PlanTier.FREE: {
        UsageType.API_CALL: 1_000,
        UsageType.AI_TOKENS: 100_000,
    },
    PlanTier.PRO: {
        UsageType.API_CALL: 100_000,
        UsageType.AI_TOKENS: 10_000_000,
    },
}

# ---------------------------------------------------------------------------
# Pricing — pinned, tested in tests/test_pricing.py.
# All prices are per-unit in microdollars unless noted "per_million".
# ---------------------------------------------------------------------------

# Flat price per billable API call.
API_CALL_PRICE_MICROS = 1_000  # $0.001 per call

# Token pricing, expressed as price per 1,000,000 tokens (industry convention),
# stored as an integer number of microdollars per million tokens.
# Cached input tokens are cheaper than fresh input tokens.
# Reasoning tokens are billed at the OUTPUT rate (they are not a separate,
# cheaper category — they are "hidden output").
TOKEN_PRICE_PER_MILLION_MICROS = {
    "input": 3_000_000,          # $3.00 / 1M input tokens
    "cached_input": 750_000,     # $0.75 / 1M cached input tokens (75% cheaper)
    "output": 15_000_000,        # $15.00 / 1M output tokens
    # reasoning tokens intentionally have NO separate entry — see pricing_service.
}


def get_quota(plan: PlanTier, usage_type: UsageType) -> int:
    return PLAN_QUOTAS[PlanTier(plan)][UsageType(usage_type)]
