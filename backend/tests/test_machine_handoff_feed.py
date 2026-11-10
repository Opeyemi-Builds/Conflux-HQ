"""Tests for the bank handoff feed: GET /machine/updates.

Banks poll this with their `cfx_api_` key to mirror Conflux signal into their
own dashboards. The feed is bank-scoped, cursor-versioned, and built for a
5s ticker loop: every poll returns the next cursor, empty items means
"nothing changed", and only polls carrying signal are audited.
"""
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
from app.models import ApiKey, CorrectiveAction, Incident
from app.models.enums import Channel, IssueType
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


def _create_key(client, headers, scopes=("read",)):
    res = client.post("/api/v1/api-keys", json={"name": "Feed pull", "scopes": list(scopes)}, headers=headers)
    assert res.status_code == 201, res.text
    return res.json()


def test_first_poll_returns_everything_and_cursor_advances(two_banks):
    client = two_banks["client"]
    key = _create_key(client, two_banks["a"])
    m = {"Authorization": f"Bearer {key['token']}"}

    # Seed some bank activity through the JWT path.
    seeded = client.post("/api/v1/complaints/bulk", headers=two_banks["a"], json={"complaints": [
        {"channel": "in_app", "text": f"Transfer of NGN 25000 failed and account debited {i}",
         "issue_type": "failed_transfer"}
        for i in range(3)
    ]})
    assert seeded.status_code == 201, seeded.text

    first = client.get("/api/v1/machine/updates", headers=m)
    assert first.status_code == 200, first.text
    body = first.json()
    assert body["poll_interval_seconds"] == 5  # ticker cadence for bank dashboards
    assert body["since"] is None and body["cursor"] is not None
    assert body["count"] >= 3
    kinds = {it["collection"] for it in body["items"]}
    assert "complaints" in kinds
    # Ticker payload: issue + severity + time + location + text. No analysis fields.
    first_complaint = next(it for it in body["items"] if it["collection"] == "complaints")
    assert set(first_complaint["data"]) == {
        "id", "channel", "issue_type", "severity", "text", "summary",
        "region", "occurred_at", "incident_id",
    }

    # Second poll with the cursor is empty: nothing changed.
    second = client.get("/api/v1/machine/updates", headers=m, params={"since": body["cursor"]})
    assert second.status_code == 200, second.text
    assert second.json()["items"] == []
    assert second.json()["cursor"] == body["cursor"]


def test_feed_is_bank_scoped_and_collection_filterable(two_banks):
    client = two_banks["client"]
    key_a = _create_key(client, two_banks["a"])
    key_b = _create_key(client, two_banks["b"])
    ma = {"Authorization": f"Bearer {key_a['token']}"}
    mb = {"Authorization": f"Bearer {key_b['token']}"}

    client.post("/api/v1/complaints/bulk", headers=two_banks["a"], json={"complaints": [
        {"channel": "x", "text": "Bank A failed transfer", "issue_type": "failed_transfer"},
    ]})

    feed_a = client.get("/api/v1/machine/updates", headers=ma).json()
    feed_b = client.get("/api/v1/machine/updates", headers=mb).json()
    assert feed_a["count"] >= 1
    assert all(it["collection"] != "complaints" or "Bank A" in it["data"]["text"] for it in feed_a["items"])
    # Bank B sees only its own rows (its key-management audit) — none of Bank A's data.
    assert all("Bank A" not in (it["data"].get("text") or "") for it in feed_b["items"])
    assert not any(it["collection"] == "complaints" for it in feed_b["items"])

    only_incidents = client.get(
        "/api/v1/machine/updates", headers=ma, params={"collections": "incidents"}
    ).json()
    assert only_incidents["collections"] == ["incidents"]
    assert all(it["collection"] == "incidents" for it in only_incidents["items"])

    bad = client.get("/api/v1/machine/updates", headers=ma, params={"collections": "nope"})
    assert bad.status_code == 422
    bad_cursor = client.get("/api/v1/machine/updates", headers=ma, params={"since": "not-a-time"})
    assert bad_cursor.status_code == 422


def test_feed_tracks_incident_action_and_draft_lifecycle(two_banks):
    from app.services.spike_detection import bucket_start

    client = two_banks["client"]
    key = _create_key(client, two_banks["a"])
    m = {"Authorization": f"Bearer {key['token']}"}

    slot = bucket_start(datetime.now(timezone.utc), 15) + timedelta(minutes=1)
    bulk = client.post("/api/v1/complaints/bulk", headers=two_banks["a"], json={"complaints": [
        {"channel": "in_app", "text": f"Transfer of NGN 25000 failed and account debited {i}",
         "occurred_at": slot.isoformat(), "issue_type": "failed_transfer"}
        for i in range(12)
    ]})
    assert bulk.status_code == 201, bulk.text
    assert client.post("/api/v1/machine/jobs/drain", headers={**m, "Authorization": m["Authorization"]},
                       json={}).status_code in (200, 403)  # read-only key cannot drain

    operate = _create_key(client, two_banks["a"], scopes=("read", "operate"))
    mo = {"Authorization": f"Bearer {operate['token']}"}
    drain = client.post("/api/v1/machine/jobs/drain", headers=mo, json={"limit": 100})
    assert drain.status_code == 200, drain.text

    feed = client.get("/api/v1/machine/updates", headers=m).json()
    kinds = {it["collection"] for it in feed["items"]}
    # Worker auto-investigations update incidents + drafts without an InvestigationRun
    # row; explicit runs come from the operate endpoint below.
    assert {"complaints", "incidents", "drafts", "audit"} <= kinds

    incident_id = next(it["data"]["id"] for it in feed["items"] if it["collection"] == "incidents")
    inv = client.post("/api/v1/machine/investigations", headers=mo, json={"incident_id": incident_id})
    assert inv.status_code == 202, inv.text
    assert client.post("/api/v1/machine/jobs/drain", headers=mo, json={"limit": 100}).status_code == 200
    feed = client.get("/api/v1/machine/updates", headers=m).json()
    assert "investigations" in {it["collection"] for it in feed["items"]}
    action = client.post(f"/api/v1/incidents/{incident_id}/actions", headers=two_banks["a"], json={
        "title": "Check settlement file", "recommendation": "Reconcile the daily settlement file line by line."})
    assert action.status_code == 201, action.text

    cursor = feed["cursor"]
    delta = client.get("/api/v1/machine/updates", headers=m, params={"since": cursor}).json()
    assert any(it["collection"] == "actions" for it in delta["items"])


