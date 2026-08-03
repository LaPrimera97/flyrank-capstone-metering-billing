"""
Cost calculation. All money math is integer microdollar arithmetic — see
app/config/plans.py for the "why integers" rule. No floats touch a cost
value anywhere in this module.
"""
from decimal import Decimal

from app.config.plans import API_CALL_PRICE_MICROS, TOKEN_PRICE_PER_MILLION_MICROS
from app.schemas import TokenBreakdown


def _price_for_category(token_count: int, price_per_million_micros: int) -> int:
    """
    Integer cost for `token_count` tokens at `price_per_million_micros` per
    1,000,000 tokens, rounded half-up to the nearest microdollar. Pure
    integer arithmetic throughout.
    """
    numerator = token_count * price_per_million_micros
    return (numerator + 500_000) // 1_000_000


def calculate_api_call_cost_micros(quantity: int) -> int:
    return quantity * API_CALL_PRICE_MICROS


def calculate_token_cost_micros(tokens: TokenBreakdown) -> int:
    """
    Token pricing rules (pinned, tested in tests/test_pricing.py):
      - input tokens priced at the standard input rate
      - cached input tokens priced at the (cheaper) cached rate
      - reasoning tokens are billed as OUTPUT tokens — they are not a
        separate, discounted category, and must not be dropped or
        double-counted
      - categories are priced independently, then summed — never averaged
        or naively added together as a single "token count"
    """
    billable_output_tokens = tokens.output_tokens + tokens.reasoning_tokens

    input_cost = _price_for_category(
        tokens.input_tokens, TOKEN_PRICE_PER_MILLION_MICROS["input"]
    )
    cached_input_cost = _price_for_category(
        tokens.cached_input_tokens, TOKEN_PRICE_PER_MILLION_MICROS["cached_input"]
    )
    output_cost = _price_for_category(
        billable_output_tokens, TOKEN_PRICE_PER_MILLION_MICROS["output"]
    )

    return input_cost + cached_input_cost + output_cost


def total_tokens_for_quota(tokens: TokenBreakdown) -> int:
    """
    Quota is metered on total tokens processed (all categories count against
    the monthly token allowance, even the cheaper cached ones).
    """
    return (
        tokens.input_tokens
        + tokens.cached_input_tokens
        + tokens.output_tokens
        + tokens.reasoning_tokens
    )


def micros_to_usd_string(cost_micros: int) -> str:
    """Exact decimal string, e.g. 3 -> '0.000003'. Uses Decimal, never float."""
    return str(Decimal(cost_micros) / Decimal(1_000_000))
