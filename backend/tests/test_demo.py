from datetime import datetime, timedelta, timezone

import jwt
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.routes import analytics, auth, complaints, incidents, synthetic
from app.core.config import Settings, get_settings
from app.db.base import Base
from app.db.session import get_db
from app.models import Bank, Complaint
from app.models.enums import Channel
from app.services.demo_auth import DEMO_AUDIENCE, DEMO_ISSUER, DEMO_USER_ID

SECRET = "demo-test-secret-at-least-thirty-two-characters"
AT = "2026-11-06T10:14:59Z"


@pytest.fixture()
def demo(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "demo_mode", True)
    monkeypatch.setattr(settings, "demo_token_secret", SECRET)
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine, expire_on_commit=False, autoflush=False)

    def database():
        with sessions() as db:
            yield db

    app = FastAPI()
    app.include_router(auth.demo_router, prefix="/api/v1/auth")
    for router in (analytics.router, complaints.router, incidents.router, synthetic.router):
        app.include_router(router, prefix="/api/v1")
    app.dependency_overrides[get_db] = database
    with TestClient(app) as client:
        yield client, sessions
    engine.dispose()


def login(client):
    response = client.post("/api/v1/auth/login", json={"username": "Zymic Bank", "password": "123"})
    assert response.status_code == 200, response.text
    client.headers["Authorization"] = "Bearer " + response.json()["access_token"]
    return response.json()


def seed(client):
    response = client.post("/api/v1/synthetic/seed", json={"at": AT})
    assert response.status_code == 201, response.text
    return response.json()


def test_login_invalid_credentials_and_protected_routes(demo):
    client, _ = demo
    assert client.get("/api/v1/analytics/summary").status_code == 401
    for username, password in [("Zymic Bank", "bad"), ("Other Bank", "123")]:
        assert client.post("/api/v1/auth/login", json={"username": username, "password": password}).status_code == 401
    body = login(client)
    assert body["user"]["bank"]["name"] == "Zymic Bank"
    assert body["demo"] and body["synthetic"]
    assert body["expires_in"] == 7200
    assert login(client)["user"]["id"] == body["user"]["id"]
    assert client.get("/api/v1/analytics/summary").status_code == 200


def test_token_expiry_audience_signature_and_mode(demo, monkeypatch):
    client, _ = demo
    login(client)
    now = datetime.now(timezone.utc)
    valid = {"sub": str(DEMO_USER_ID), "iss": DEMO_ISSUER, "aud": DEMO_AUDIENCE,
             "iat": now, "exp": now + timedelta(hours=1)}
    for changes, secret in [({"exp": now - timedelta(seconds=1)}, SECRET),
                            ({"aud": "authenticated"}, SECRET), ({}, "another-secret-which-is-at-least-32-characters")]:
        token = jwt.encode({**valid, **changes}, secret, algorithm="HS256")
        client.headers["Authorization"] = "Bearer " + token
        assert client.get("/api/v1/analytics/summary").status_code == 401
    monkeypatch.setattr(get_settings(), "demo_token_secret", "")
    assert client.post("/api/v1/auth/login", json={"username": "Zymic Bank", "password": "123"}).status_code == 503
    monkeypatch.setattr(get_settings(), "demo_mode", False)
    assert client.post("/api/v1/auth/login", json={"username": "Zymic Bank", "password": "123"}).status_code == 404


def test_seed_analytics_and_idempotent_detection(demo):
    client, _ = demo
    login(client)
    body = seed(client)
    assert body["complaints_created"] == 1000
    assert client.post("/api/v1/synthetic/seed", json={"at": AT}).status_code == 409
    params = {"hours": 49, "at": body["detection_at"]}
    summary = client.get("/api/v1/analytics/summary", params=params).json()
    assert summary["total_complaints"] == 1000
    assert summary["fraud_count"] == 8
    assert float(summary["money_at_risk"]) > 0
    trends = client.get("/api/v1/analytics/trends", params=params).json()
    assert sum(b["total_complaints"] for b in trends["buckets"]) == 1000
    breakdown = client.get("/api/v1/analytics/breakdown", params=params).json()
    assert sum(breakdown["by_region"].values()) == 1000
    txns = client.get("/api/v1/analytics/transactions", params=params).json()
    assert txns["total_transactions"] == 5000
    assert 0 < txns["failed_rate"] < 1
    for _ in range(2):
        result = client.post("/api/v1/incidents/detect", json={"now": body["detection_at"]})
        assert result.status_code == 200, result.text
    detected = client.get("/api/v1/incidents").json()
    assert len(detected) == 1 and detected[0]["issue_type"] == "failed_transfer"
    assert detected[0]["complaint_count"] == 30
    # Linked synthetic transaction UUIDs must serialize in complaint responses.
    response = client.get("/api/v1/complaints", params={"issue_type": "failed_transfer", "limit": 50})
    assert response.status_code == 200, response.text
    assert any(row["transaction_id"] for row in response.json())
    assert client.get("/api/v1/synthetic/transactions", params={"status": "failed", "limit": 5}).status_code == 200
    assert len(client.get("/api/v1/synthetic/system-events").json()["items"]) == 2


def test_analytics_scope_boundaries_and_validation(demo):
    client, sessions = demo
    identity = login(client)
    from uuid import UUID
    bank_id = UUID(identity["user"]["bank"]["id"])
    anchor = datetime(2026, 11, 6, 10, tzinfo=timezone.utc)
    with sessions() as db:
        other = Bank(name="Other", slug="other", contact_email="other@example.com")
        db.add(other)
        db.flush()
        db.add_all([
            Complaint(bank_id=bank_id, channel=Channel.X, text="in window", occurred_at=anchor - timedelta(hours=1)),
            Complaint(bank_id=bank_id, channel=Channel.X, text="at exclusive end", occurred_at=anchor),
            Complaint(bank_id=bank_id, channel=Channel.X, text="future", occurred_at=anchor + timedelta(hours=1)),
            Complaint(bank_id=other.id, channel=Channel.X, text="other bank", occurred_at=anchor - timedelta(minutes=5)),
        ])
        db.commit()
    for endpoint in ("summary", "trends", "breakdown", "transactions"):
        path = "/api/v1/analytics/" + endpoint
        assert client.get(path, params={"hours": 0}).status_code == 422
        assert client.get(path, params={"at": "2026-11-06T10:00:00"}).status_code == 422
    params = {"hours": 2, "at": anchor.isoformat()}
    summary = client.get("/api/v1/analytics/summary", params=params).json()
    assert summary["total_complaints"] == 1
    trends = client.get("/api/v1/analytics/trends", params=params).json()
    assert [bucket["total_complaints"] for bucket in trends["buckets"]] == [0, 1]
    assert client.post("/api/v1/synthetic/seed", json={"at": AT}).status_code == 409
    assert client.post("/api/v1/synthetic/seed", json={"at": "2026-11-06T10:00:00"}).status_code == 422


def test_demo_mode_rejected_in_production():
    with pytest.raises(ValueError, match="DEMO_MODE"):
        Settings(environment="production", demo_mode=True)
