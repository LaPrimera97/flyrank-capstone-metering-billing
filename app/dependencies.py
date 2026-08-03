from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Tenant


def get_current_tenant(
    x_api_key: str = Header(..., alias="X-API-Key"),
    db: Session = Depends(get_db),
) -> Tenant:
    """
    Real authorization: every billable/usage request must present a valid
    per-tenant API key. Bad input -> clean 4xx, never a 500.
    """
    tenant = db.query(Tenant).filter(Tenant.api_key == x_api_key).first()
    if tenant is None:
        raise HTTPException(status_code=401, detail="Invalid or missing X-API-Key.")
    return tenant
