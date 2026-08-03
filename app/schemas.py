from typing import Optional
from pydantic import BaseModel, Field


class TokenBreakdown(BaseModel):
    input_tokens: int = 0
    cached_input_tokens: int = 0
    output_tokens: int = 0
    reasoning_tokens: int = 0


class GenerateRequest(BaseModel):
    """Body for the one dummy billable endpoint, POST /v1/generate."""
    usage_type: str = Field(..., pattern="^(api_call|ai_tokens)$")
    # For usage_type == "api_call": quantity is the number of calls (usually 1).
    quantity: int = 1
    # For usage_type == "ai_tokens": token breakdown drives both quota + cost.
    tokens: Optional[TokenBreakdown] = None


class GenerateResponse(BaseModel):
    usage_event_id: str
    tenant_id: str
    usage_type: str
    billable_quantity: int
    cost_micros: int
    cost_usd: str
    quota_used: int
    quota_limit: int
    idempotent_replay: bool


class UsageSummaryResponse(BaseModel):
    tenant_id: str
    plan: str
    billing_period: str
    api_calls_used: int
    api_calls_limit: int
    ai_tokens_used: int
    ai_tokens_limit: int
    total_cost_micros: int
    total_cost_usd: str


class CheckoutSessionResponse(BaseModel):
    checkout_url: str


class ErrorResponse(BaseModel):
    error: str
    message: str
