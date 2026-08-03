from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Tenant

router = APIRouter(prefix="/tenants", tags=["tenants"])


class CreateTenantRequest(BaseModel):
    name: str


class TenantResponse(BaseModel):
    id: str
    name: str
    api_key: str
    plan: str
    status: str


@router.post("", response_model=TenantResponse)
def create_tenant(body: CreateTenantRequest, db: Session = Depends(get_db)):
    """Minimal onboarding: create a tenant, get back its API key. No auth on
    this endpoint by design — it's the front door. In production this would
    sit behind an admin/auth layer; out of scope for this capstone."""
    tenant = Tenant(name=body.name, plan="free", status="active")
    db.add(tenant)
    db.commit()
    db.refresh(tenant)
    return TenantResponse(id=tenant.id, name=tenant.name, api_key=tenant.api_key, plan=tenant.plan, status=tenant.status)
