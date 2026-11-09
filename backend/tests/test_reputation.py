import uuid
from datetime import datetime, timedelta, timezone

from app.ai.reputation import (
    ALLOWED_REPUTATION_LABELS,
    coordinated_post_ids,
    public_escalation_urgency,
    reputation_signal_index,
)
from app.models import Complaint, SocialReceipt
from app.models.enums import Channel, IssueType, Sentiment, Severity
from tests.helpers import register


START = datetime(2026, 11, 6, 10, 0, tzinfo=timezone.utc)


def _session():
    from app.db.session import get_db
    from app.main import app

    generator = app.dependency_overrides[get_db]()
    return generator, next(generator)


def test_signal_index_is_balanced_and_high_reach_negative_posts_lower_it():
    balanced = (
        [{"flags": [], "score": 0.0} for _ in range(100)]
        + [{"flags": ["service_failure"], "score": 0.4} for _ in range(100)]
    )
    high_reach_negative = (
        [{"flags": [], "score": 0.0} for _ in range(100)]
        + [
            {"flags": ["service_failure", "high_reach"], "score": 0.6}
            for _ in range(90)
        ]
        + [{"flags": ["service_failure"], "score": 0.4} for _ in range(10)]
    )
    assert reputation_signal_index(balanced) == 50.0
    assert reputation_signal_index(high_reach_negative) < 35.0


def test_coordinated_pattern_requires_five_posts_and_three_authors():
    posts = [
        {
            "id": str(index),
            "text": "My transfer failed after debit, receiver still not credited",
            "received_at": START + timedelta(minutes=index),
            "author_ref_hash": f"author-{index % 3}",
        }
        for index in range(5)
    ]
    assert coordinated_post_ids(posts) == {str(index) for index in range(5)}
    assert coordinated_post_ids([{**post, "author_ref_hash": "author-1"} for post in posts]) == set()


def test_scam_allegation_with_high_reach_is_urgent():
    urgency, priority, requires_review = public_escalation_urgency(
        ["scam_allegation", "high_reach"], score=0.8, engagement=500
    )
    assert urgency == "urgent"
    assert priority == "urgent"
    assert requires_review is True


def test_reputation_summary_is_aggregated_masked_and_tenant_scoped(authed, client):
    headers = authed.headers["Authorization"]
    bank_id = uuid.UUID(authed.get("/api/v1/auth/me").json()["bank"]["id"])
    generator, db = _session()
    try:
        complaint = Complaint(
            bank_id=bank_id,
            channel=Channel.X,
            text="My account failed, please call [PHONE]",
            occurred_at=START,
            issue_type=IssueType.FAILED_TRANSFER,
            severity=Severity.HIGH,
            sentiment=Sentiment.NEGATIVE,
            is_fraud=False,
        )
        db.add(complaint)
        db.flush()
        db.add(
            SocialReceipt(
                bank_id=bank_id,
                platform="x",
                post_id="synthetic-post-1",
                complaint_id=complaint.id,
                matched_aliases=[],
                author_ref_hash="private-author-hash",
                public_metrics={"like_count": 250},
                reputation_flags=["service_failure", "high_reach"],
                reputation_score=0.5,
                received_at=START,
            )
        )
        db.commit()
    finally:
        db.close()
        generator.close()

    client.headers.pop("Authorization", None)
    assert client.get("/api/v1/ai/reputation/summary").status_code == 401
    client.headers["Authorization"] = headers
    response = authed.get(
        "/api/v1/ai/reputation/summary",
        params={"since": START.isoformat(), "until": (START + timedelta(days=1)).isoformat()},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert 0 <= body["reputation_signal_index"] <= 100
    assert body["posts_needing_review"][0]["priority"] in {"low", "normal", "high", "urgent"}
    assert "private-author-hash" not in response.text
    assert "author_ref_hash" not in body["posts_needing_review"][0]
    labels = set(body["flag_counts"]) | set(body["indicator_counts"])
    labels.update(item["label"] for item in body["top_repeated_themes"])
    assert labels <= ALLOWED_REPUTATION_LABELS
    assert authed.get(
        "/api/v1/ai/reputation/summary",
        params={"since": (START + timedelta(days=1)).isoformat(), "until": START.isoformat()},
    ).status_code == 422

    beta_headers, _ = register(client, bank="Beta Reputation Bank", email="reputation@beta.example")
    client.headers.update(beta_headers)
    beta_summary = client.get("/api/v1/ai/reputation/summary").json()
    assert beta_summary["posts_needing_review"] == []
    assert beta_summary["flag_counts"] == {}
