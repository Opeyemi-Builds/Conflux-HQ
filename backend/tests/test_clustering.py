import uuid
from datetime import datetime, timedelta, timezone

from app.core.config import get_settings
from app.models import Complaint, ComplaintCluster, Incident
from app.models.enums import Channel, IncidentStatus, IssueType, Severity, Sentiment
from tests.helpers import register


START = datetime(2026, 11, 6, 10, 0, tzinfo=timezone.utc)


def _session():
    from app.db.session import get_db
    from app.main import app

    generator = app.dependency_overrides[get_db]()
    return generator, next(generator)


def _add_complaint(db, bank_id, text, at, *, channel=Channel.IN_APP, region="Lagos", fraud=False):
    complaint = Complaint(
        bank_id=bank_id,
        channel=channel,
        text=text,
        occurred_at=at,
        issue_type=IssueType.FAILED_TRANSFER,
        payment_category="failed_transfer",
        classification_confidence=0.9,
        severity=Severity.HIGH,
        sentiment=Sentiment.NEGATIVE,
        is_fraud=fraud,
        routing_queue="fraud_security" if fraud else "standard",
        region=region,
    )
    db.add(complaint)
    return complaint


def _disable_ai(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "ai_provider", "gemini")
    monkeypatch.setattr(settings, "gemini_api_key", None)
    monkeypatch.setattr(settings, "anthropic_api_key", None)


def test_one_hundred_similar_posts_form_one_cluster_and_atm_is_separate(authed, monkeypatch):
    _disable_ai(monkeypatch)
    me = authed.get("/api/v1/auth/me").json()
    bank_id = uuid.UUID(me["bank"]["id"])
    generator, db = _session()
    try:
        db.add_all(
            _add_complaint(
                db,
                bank_id,
                "My transfer failed after debit, receiver not credited.",
                START + timedelta(seconds=index),
                channel=Channel.IN_APP if index % 2 == 0 else Channel.X,
                region="Lagos",
            )
            for index in range(100)
        )
        db.add(
            Complaint(
                bank_id=bank_id,
                channel=Channel.ATM if hasattr(Channel, "ATM") else Channel.IN_APP,
                text="ATM cash was not dispensed.",
                occurred_at=START + timedelta(minutes=5),
                issue_type=IssueType.CARD_ATM,
                payment_category="card_atm_failure",
                region="Abuja",
            )
        )
        db.commit()
    finally:
        db.close()
        generator.close()

    response = authed.post(
        "/api/v1/ai/clusters/refresh",
        json={"since": START.isoformat(), "until": (START + timedelta(minutes=30)).isoformat()},
    )
    assert response.status_code == 200, response.text
    assert response.json()["cluster_count"] == 1
    clusters = authed.get("/api/v1/ai/clusters", params={"min_count": 10}).json()
    assert clusters["total"] == 1
    assert clusters["items"][0]["complaint_count"] == 100
    assert clusters["items"][0]["label_method"] == "rules"


def test_pidgin_and_english_failure_phrases_cluster_together():
    from app.ai.clustering import cluster_complaints

    complaints = [
        {"id": "a", "text": "My transfer no go, money don enter nowhere", "payment_category": "failed_transfer"},
        {"id": "b", "text": "My transfer failed, receiver was not credited", "payment_category": "failed_transfer"},
    ]
    groups = cluster_complaints(complaints, similarity_threshold=0.35)
    assert len(groups) == 1
    assert len(groups[0]) == 2


def test_cluster_metadata_growth_and_related_incident(authed, monkeypatch):
    _disable_ai(monkeypatch)
    me = authed.get("/api/v1/auth/me").json()
    bank_id = uuid.UUID(me["bank"]["id"])
    generator, db = _session()
    try:
        incident = Incident(
            bank_id=bank_id,
            issue_type=IssueType.FAILED_TRANSFER,
            status=IncidentStatus.OPEN,
            started_at=START,
            complaint_count=10,
        )
        db.add(incident)
        db.flush()
        _add_complaint(db, bank_id, "Transfer failed, receiver not credited", START - timedelta(minutes=30))
        _add_complaint(db, bank_id, "Transfer failed, receiver not credited", START - timedelta(minutes=29))
        for index in range(10):
            _add_complaint(
                db,
                bank_id,
                "Transfer failed, receiver not credited",
                START + timedelta(seconds=index),
                channel=Channel.IN_APP if index < 6 else Channel.X,
                region="Lagos" if index < 7 else "Abuja",
                fraud=index < 2,
            )
        db.commit()
    finally:
        db.close()
        generator.close()

    response = authed.post(
        "/api/v1/ai/clusters/refresh",
        json={"since": START.isoformat(), "until": (START + timedelta(minutes=30)).isoformat()},
    )
    assert response.status_code == 200, response.text
    cluster = authed.get("/api/v1/ai/clusters").json()["items"][0]
    assert cluster["complaint_count"] == 10
    assert cluster["fraud_count"] == 2
    assert cluster["growth_rate"] == 5.0
    assert cluster["first_seen"].startswith("2026-11-06T10:00:00")
    assert cluster["last_seen"].startswith("2026-11-06T10:00:09")
    assert cluster["channels"] == {"in_app": 6, "x": 4}
    assert cluster["regions"] == {"Lagos": 7, "Abuja": 3}
    assert cluster["related_incident_id"] == str(incident.id)


def test_refresh_is_idempotent_filters_and_detail_samples(authed, monkeypatch):
    _disable_ai(monkeypatch)
    me = authed.get("/api/v1/auth/me").json()
    bank_id = uuid.UUID(me["bank"]["id"])
    generator, db = _session()
    try:
        db.add_all(
            _add_complaint(
                db, bank_id, "Transfer failed, receiver not credited", START + timedelta(seconds=index)
            )
            for index in range(10)
        )
        db.commit()
    finally:
        db.close()
        generator.close()

    payload = {"since": START.isoformat(), "until": (START + timedelta(minutes=30)).isoformat()}
    first = authed.post("/api/v1/ai/clusters/refresh", json=payload)
    second = authed.post("/api/v1/ai/clusters/refresh", json=payload)
    assert first.status_code == second.status_code == 200
    assert second.json()["cluster_count"] == 1
    filtered = authed.get("/api/v1/ai/clusters", params={"payment_category": "failed_transfer", "min_count": 10})
    assert filtered.status_code == 200 and filtered.json()["total"] == 1
    detail = authed.get(f"/api/v1/ai/clusters/{filtered.json()['items'][0]['id']}")
    assert detail.status_code == 200
    assert len(detail.json()["sample_complaints"]) == 5


def test_cluster_endpoints_auth_empty_state_and_tenant_isolation(authed, client):
    alpha_auth = authed.headers["Authorization"]
    client.headers.pop("Authorization", None)
    assert client.get("/api/v1/ai/clusters").status_code == 401
    client.headers["Authorization"] = alpha_auth
    assert authed.get("/api/v1/ai/clusters").json()["items"] == []

    beta_headers, _ = register(client, bank="Beta Clustering Bank", email="cluster@beta.example")
    client.headers.update(beta_headers)
    assert client.get("/api/v1/ai/clusters").json()["total"] == 0
