from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.services import stripe_service

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


@router.post("/stripe")
async def stripe_webhook(request: Request, db: Session = Depends(get_db)):
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature", "")

    # 1. Verify signature. Forged/invalid -> 400, nothing changes.
    event = stripe_service.verify_and_parse_event(payload, sig_header)

    # 2. Deduplicate. A replayed real event is processed once.
    if stripe_service.is_duplicate_event(db, event["id"]):
        return {"status": "duplicate_ignored", "event_id": event["id"]}

    # 3. Apply the event, then record it so future replays are ignored.
    stripe_service.handle_event(db, event)
    stripe_service.record_event(db, event)

    return {"status": "processed", "event_id": event["id"]}
