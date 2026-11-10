"""Unit and integration tests for bank complaint ingestion, connector auth, and idempotency."""
import uuid
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.deps import get_db
from app.core.config import get_settings
from app.db.base import Base
from app.main import app
from app.models import Bank, Complaint, Job
from app.models.enums import BankStatus, Channel, JobKind
from app.models.ingestion import ComplaintReceipt, IngestionConnector
from app.services.bank_intake import generate_connector_token


@pytest.fixture()
def test_setup():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    with Session() as db:
        bank_a = Bank(id=uuid.uuid4(), name="Access Bank Plc", slug="access", contact_email="support@access.example", status=BankStatus.ACTIVE)
        bank_b = Bank(id=uuid.uuid4(), name="United Bank for Africa", slug="uba", contact_email="support@uba.example", status=BankStatus.ACTIVE)
        db.add_all([bank_a, bank_b])
        db.commit()

        # Provision connectors for Bank A and Bank B
        pref_a, token_a, hash_a = generate_connector_token()
        conn_a = IngestionConnector(
            bank_id=bank_a.id,
            name="Access CRM Simulator",
            source_system="zendesk_sim",
            key_prefix=pref_a,
            key_hash=hash_a,
            status="active",
        )

        pref_b, token_b, hash_b = generate_connector_token()
        conn_b = IngestionConnector(
            bank_id=bank_b.id,
            name="UBA CRM Simulator",
            source_system="crm_sim",
            key_prefix=pref_b,
            key_hash=hash_b,
            status="active",
        )
        db.add_all([conn_a, conn_b])
        db.commit()
        bank_a_id = bank_a.id
        bank_b_id = bank_b.id
        conn_a_id = conn_a.id

    def override_db():
        with Session() as s:
            yield s

    app.dependency_overrides[get_db] = override_db
    client = TestClient(app)

    yield {
        "client": client,
        "token_a": token_a,
        "token_b": token_b,
        "conn_a_id": conn_a_id,
        "bank_a_id": bank_a_id,
        "bank_b_id": bank_b_id,
        "Session": Session,
    }

    app.dependency_overrides.clear()
    Base.metadata.drop_all(engine)
    engine.dispose()


def test_auth_rejection_cases(test_setup):
    client = test_setup["client"]

    # 1. Missing Authorization header
    resp = client.post("/api/v1/ingestion/complaints", json={})
    assert resp.status_code == 401

    # 2. Malformed token prefix
    resp = client.post("/api/v1/ingestion/complaints", json={}, headers={"Authorization": "Bearer invalid_token"})
    assert resp.status_code == 401

    # 3. Wrong secret
    resp = client.post("/api/v1/ingestion/complaints", json={}, headers={"Authorization": "Bearer cfx_conn_0123456789ab_wrongsecret"})
    assert resp.status_code == 401


def test_validation_rules_and_pii_masking(test_setup):
    client = test_setup["client"]
    token = test_setup["token_a"]
    headers = {"Authorization": f"Bearer {token}"}

    payload = {
        "source_system": "zendesk_sim",
        "external_id": "VAL-001",
        "channel": "call_center",
        "occurred_at": datetime.now(timezone.utc).isoformat(),
        "text": "Debited ₦25,000 twice on ATM card 5399830000000008, phone 08031234567, email lagos@trader.com",
        "customer_ref": "08031234567",
        "payment_reference": "TRF-20261109-0001",
        "amount": "25000.02",
        "currency": "NGN",
        "synthetic": True,
    }

    resp = client.post("/api/v1/ingestion/complaints", json=payload, headers=headers)
    assert resp.status_code == 202, resp.text
    data = resp.json()
    assert data["duplicate"] is False
    assert data["processing_status"] == "queued"

    # Verify PII masking in database
    Session = test_setup["Session"]
    with Session() as db:
        complaint = db.get(Complaint, uuid.UUID(data["complaint_id"]))
        assert complaint is not None
        assert "[PHONE]" in complaint.text and "08031234567" not in complaint.text
        assert "[CARD]" in complaint.text and "5399830000000008" not in complaint.text
        assert "[EMAIL]" in complaint.text and "lagos@trader.com" not in complaint.text
        assert complaint.customer_ref.startswith("cust_")
        assert complaint.payment_reference == "TRF-20261109-0001"

        # Verify atomic job enqueued
        job = db.scalar(select(Job).where(Job.kind == JobKind.CLASSIFY_COMPLAINT, Job.bank_id == test_setup["bank_a_id"]))
        assert job is not None
        assert job.payload["complaint_id"] == str(complaint.id)


