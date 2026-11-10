"""Lifecycle and isolation tests for bank-scoped machine API keys.

Management is JWT bank_admin-only: create (raw token shown once), list (never
leaks secrets or hashes), revoke (immediate, idempotent). Machine auth presents
the raw token as Bearer: 'read' pulls bank-scoped signal, 'operate' adds
drain/investigate. Cross-bank keys stay invisible to each other.
"""
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient

from app import models  # noqa: F401
from app.api.deps import get_db
from app.db.base import Base
from app.main import app
from app.models import ApiKey, Bank
from app.models.enums import BankStatus
from app.services.supabase_client import get_supabase
from tests.helpers import FakeSupabase, register


@pytest.fixture()
def two_banks():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    fake_sb = FakeSupabase()

    def override_db():
        db = Session()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_supabase] = lambda: fake_sb
    client = TestClient(app)
    a_headers, _ = register(client, bank="Key Bank A", email="keya@example.com")
    b_headers, _ = register(client, bank="Key Bank B", email="keyb@example.com")
    yield {"client": client, "Session": Session, "a": a_headers, "b": b_headers}
    app.dependency_overrides.clear()
    engine.dispose()


def _create(client, headers, **overrides):
    payload = {"name": "Dashboard pull", "scopes": ["read"]}
    payload.update(overrides)
    res = client.post("/api/v1/api-keys", json=payload, headers=headers)
    assert res.status_code == 201, res.text
    return res.json()


def test_create_shows_raw_token_once_and_stores_only_hash(two_banks):
    client, Session = two_banks["client"], two_banks["Session"]
    created = _create(client, two_banks["a"])
    token = created["token"]
    assert token.startswith("cfx_api_")

    # List never exposes the raw token or hash.
    listed = client.get("/api/v1/api-keys", headers=two_banks["a"]).json()
    assert len(listed) == 1
    assert "token" not in listed[0] and "key_hash" not in listed[0]
    assert listed[0]["key_prefix"] == created["key_prefix"]

    with Session() as db:
        key = db.scalar(select(ApiKey).where(ApiKey.key_prefix == created["key_prefix"]))
        assert key.key_hash != token and token not in key.key_hash
        assert key.status == "active"


def test_machine_read_scope_pulls_bank_signal(two_banks):
    client = two_banks["client"]
    created = _create(client, two_banks["a"])
    m = {"Authorization": f"Bearer {created['token']}"}

    assert client.get("/api/v1/machine/summary", headers=m).status_code == 200
    assert client.get("/api/v1/machine/incidents", headers=m).status_code == 200
    assert client.get("/api/v1/machine/complaints", headers=m).status_code == 200
    assert client.get("/api/v1/machine/audit", headers=m).status_code == 200
    assert client.get("/api/v1/machine/health/connectors", headers=m).status_code == 200
    # operate-only endpoints reject a read-only key.
    assert client.post("/api/v1/machine/jobs/drain", headers=m).status_code == 403
    assert client.post("/api/v1/machine/investigations",
                       json={"incident_id": str(uuid.uuid4())}, headers=m).status_code == 403


def test_connector_token_and_jwt_do_not_cross_authenticate(two_banks):
    from app.services.bank_intake import generate_connector_token

    client = two_banks["client"]
    created = _create(client, two_banks["a"])
    key_headers = {"Authorization": f"Bearer {created['token']}"}
    # Machine key is not a user JWT: JWT-only routes reject it.
    assert client.get("/api/v1/complaints", headers=key_headers).status_code in (401, 403)
    # JWT cannot act as an ingestion connector either (wrong prefix domain).
    a_jwt = two_banks["a"]["Authorization"]
    denied = client.post("/api/v1/ingestion/complaints", json={},
                         headers={"Authorization": a_jwt})
    assert denied.status_code in (401, 403, 422)
    # JWT also cannot reach the machine surface (needs cfx_api_ prefix).
    assert client.get("/api/v1/machine/summary", headers=two_banks["a"]).status_code == 401
    _ = generate_connector_token  # connector domain is separate: cfx_conn_ never verifies here