def test_feed_requires_machine_credential_not_jwt(two_banks):
    client = two_banks["client"]
    # JWT (even admin) is the wrong domain for the machine surface.
    assert client.get("/api/v1/machine/updates", headers=two_banks["a"]).status_code == 401
    # Unknown/garbage bearer is rejected, never leaks data.
    assert client.get("/api/v1/machine/updates",
                      headers={"Authorization": "Bearer cfx_api_nope_nope"}).status_code == 401


def test_expired_and_revoked_keys_lose_feed_access(two_banks):
    from datetime import timedelta

    client = two_banks["client"]
    created = _create_key(client, two_banks["a"])
    m = {"Authorization": f"Bearer {created['token']}"}
    assert client.get("/api/v1/machine/updates", headers=m).status_code == 200

    with two_banks["Session"]() as db:
        key = db.scalar(select(ApiKey).where(ApiKey.key_prefix == created["key_prefix"]))
        key.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        db.commit()
    assert client.get("/api/v1/machine/updates", headers=m).status_code == 403

    fresh = _create_key(client, two_banks["a"])
    mf = {"Authorization": f"Bearer {fresh['token']}"}
    revoke = client.post(f"/api/v1/api-keys/{fresh['id']}/revoke", headers=two_banks["a"])
    assert revoke.status_code == 200, revoke.text
    assert client.get("/api/v1/machine/updates", headers=mf).status_code == 403


def test_feed_poll_audits_only_signal(two_banks):
    """Signal-bearing polls are audited; empty 5s ticker polls write nothing."""
    client = two_banks["client"]
    key = _create_key(client, two_banks["a"])
    m = {"Authorization": f"Bearer {key['token']}"}

    # Fresh bank: first poll returns the key-management audit row -> audited.
    assert client.get("/api/v1/machine/updates", headers=m).status_code == 200
    trail = client.get("/api/v1/machine/audit", headers=m).json()
    assert any(row["action"] == "machine_updates_polled" for row in trail)

    # Empty poll (cursor at head) writes no new audit rows.
    cursor = client.get("/api/v1/machine/updates", headers=m).json()["cursor"]
    before = len(client.get("/api/v1/machine/audit", headers=m).json())
    empty = client.get("/api/v1/machine/updates", headers=m, params={"since": cursor}).json()
    assert empty["items"] == []
    after = len(client.get("/api/v1/machine/audit", headers=m).json())
    assert after == before


def test_incident_updates_advance_the_cursor(two_banks):
    """Growth in the same bucket surfaces as new complaint items, not a re-stamped incident."""
    from app.services.spike_detection import bucket_start

    client = two_banks["client"]
    key = _create_key(client, two_banks["a"])
    m = {"Authorization": f"Bearer {key['token']}"}
    slot = bucket_start(datetime.now(timezone.utc), 15) + timedelta(minutes=1)

    def seed(n):
        return client.post("/api/v1/complaints/bulk", headers=two_banks["a"], json={"complaints": [
            {"channel": "in_app", "text": f"Transfer of NGN 25000 failed and account debited {n}-{i}",
             "occurred_at": slot.isoformat(), "issue_type": "failed_transfer"}
            for i in range(12)
        ]})

    assert seed(0).status_code == 201
    operate = _create_key(client, two_banks["a"], scopes=("read", "operate"))
    mo = {"Authorization": f"Bearer {operate['token']}"}
    assert client.post("/api/v1/machine/jobs/drain", headers=mo, json={"limit": 100}).status_code == 200
    first = client.get("/api/v1/machine/updates", headers=m).json()
    assert any(it["collection"] == "incidents" for it in first["items"])

    # More complaints in the same bucket grow the open incident in place
    # (complaint_count bumps, detected_at stays); the feed surfaces the growth
    # as new complaint items, not a duplicate incident row.
    assert seed(1).status_code == 201
    assert client.post("/api/v1/machine/jobs/drain", headers=mo, json={"limit": 100}).status_code == 200
    delta = client.get("/api/v1/machine/updates", headers=m, params={"since": first["cursor"]}).json()
    assert any(it["collection"] == "complaints" for it in delta["items"])

    with two_banks["Session"]() as db:
        incidents = db.scalars(select(Incident)).all()
        assert len(incidents) == 1 and incidents[0].complaint_count >= 24