def test_rejection_of_social_channels_and_float_amounts(test_setup):
    client = test_setup["client"]
    headers = {"Authorization": f"Bearer {test_setup['token_a']}"}

    # Social channels must be redirected to /social/events
    bad_channel = {
        "source_system": "zendesk_sim",
        "external_id": "REJ-01",
        "channel": "x",
        "occurred_at": datetime.now(timezone.utc).isoformat(),
        "text": "Transfer failed",
    }
    resp = client.post("/api/v1/ingestion/complaints", json=bad_channel, headers=headers)
    assert resp.status_code == 422
    assert "Social media events must be delivered to /api/v1/social/events" in resp.text

    # Float amounts or invalid decimals must be rejected
    bad_amount = {
        "source_system": "zendesk_sim",
        "external_id": "REJ-02",
        "channel": "in_app",
        "occurred_at": datetime.now(timezone.utc).isoformat(),
        "text": "Transfer failed",
        "amount": "25000.005",  # 3 decimal places
    }
    resp = client.post("/api/v1/ingestion/complaints", json=bad_amount, headers=headers)
    assert resp.status_code == 422


def test_idempotent_replay_and_conflict_rejection(test_setup):
    client = test_setup["client"]
    token = test_setup["token_a"]
    headers = {"Authorization": f"Bearer {token}"}

    payload = {
        "source_system": "zendesk_sim",
        "external_id": "TCK-IDEM-99",
        "channel": "in_app",
        "occurred_at": datetime.now(timezone.utc).isoformat(),
        "text": "Customer states transfer of ₦18,000.05 to UBA failed.",
        "payment_reference": "TRF-20261109-0005",
        "amount": "18000.05",
        "currency": "NGN",
    }

    # 1. First submission -> 202
    resp1 = client.post("/api/v1/ingestion/complaints", json=payload, headers=headers)
    assert resp1.status_code == 202
    res1_data = resp1.json()

    # 2. Identical Replay -> 200 OK (duplicate: true, no new complaint)
    resp2 = client.post("/api/v1/ingestion/complaints", json=payload, headers=headers)
    assert resp2.status_code == 200
    res2_data = resp2.json()
    assert res2_data["duplicate"] is True
    assert res2_data["complaint_id"] == res1_data["complaint_id"]
    assert res2_data["receipt_id"] == res1_data["receipt_id"]

    # 3. Conflicting Replay (modified text) -> 409 Conflict
    drift_payload = dict(payload)
    drift_payload["text"] = "Customer changed complaint: actually ₦40,000 was debited!"
    resp3 = client.post("/api/v1/ingestion/complaints", json=drift_payload, headers=headers)
    assert resp3.status_code == 409
    assert resp3.json()["detail"]["error"] == "external_id_conflict"


def test_cross_bank_isolation(test_setup):
    client = test_setup["client"]
    headers_a = {"Authorization": f"Bearer {test_setup['token_a']}"}
    headers_b = {"Authorization": f"Bearer {test_setup['token_b']}"}

    payload = {
        "source_system": "zendesk_sim",
        "external_id": "SHARED-ID-100",
        "channel": "in_app",
        "occurred_at": datetime.now(timezone.utc).isoformat(),
        "text": "Bank transfer timed out",
    }

    # Bank A ingests SHARED-ID-100
    resp_a = client.post("/api/v1/ingestion/complaints", json=payload, headers=headers_a)
    assert resp_a.status_code == 202

    # Bank B ingests identical external_id -> must be 202 (not 200 or 409) because identity is scoped by (bank_id, connector_id, external_id)
    resp_b = client.post("/api/v1/ingestion/complaints", json=payload, headers=headers_b)
    assert resp_b.status_code == 202
    assert resp_a.json()["complaint_id"] != resp_b.json()["complaint_id"]


