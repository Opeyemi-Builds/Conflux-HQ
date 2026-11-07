from datetime import datetime, timedelta, timezone
from decimal import Decimal

from app.ai.drafts import _grounded_or_fallback
from app.ai.evidence import rank_events
from app.models import AuditLog, Incident, Job, SystemEvent, Transaction
from app.models.enums import (
    DraftKind,
    EventType,
    IncidentStatus,
    IssueType,
    JobKind,
    JobStatus,
    ReversalStatus,
    TxnChannel,
    TxnStatus,
    TxnType,
)
from app.services.worker import drain_jobs, enqueue_job, process_next_job


def test_transactional_worker_end_to_end_pipeline(authed, client):
    """Ingest -> Drain -> Classify -> Detect Spike -> Investigate -> Draft -> Approve -> Outbox."""
    # 1. Ingest 12 unclassified Pidgin transfer complaints in the same 15-min bucket
    occurred = "2026-11-06T10:32:00Z"
    res = authed.post(
        "/api/v1/complaints/bulk",
        json={
            "complaints": [
                {
                    "channel": "in_app" if i % 2 == 0 else "x",
                    "text": "abeg my money don enter nowhere, failed transfer 50k",
                    "customer_ref": f"080300000{i % 4:02d}",
                    "region": "Lagos",
                    "occurred_at": occurred,
                }
                for i in range(12)
            ]
        },
    )
    assert res.status_code == 201

    # Jobs should be queued as pending before drain
    pending_jobs = authed.get("/api/v1/jobs", params={"status": "pending"}).json()
    assert len(pending_jobs) == 12
    assert all(j["kind"] == "classify_complaint" for j in pending_jobs)

    # 2. Drain the queue: should classify all 12, run spike detection, and run investigation + drafts
    drain_res = authed.post("/api/v1/jobs/drain", json={"limit": 100})
    assert drain_res.status_code == 200
    stats = drain_res.json()
    assert stats["completed"] >= 14  # 12 classify + 1 detect_spikes + 1 investigate_incident
    assert stats["dead_lettered"] == 0

    # 3. Verify incident was created, investigated, and drafts generated
    incidents = authed.get("/api/v1/incidents").json()
    assert len(incidents) == 1
    incident = incidents[0]
    assert incident["issue_type"] == "failed_transfer"
    assert incident["status"] == "awaiting_approval"
    assert incident["likely_cause"] is not None

    drafts = authed.get(f"/api/v1/ai/incidents/{incident['id']}/drafts").json()
    assert len(drafts) == 2

    # 4. Approve a draft -> enqueues transactional outbox job (dispatch_approval)
    draft_id = drafts[0]["id"]
    dec = authed.post(f"/api/v1/ai/drafts/{draft_id}/decision", json={"decision": "approved"})
    assert dec.status_code == 200

    outbox_jobs = authed.get("/api/v1/jobs", params={"kind": "dispatch_approval", "status": "pending"}).json()
    assert len(outbox_jobs) == 1

    # Drain outbox job
    drain2 = authed.post("/api/v1/jobs/drain").json()
    assert drain2["completed"] == 1

    # 5. Verify new analytics metrics (avg_time_to_detect_seconds & repeat_complaint_rate)
    summary = authed.get(
        "/api/v1/analytics/summary",
        params={"hours": 24, "at": "2026-11-06T11:00:00Z"},
    ).json()
    assert summary["avg_time_to_detect_seconds"] is not None
    assert summary["repeat_complaint_rate"] > 0.0


def test_job_idempotency_lease_recovery_and_dead_letter(authed, client):
    from app.db.session import get_db
    from app.main import app

    db_gen = app.dependency_overrides[get_db]()
    db = next(db_gen)
    try:
        me = authed.get("/api/v1/auth/me").json()
        import uuid
        bank_id = uuid.UUID(me["bank"]["id"])

        # Duplicate idempotency key returns the same job row
        j1 = enqueue_job(
            db,
            bank_id=bank_id,
            kind=JobKind.DETECT_SPIKES,
            payload={"simulate_failure": True},
            idempotency_key="test:fail:1",
            max_attempts=2,
        )
        db.commit()
        j2 = enqueue_job(
            db,
            bank_id=bank_id,
            kind=JobKind.DETECT_SPIKES,
            payload={"simulate_failure": True},
            idempotency_key="test:fail:1",
            max_attempts=2,
        )
        db.commit()
        assert j1.id == j2.id

        # Attempt 1 fails -> back to PENDING
        processed1 = process_next_job(db, bank_id=bank_id)
        assert processed1.status == JobStatus.PENDING
        assert processed1.attempts == 1
        assert "Simulated worker failure" in processed1.last_error

        # Attempt 2 fails -> transitions to DEAD_LETTER and logs audit entry
        processed2 = process_next_job(db, bank_id=bank_id)
        assert processed2.status == JobStatus.DEAD_LETTER
        assert processed2.attempts == 2

        dead_jobs = authed.get("/api/v1/jobs", params={"status": "dead_letter"}).json()
        assert any(j["id"] == str(j1.id) for j in dead_jobs)
    finally:
        db.close()


