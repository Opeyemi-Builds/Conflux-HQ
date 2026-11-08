from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.routes import auth, social
from app.core.config import get_settings
from app.db.base import Base
from app.db.session import get_db
from app.models import Bank, Complaint, SocialReceipt
from app.services.demo_auth import DEMO_BANK_ID

SECRET = "social-demo-test-secret-at-least-thirty-two-characters"
ADAPTER = "social-adapter-test-secret-at-least-thirty-two-characters"


def setup(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "demo_mode", True)
    monkeypatch.setattr(settings, "demo_token_secret", SECRET)
    monkeypatch.setattr(settings, "social_adapter_token", ADAPTER)
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine, expire_on_commit=False)

    def database():
        with sessions() as db:
            yield db

    app = FastAPI()
    app.include_router(auth.demo_router, prefix="/api/v1/auth")
    app.include_router(social.router, prefix="/api/v1")
    app.dependency_overrides[get_db] = database
    client = TestClient(app)
    client.headers["Authorization"] = "Bearer " + client.post("/api/v1/auth/login", json={
        "username": "Zymic Bank", "password": "123"}).json()["access_token"]
    return client, sessions, engine


def event(post_id, text):
    return {"platform": "x", "post_id": post_id, "text": text,
            "occurred_at": "2026-11-06T10:12:00Z",
            "source_url": f"https://x.com/customer/status/{post_id}",
            "author_ref": "customer@example.com", "region": "Lagos"}


def test_alias_configuration_and_tenant_safe_intake(monkeypatch):
    client, sessions, engine = setup(monkeypatch)
    try:
        aliases = client.get("/api/v1/social/aliases")
        assert aliases.status_code == 200
        assert {a["value"] for a in aliases.json()["items"]} >= {"zymic bank"}
        invalid = client.put("/api/v1/social/aliases", json={"aliases": [
            {"value": "same", "kind": "name"}, {"value": " SAME ", "kind": "name"}]})
        assert invalid.status_code == 422
        configured = client.put("/api/v1/social/aliases", json={"aliases": [
            {"value": "Zymic Bank", "kind": "name"},
            {"value": "@zymicbank", "kind": "handle", "platform": "x"}]})
        assert configured.status_code == 200
        assert client.post("/api/v1/social/events", json=event("p-unauth", "Zymic Bank debited me twice")).status_code == 401
        client.headers["Authorization"] = "Bearer " + ADAPTER
        ambiguous = client.post("/api/v1/social/events", json=event("p-amb", "Zymic Bank, Access Bank and UBA all failed my transfer"))
        # Only the configured Zymic identity exists in this demo DB, so it is a unique match.
        assert ambiguous.status_code == 202 and ambiguous.json()["accepted"] is True
        first = client.post("/api/v1/social/events", json=event("p-1", "@zymicbank debited me twice, call 08031234567"))
        assert first.status_code == 202
        body = first.json()
        assert body["issue_type"] == "double_debit" and body["channel"] == "x"
        assert body["analysis_method"] == "demo_rules_v2" and body["synthetic"] is False
        duplicate = client.post("/api/v1/social/events", json=event("p-1", "@zymicbank another different text"))
        assert duplicate.json()["duplicate"] is True
        unmatched = client.post("/api/v1/social/events", json=event("p-no", "I need access to my account"))
        assert unmatched.json()["reason"] == "no_bank_match"
        with sessions() as db:
            assert db.query(Complaint).count() == 2
            assert db.query(SocialReceipt).count() == 2
            complaint = db.query(Complaint).filter(Complaint.text.contains("[PHONE]")).one()
            assert "08031234567" not in complaint.text
            assert complaint.customer_ref.startswith("cust_")
            assert complaint.bank_id == DEMO_BANK_ID
    finally:
        engine.dispose()


def test_matching_rejects_ambiguous_bank_and_generic_access(monkeypatch):
    client, sessions, engine = setup(monkeypatch)
    try:
        with sessions() as db:
            other = Bank(name="Access Bank", slug="access", contact_email="access@example.com")
            db.add(other)
            db.commit()
            from app.models import BankAlias
            db.add_all([
                BankAlias(bank_id=other.id, value="access bank", kind="name"),
                BankAlias(bank_id=other.id, value="access", kind="contextual"),
            ])
            db.commit()
        client.get("/api/v1/social/aliases")
        client.headers["Authorization"] = "Bearer " + ADAPTER
        generic = client.post("/api/v1/social/events", json=event("g", "I need access to my account"))
        assert generic.json()["reason"] == "no_bank_match"
        ambiguous = client.post("/api/v1/social/events", json=event("a", "Zymic Bank and Access Bank both failed my transfer"))
        assert ambiguous.json()["reason"] == "ambiguous_bank_match"
    finally:
        engine.dispose()


def test_monitoring_discovery_and_non_demo_delivery(monkeypatch):
    client, sessions, engine = setup(monkeypatch)
    try:
        assert client.get("/api/v1/social/monitoring-rules").status_code == 401
        client.headers["Authorization"] = "Bearer " + ADAPTER
        rules = client.get("/api/v1/social/monitoring-rules").json()
        assert rules["items"][0]["bank_id"] == str(DEMO_BANK_ID)
        assert rules["items"][0]["aliases"][0]["value"] == "zymic bank"
        assert client.get("/api/v1/social/monitoring-rules?limit=0").status_code == 422
        monkeypatch.setattr(get_settings(), "demo_mode", False)
        response = client.post("/api/v1/social/events", json=event("live", "Zymic Bank transfer failed"))
        assert response.status_code == 202 and response.json()["accepted"]
        assert response.json()["synthetic"] is False
        monkeypatch.setattr(get_settings(), "social_adapter_token", "")
        assert client.get("/api/v1/social/monitoring-rules").status_code == 503
    finally:
        engine.dispose()


def test_bad_adapter_secret_and_urls_rejected(monkeypatch):
    client, _, engine = setup(monkeypatch)
    try:
        client.headers["Authorization"] = "Bearer wrong"
        assert client.post("/api/v1/social/events", json=event("x", "@zymicbank failed transfer")).status_code == 401
        client.headers["Authorization"] = "Bearer " + ADAPTER
        invalid = event("unsafe", "@zymicbank failed transfer")
        invalid["source_url"] = "https://evil.test/x"
        assert client.post("/api/v1/social/events", json=invalid).status_code == 422
    finally:
        engine.dispose()