def test_connector_revocation(test_setup):
    client = test_setup["client"]
    token = test_setup["token_a"]
    headers = {"Authorization": f"Bearer {token}"}

    # Ingestion works initially
    payload = {
        "source_system": "zendesk_sim",
        "external_id": "REV-01",
        "channel": "in_app",
        "occurred_at": datetime.now(timezone.utc).isoformat(),
        "text": "Test complaint",
    }
    assert client.post("/api/v1/ingestion/complaints", json=payload, headers=headers).status_code == 202

    # Revoke connector
    Session = test_setup["Session"]
    with Session() as db:
        connector = db.get(IngestionConnector, test_setup["conn_a_id"])
        connector.status = "revoked"
        db.commit()

    # Next attempt is rejected with 403 Forbidden
    payload["external_id"] = "REV-02"
    resp = client.post("/api/v1/ingestion/complaints", json=payload, headers=headers)
    assert resp.status_code == 403
    assert "revoked" in resp.json()["detail"]


def test_client_bank_id_injection_forbidden(test_setup):
    """Clients cannot forge or inject bank_id; extra fields return 422."""
    client = test_setup["client"]
    token = test_setup["token_a"]
    headers = {"Authorization": f"Bearer {token}"}

    payload = {
        "source_system": "zendesk_sim",
        "external_id": "FORGE-01",
        "bank_id": str(uuid.uuid4()),
        "channel": "in_app",
        "occurred_at": datetime.now(timezone.utc).isoformat(),
        "text": "Customer tries to claim another bank id",
    }
    resp = client.post("/api/v1/ingestion/complaints", json=payload, headers=headers)
    assert resp.status_code == 422
    assert "extra_forbidden" in resp.text


def test_timestamp_and_amount_currency_constraints(test_setup):
    """Enforce timezone awareness, 5-minute future limit, and paired amount/currency."""
    client = test_setup["client"]
    token = test_setup["token_a"]
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Naive timestamp rejected
    naive_payload = {
        "source_system": "zendesk_sim",
        "external_id": "TIME-01",
        "channel": "in_app",
        "occurred_at": "2026-11-09T10:00:00",  # no timezone info
        "text": "Naive time",
    }
    resp = client.post("/api/v1/ingestion/complaints", json=naive_payload, headers=headers)
    assert resp.status_code == 422
    assert "timezone_aware" in resp.text

    # 2. Future timestamp (> 5 minutes ahead) rejected
    from datetime import timedelta
    future_time = (datetime.now(timezone.utc) + timedelta(minutes=15)).isoformat()
    future_payload = {
        "source_system": "zendesk_sim",
        "external_id": "TIME-02",
        "channel": "in_app",
        "occurred_at": future_time,
        "text": "Time from tomorrow",
    }
    resp = client.post("/api/v1/ingestion/complaints", json=future_payload, headers=headers)
    assert resp.status_code == 422
    assert "cannot be more than 5 minutes in the future" in resp.text

    # 3. Amount provided without currency rejected
    no_curr = {
        "source_system": "zendesk_sim",
        "external_id": "CURR-01",
        "channel": "in_app",
        "occurred_at": datetime.now(timezone.utc).isoformat(),
        "text": "Failed transfer",
        "amount": "25000.00",
        "currency": None,
    }
    resp = client.post("/api/v1/ingestion/complaints", json=no_curr, headers=headers)
    assert resp.status_code == 422
    assert "Currency is required when amount is provided" in resp.text

    # 4. Currency provided without amount rejected
    no_amt = {
        "source_system": "zendesk_sim",
        "external_id": "CURR-02",
        "channel": "in_app",
        "occurred_at": datetime.now(timezone.utc).isoformat(),
        "text": "Failed transfer",
        "amount": None,
        "currency": "NGN",
    }
    resp = client.post("/api/v1/ingestion/complaints", json=no_amt, headers=headers)
    assert resp.status_code == 422
    assert "Amount is required when currency is provided" in resp.text


