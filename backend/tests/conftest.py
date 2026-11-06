import os

os.environ["DEMO_MODE"] = "false"  # retain coverage of the future Supabase Auth flow
os.environ["DEMO_TOKEN_SECRET"] = "demo-test-secret-at-least-thirty-two-characters"
os.environ["AUTO_CREATE_TABLES"] = "false"
os.environ["DATABASE_URL"] = "sqlite://"
os.environ["SUPABASE_JWT_SECRET"] = "test-secret-test-secret-test-secret-123456"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from app import models  # noqa: E402,F401
from app.db.base import Base  # noqa: E402
from app.db.session import get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.services.supabase_client import get_supabase  # noqa: E402
from tests.helpers import FakeSupabase, register  # noqa: E402


@pytest.fixture()
def fake_sb():
    return FakeSupabase()


@pytest.fixture()
def client(fake_sb):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    def override_get_db():
        db = Session()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_supabase] = lambda: fake_sb
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture()
def authed(client):
    """Client pre-authenticated as the admin of 'Alpha Bank'."""
    headers, _ = register(client)
    client.headers.update(headers)
    return client
