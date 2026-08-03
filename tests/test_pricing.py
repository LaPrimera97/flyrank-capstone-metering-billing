from app.schemas import TokenBreakdown
from app.services import pricing_service


def test_api_call_cost_is_flat_and_linear():
    assert pricing_service.calculate_api_call_cost_micros(1) == 1_000
    assert pricing_service.calculate_api_call_cost_micros(7) == 7_000


def test_token_categories_priced_independently_then_summed():
    tokens = TokenBreakdown(
        input_tokens=1000, cached_input_tokens=500, output_tokens=200, reasoning_tokens=100
    )
    cost = pricing_service.calculate_token_cost_micros(tokens)
    # input: 1000 * $3/1M = 3000 micros
    # cached: 500 * $0.75/1M = 375 micros
    # output+reasoning: 300 * $15/1M = 4500 micros
    assert cost == 3000 + 375 + 4500 == 7875


def test_cached_input_tokens_are_cheaper_than_fresh_input():
    fresh = pricing_service.calculate_token_cost_micros(
        TokenBreakdown(input_tokens=1000, cached_input_tokens=0, output_tokens=0, reasoning_tokens=0)
    )
    cached = pricing_service.calculate_token_cost_micros(
        TokenBreakdown(input_tokens=0, cached_input_tokens=1000, output_tokens=0, reasoning_tokens=0)
    )
    assert cached < fresh
    assert fresh == 3000
    assert cached == 750


def test_reasoning_tokens_billed_at_output_rate_not_a_separate_category():
    via_output = pricing_service.calculate_token_cost_micros(
        TokenBreakdown(input_tokens=0, cached_input_tokens=0, output_tokens=300, reasoning_tokens=0)
    )
    via_reasoning = pricing_service.calculate_token_cost_micros(
        TokenBreakdown(input_tokens=0, cached_input_tokens=0, output_tokens=0, reasoning_tokens=300)
    )
    split = pricing_service.calculate_token_cost_micros(
        TokenBreakdown(input_tokens=0, cached_input_tokens=0, output_tokens=150, reasoning_tokens=150)
    )
    assert via_output == via_reasoning == split == 4500


def test_categories_are_not_simply_added_as_one_token_count():
    """1000 tokens of pure input must cost less than 1000 tokens of pure
    output — proving categories can't be collapsed into a single count."""
    all_input = pricing_service.calculate_token_cost_micros(
        TokenBreakdown(input_tokens=1000, cached_input_tokens=0, output_tokens=0, reasoning_tokens=0)
    )
    all_output = pricing_service.calculate_token_cost_micros(
        TokenBreakdown(input_tokens=0, cached_input_tokens=0, output_tokens=1000, reasoning_tokens=0)
    )
    assert all_input != all_output


def test_rounding_is_half_up_and_integer_only():
    # 2 cached tokens * $0.75/1M = 1.5 micros -> rounds to 2
    cost = pricing_service.calculate_token_cost_micros(
        TokenBreakdown(input_tokens=0, cached_input_tokens=2, output_tokens=0, reasoning_tokens=0)
    )
    assert cost == 2
    assert isinstance(cost, int)


def test_total_tokens_for_quota_sums_every_category():
    tokens = TokenBreakdown(input_tokens=10, cached_input_tokens=20, output_tokens=30, reasoning_tokens=40)
    assert pricing_service.total_tokens_for_quota(tokens) == 100


def test_micros_to_usd_string_is_exact_no_float_drift():
    assert pricing_service.micros_to_usd_string(3) == "0.000003"
    assert pricing_service.micros_to_usd_string(1_000_000) == "1"
    assert pricing_service.micros_to_usd_string(0) == "0"