def test_text_boundary_and_control_chars_rejected(test_setup):
    """Enforce text length bounds and reject invalid control characters."""
    client = test_setup["client"]
    token = test_setup["token_a"]
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Null byte in text
    null_payload = {
        "source_system": "zendesk_sim",
        "external_id": "TXT-01",
        "channel": "in_app",
        "occurred_at": datetime.now(timezone.utc).isoformat(),
        "text": "Customer note with \x00 null byte",
    }
    assert client.post("/api/v1/ingestion/complaints", json=null_payload, headers=headers).status_code == 422

    # 2. Oversized text (> 5000 characters)
    huge_payload = {
        "source_system": "zendesk_sim",
        "external_id": "TXT-02",
        "channel": "in_app",
        "occurred_at": datetime.now(timezone.utc).isoformat(),
        "text": "A" * 5001,
    }
    assert client.post("/api/v1/ingestion/complaints", json=huge_payload, headers=headers).status_code == 422


def test_transaction_rollback_without_orphan_records(test_setup, monkeypatch):
    """A database or worker enqueue failure rolls back completely without leaving orphan complaints or receipts."""
    client = test_setup["client"]
    token = test_setup["token_a"]
    headers = {"Authorization": f"Bearer {token}"}

    def failing_enqueue(db, bank_id, complaint):
        raise RuntimeError("Simulated transient queue explosion")

    monkeypatch.setattr("app.services.bank_intake._enqueue_for_complaint", failing_enqueue)

    payload = {
        "source_system": "zendesk_sim",
        "external_id": "FAIL-01",
        "channel": "in_app",
        "occurred_at": datetime.now(timezone.utc).isoformat(),
        "text": "This complaint must roll back cleanly",
    }

    with pytest.raises(RuntimeError, match="Simulated transient queue explosion"):
        client.post("/api/v1/ingestion/complaints", json=payload, headers=headers)

    Session = test_setup["Session"]
    with Session() as db:
        # Zero complaints or receipts persisted
        assert db.scalar(select(Complaint).where(Complaint.text.contains("This complaint must roll back cleanly"))) is None
        assert db.scalar(select(ComplaintReceipt).where(ComplaintReceipt.external_id == "FAIL-01")) is None


def test_worker_end_to_end_classification_and_complaint_query(test_setup):
    """Ingested complaint is classified by worker, queryable with payment_reference, and reports status='classified'."""
    from app.services.worker import drain_jobs

    client = test_setup["client"]
    token = test_setup["token_a"]
    headers = {"Authorization": f"Bearer {token}"}

    payload = {
        "source_system": "zendesk_sim",
        "external_id": "E2E-001",
        "channel": "call_center",
        "occurred_at": datetime.now(timezone.utc).isoformat(),
        "text": "Customer called about double debit of ₦20,000.00 at ATM. Please reverse funds.",
        "payment_reference": "TRF-E2E-9999",
        "amount": "20000.00",
        "currency": "NGN",
    }

    resp = client.post("/api/v1/ingestion/complaints", json=payload, headers=headers)
    assert resp.status_code == 202
    complaint_id = resp.json()["complaint_id"]
    receipt_id = resp.json()["receipt_id"]

    Session = test_setup["Session"]
    with Session() as db:
        # Before worker runs, processing_status is queued
        dup_resp = client.post("/api/v1/ingestion/complaints", json=payload, headers=headers)
        assert dup_resp.status_code == 200
        assert dup_resp.json()["processing_status"] == "queued"

        # Run worker
        drain_res = drain_jobs(db, bank_id=test_setup["bank_a_id"])
        assert drain_res["processed"] >= 1
        assert drain_res["completed"] >= 1

        # Complaint is now classified in DB and retains payment_reference
        complaint = db.get(Complaint, uuid.UUID(complaint_id))
        assert complaint.issue_type is not None
        assert complaint.payment_reference == "TRF-E2E-9999"

        # Duplicate replay now reflects classified status
        post_worker_dup = client.post("/api/v1/ingestion/complaints", json=payload, headers=headers)
        assert post_worker_dup.status_code == 200
        assert post_worker_dup.json()["processing_status"] == "classified"