def test_dynamic_cause_scoring_and_transaction_matching(authed):
    from app.db.session import get_db
    from app.main import app
    import uuid

    me = authed.get("/api/v1/auth/me").json()
    bank_id = uuid.UUID(me["bank"]["id"])

    # Create release event (12m before spike), decoy maintenance (6h before), and failed txns
    spike_start = datetime(2026, 11, 6, 10, 0, tzinfo=timezone.utc)
    db_gen = app.dependency_overrides[get_db]()
    db = next(db_gen)
    try:
        db.add_all([
            SystemEvent(
                bank_id=bank_id,
                event_type=EventType.RELEASE,
                component="transfer-service",
                version="v4.2.1",
                description="App transfer release on demo-switch-a",
                starts_at=spike_start - timedelta(minutes=12),
            ),
            SystemEvent(
                bank_id=bank_id,
                event_type=EventType.MAINTENANCE,
                component="email-service",
                description="SYNTHETIC DECOY: unrelated email maintenance",
                starts_at=spike_start - timedelta(hours=5),
            ),
            Transaction(
                bank_id=bank_id,
                reference="TXN-MATCH-1",
                txn_type=TxnType.TRANSFER,
                txn_channel=TxnChannel.APP,
                status=TxnStatus.FAILED,
                reversal_status=ReversalStatus.PENDING,
                processor="demo-switch-a",
                amount=Decimal("25000.00"),
                region="Lagos",
                occurred_at=spike_start + timedelta(minutes=2),
            ),
        ])
        db.commit()
    finally:
        db.close()

    # Ingest 12 complaints with mentioned_amount=25000 at 10:03
    for i in range(12):
        c = authed.post(
            "/api/v1/complaints",
            json={
                "channel": "in_app",
                "text": "my transfer of 25000 failed on app",
                "region": "Lagos",
                "issue_type": "failed_transfer",
                "occurred_at": (spike_start + timedelta(minutes=3, seconds=i)).isoformat(),
            },
        ).json()
        if i == 0:
            authed.patch(
                f"/api/v1/complaints/{c['id']}/classification",
                json={
                    "issue_type": "failed_transfer",
                    "severity": "high",
                    "sentiment": "negative",
                    "mentioned_amount": "25000.00",
                    "confidence": 0.9,
                },
            )

    detected = authed.post("/api/v1/incidents/detect", json={"now": "2026-11-06T10:14:00Z"}).json()
    assert len(detected) == 1
    incident_id = detected[0]["id"]

    inv = authed.post(f"/api/v1/ai/incidents/{incident_id}/investigate").json()
    assert "v4.2.1" in inv["likely_cause"]
    assert inv["cause_confidence"] >= 0.75
    # Because a complaint was matched to an unreversed failed transaction, 3 drafts (including reversal_request) are created
    drafts = authed.get(f"/api/v1/ai/incidents/{incident_id}/drafts").json()
    kinds = {d["kind"] for d in drafts}
    assert kinds == {"customer_message", "it_ticket", "reversal_request"}


def test_grounding_verifier_blocks_hallucinated_numbers_in_drafts(authed, monkeypatch):
    from app.db.session import get_db
    from app.main import app
    import uuid

    me = authed.get("/api/v1/auth/me").json()
    bank_id = uuid.UUID(me["bank"]["id"])
    incident_id = uuid.uuid4()

    # Simulate an LLM draft that hallucinates an ungrounded number ("999999")
    monkeypatch.setattr("app.ai.drafts._llm_draft_text", lambda prompt_file, facts: "We will refund 999999 naira in 5 minutes.")

    db_gen = app.dependency_overrides[get_db]()
    db = next(db_gen)
    try:
        out = _grounded_or_fallback(
            db,
            bank_id,
            incident_id,
            DraftKind.CUSTOMER_MESSAGE,
            "draft_message.md",
            "Fallback safe template with 12 complaints.",
            {"complaint_count": 12},
            "worker",
        )
        db.commit()
        assert out == "Fallback safe template with 12 complaints."
        audit_entry = db.query(AuditLog).filter(AuditLog.action == "draft_grounding_blocked").first()
        assert audit_entry is not None
        assert "999999" in audit_entry.details["ungrounded_numbers"]
    finally:
        db.close()


def test_golden_100_evaluation_endpoint(authed):
    res = authed.get("/api/v1/ai/evaluate", params={"mode": "rules"})
    assert res.status_code == 200
    body = res.json()
    assert body["total"] == 100
    assert body["overall_accuracy"] >= 0.95
    assert body["fraud_recall"] == 1.0
    assert set(body["accuracy_by_language"]) == {"english", "pidgin", "yoruba_mix", "hausa_mix", "igbo_mix"}


