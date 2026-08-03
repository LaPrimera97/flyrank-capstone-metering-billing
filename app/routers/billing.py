from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_tenant
from app.models import Tenant
from app.schemas import CheckoutSessionResponse
from app.services import stripe_service

router = APIRouter(prefix="/billing", tags=["billing"])


@router.post("/checkout", response_model=CheckoutSessionResponse)
def create_checkout(
    tenant: Tenant = Depends(get_current_tenant),
    db: Session = Depends(get_db),
):
    """Tenant picks Pro -> returns a Stripe test-mode Checkout URL to open."""
    url = stripe_service.create_checkout_session(db, tenant)
    return CheckoutSessionResponse(checkout_url=url)


@router.get("/success")
def checkout_success(session_id: str | None = None):
    return {"message": "Checkout complete. Your plan will update once the webhook is processed.", "session_id": session_id}


@router.get("/cancel")
def checkout_cancel():
    return {"message": "Checkout canceled."}