def test_worker_failure_preserves_complaint(test_setup, monkeypatch):
    """When the worker or classifier fails, the accepted complaint is never deleted or corrupted."""
    from app.models.enums import JobStatus
    from app.services.worker import claim_next_job, process_next_job

    client = test_setup["client"]
    token = test_setup["token_a"]
    headers = {"Authorization": f"Bearer {token}"}

    payload = {
        "source_system": "zendesk_sim",
        "external_id": "PRESERVE-01",
        "channel": "in_app",
        "occurred_at": datetime.now(timezone.utc).isoformat(),
        "text": "App login crashes every time",
    }
    resp = client.post("/api/v1/ingestion/complaints", json=payload, headers=headers)
    assert resp.status_code == 202
    complaint_id = resp.json()["complaint_id"]

    # Mock classifier to crash
    def crash_classify(*args, **kwargs):
        raise ValueError("Model inference outage")

    monkeypatch.setattr("app.services.worker.ai_classify_text", crash_classify)

    Session = test_setup["Session"]
    with Session() as db:
        job = claim_next_job(db, bank_id=test_setup["bank_a_id"])
        assert job is not None
        process_next_job(db, bank_id=test_setup["bank_a_id"])

        # Complaint remains intact and queryable!
        complaint = db.get(Complaint, uuid.UUID(complaint_id))
        assert complaint is not None
        assert "App login crashes" in complaint.text


def test_concurrent_duplicate_delivery(test_setup, monkeypatch):
    """Simulate race condition where fast-path check misses a concurrent insert.
    
    When two requests race past the fast-path check, the second encounters an IntegrityError
    on the database UniqueConstraint. The savepoint rolls back and resolves it cleanly as a 200 duplicate.
    """
    client = test_setup["client"]
    token = test_setup["token_a"]
    headers = {"Authorization": f"Bearer {token}"}

    payload = {
        "source_system": "zendesk_sim",
        "external_id": "RACE-COND-001",
        "channel": "in_app",
        "occurred_at": datetime.now(timezone.utc).isoformat(),
        "text": "Concurrent debit test",
        "amount": "5000.00",
        "currency": "NGN",
    }

    # 1. Normal first delivery -> 202
    resp1 = client.post("/api/v1/ingestion/complaints", json=payload, headers=headers)
    assert resp1.status_code == 202

    # 2. Simulate the race condition:
    # A concurrent request races past the fast path (fast-path returns None).
    # It attempts to insert, triggering IntegrityError on (bank_id, connector_id, external_id).
    from app.services import bank_intake
    orig_compute_hash = bank_intake.compute_canonical_content_hash

    call_count = 0
    from sqlalchemy.orm import Session
    orig_scalar = Session.scalar

    def mocked_scalar(self, statement, *args, **kwargs):
        nonlocal call_count
        # On the very first check in bank_intake (the fast path), return None to simulate race
        if "FROM complaint_receipts" in str(statement) and call_count == 0:
            call_count += 1
            return None
        return orig_scalar(self, statement, *args, **kwargs)

    monkeypatch.setattr(Session, "scalar", mocked_scalar)

    # The racing request attempts insert, hits DB UniqueConstraint, catches IntegrityError,
    # rolls back savepoint, finds the committed record, and returns 200 OK duplicate!
    resp2 = client.post("/api/v1/ingestion/complaints", json=payload, headers=headers)
    assert resp2.status_code == 200
    assert resp2.json()["duplicate"] is True
    assert resp2.json()["complaint_id"] == resp1.json()["complaint_id"]

    # Verify database has strictly 1 receipt and 1 complaint
    SessionLocal = test_setup["Session"]
    with SessionLocal() as db:
        receipts = db.scalars(select(ComplaintReceipt).where(ComplaintReceipt.external_id == "RACE-COND-001")).all()
        assert len(receipts) == 1


