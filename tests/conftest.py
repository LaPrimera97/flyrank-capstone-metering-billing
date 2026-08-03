import os

os.environ["DATABASE_URL"] = "sqlite:///./test_billing.db"

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import Base, get_db
from app.main import app

TEST_DB_URL = "sqlite:///./test_billing.db"
engine = create_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(autouse=True)
def _clean_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def free_tenant(client):
    resp = client.post("/tenants", json={"name": "Test Free Co."})
    assert resp.status_code == 200
    return resp.json()


@pytest.fixture
def pro_tenant(client):
    resp = client.post("/tenants", json={"name": "Test Pro Co."})
    data = resp.json()
    # Promote directly via DB for test convenience (mirrors what a webhook would do).
    db = TestingSessionLocal()
    from app.models import Tenant
    t = db.query(Tenant).filter(Tenant.id == data["id"]).first()
    t.plan = "pro"
    db.commit()
    db.close()
    data["plan"] = "pro"
    return data