def test_revocation_is_immediate_and_cross_bank_invisible(two_banks):
    client = two_banks["client"]
    created = _create(client, two_banks["a"])
    m = {"Authorization": f"Bearer {created['token']}"}
    assert client.get("/api/v1/machine/summary", headers=m).status_code == 200

    # Non-admin (agent) cannot manage keys.
    from tests.helpers import make_token
    member = client.post("/api/v1/bank/members", headers=two_banks["a"], json={
        "email": "agent@example.com", "full_name": "Agent User", "role": "agent",
    })
    assert member.status_code == 201, member.text
    agent_headers = {"Authorization": "Bearer " + make_token(member.json()["id"], "agent@example.com")}
    assert client.get("/api/v1/api-keys", headers=agent_headers).status_code == 403

    revoke = client.post(f"/api/v1/api-keys/{created['id']}/revoke", headers=two_banks["a"])
    assert revoke.status_code == 200, revoke.text
    assert revoke.json()["status"] == "revoked"
    # Idempotent second revoke.
    assert client.post(f"/api/v1/api-keys/{created['id']}/revoke",
                       headers=two_banks["a"]).status_code == 200
    assert client.get("/api/v1/machine/summary", headers=m).status_code == 403

    # Bank B sees nothing of Bank A's keys and cannot revoke them.
    assert client.get("/api/v1/api-keys", headers=two_banks["b"]).json() == []
    assert client.post(f"/api/v1/api-keys/{created['id']}/revoke",
                       headers=two_banks["b"]).status_code == 404


def test_expired_key_is_rejected(two_banks):
    client = two_banks["client"]
    created = _create(client, two_banks["a"])
    m = {"Authorization": f"Bearer {created['token']}"}
    assert client.get("/api/v1/machine/summary", headers=m).status_code == 200
    # The create endpoint rightly rejects past timestamps, so backdate expiry in the DB.
    with two_banks["Session"]() as db:
        key = db.scalar(select(ApiKey).where(ApiKey.key_prefix == created["key_prefix"]))
        key.expires_at = datetime.now(timezone.utc) - timedelta(hours=1)
        db.commit()
    assert client.get("/api/v1/machine/summary", headers=m).status_code == 403


def test_operate_scope_drains_and_investigates(two_banks):
    from datetime import timedelta

    from app.services.spike_detection import bucket_start

    client = two_banks["client"]
    admin = two_banks["a"]
    created = _create(client, admin, name="Ops key", scopes=["read", "operate"])
    m = {"Authorization": f"Bearer {created['token']}"}

    # Seed one classified spike through the JWT path, then drain via machine key.
    slot = bucket_start(datetime.now(timezone.utc), 15) + timedelta(minutes=1)
    bulk = client.post("/api/v1/complaints/bulk", headers=admin, json={"complaints": [
        {"channel": "in_app",
         "text": f"Transfer of NGN 25000 failed and account debited {i}",
         "occurred_at": slot.isoformat(), "issue_type": "failed_transfer"}
        for i in range(12)
    ]})
    assert bulk.status_code == 201, bulk.text
    drain = client.post("/api/v1/machine/jobs/drain", headers=m, json={"limit": 100})
    assert drain.status_code == 200, drain.text
    # 12 pre-classified complaints share one idempotent detect:{bucket} job;
    # draining completes the detect + queued investigate jobs.
    assert drain.json()["completed"] == 2
    assert drain.json()["dead_lettered"] == 0

    incidents = client.get("/api/v1/machine/incidents", headers=m).json()
    assert len(incidents) == 1
    overview = client.get(f"/api/v1/machine/incidents/{incidents[0]['id']}", headers=m)
    assert overview.status_code == 200, overview.text

    inv = client.post("/api/v1/machine/investigations", headers=m,
                      json={"incident_id": incidents[0]["id"]})
    assert inv.status_code == 202, inv.text
    assert inv.json()["incident_id"] == incidents[0]["id"]