def test_inactive_bank_blocked_and_staff_token_rejected(test_setup):
    """Suspended banks and staff JWT tokens cannot call the ingestion intake endpoint."""
    client = test_setup["client"]
    token = test_setup["token_a"]

    # 1. Staff token instead of connector token
    staff_token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.e30.fake"
    resp = client.post(
        "/api/v1/ingestion/complaints",
        json={"source_system": "sim", "external_id": "X", "channel": "in_app", "occurred_at": datetime.now(timezone.utc).isoformat(), "text": "Hi"},
        headers={"Authorization": f"Bearer {staff_token}"},
    )
    assert resp.status_code == 401

    # 2. Suspended bank
    Session = test_setup["Session"]
    with Session() as db:
        bank = db.get(Bank, test_setup["bank_a_id"])
        bank.status = BankStatus.SUSPENDED
        db.commit()

    resp = client.post(
        "/api/v1/ingestion/complaints",
        json={"source_system": "sim", "external_id": "SUSP-01", "channel": "in_app", "occurred_at": datetime.now(timezone.utc).isoformat(), "text": "Hi"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403
    assert "suspended" in resp.json()["detail"]


def test_admin_connector_lifecycle_and_receipt_api(test_setup):
    """An authenticated bank admin can create connectors, list them, revoke them, and read receipts."""
    from tests.helpers import make_token
    from app.models.bank import Profile
    from app.models.enums import UserRole, MemberStatus

    admin_id = uuid.uuid4()
    Session = test_setup["Session"]
    with Session() as db:
        admin_profile = Profile(
            id=admin_id,
            bank_id=test_setup["bank_a_id"],
            email="admin@access.example",
            full_name="Ada Admin",
            role=UserRole.BANK_ADMIN,
            status=MemberStatus.ACTIVE,
        )
        db.add(admin_profile)
        db.commit()

    admin_token = make_token(str(admin_id), "admin@access.example")
    admin_headers = {"Authorization": f"Bearer {admin_token}"}
    client = test_setup["client"]

    # 1. Admin creates a connector via API
    create_resp = client.post(
        "/api/v1/ingestion/connectors",
        json={"name": "Core Banking CRM", "source_system": "core_crm", "synthetic": True},
        headers=admin_headers,
    )
    assert create_resp.status_code == 201, create_resp.text
    created_data = create_resp.json()
    new_token = created_data["token"]
    connector_id = created_data["id"]
    assert new_token.startswith("cfx_conn_")

    # 2. List connectors
    list_resp = client.get("/api/v1/ingestion/connectors", headers=admin_headers)
    assert list_resp.status_code == 200
    connectors = list_resp.json()
    assert any(c["id"] == connector_id for c in connectors)

    # 3. Use newly created connector token to ingest a ticket
    ticket_payload = {
        "source_system": "core_crm",
        "external_id": "CRM-TICKET-001",
        "channel": "in_app",
        "occurred_at": datetime.now(timezone.utc).isoformat(),
        "text": "Transfer of ₦50,000 to Zenith Bank failed.",
        "payment_reference": "TRF-ZEN-8800",
        "amount": "50000.00",
        "currency": "NGN",
    }
    ingest_resp = client.post(
        "/api/v1/ingestion/complaints",
        json=ticket_payload,
        headers={"Authorization": f"Bearer {new_token}"},
    )
    assert ingest_resp.status_code == 202
    receipt_id = ingest_resp.json()["receipt_id"]

    # 4. Read receipts via API
    receipts_resp = client.get("/api/v1/ingestion/receipts?payment_reference=TRF-ZEN-8800", headers=admin_headers)
    assert receipts_resp.status_code == 200
    receipts = receipts_resp.json()
    assert len(receipts) == 1
    assert receipts[0]["id"] == receipt_id
    assert receipts[0]["external_id"] == "CRM-TICKET-001"

    # Single receipt read
    single_resp = client.get(f"/api/v1/ingestion/receipts/{receipt_id}", headers=admin_headers)
    assert single_resp.status_code == 200
    assert single_resp.json()["id"] == receipt_id

    # 5. Revoke connector via API
    revoke_resp = client.post(f"/api/v1/ingestion/connectors/{connector_id}/revoke", headers=admin_headers)
    assert revoke_resp.status_code == 200
    assert revoke_resp.json()["status"] == "revoked"

    # Next attempt with revoked token is rejected
    ticket_payload["external_id"] = "CRM-TICKET-002"
    blocked_resp = client.post(
        "/api/v1/ingestion/complaints",
        json=ticket_payload,
        headers={"Authorization": f"Bearer {new_token}"},
    )
    assert blocked_resp.status_code == 403
    assert "revoked" in blocked_resp.json()["detail"]
