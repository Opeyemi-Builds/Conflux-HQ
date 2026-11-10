from datetime import datetime, timedelta, timezone
from decimal import Decimal
import hashlib
import hmac
import json
import uuid

import httpx
import pytest

from app.adapters.xtradot_client import (
    XtradotAPIError,
    XtradotClient,
    XtradotConfigurationError,
)
from app.adapters.xtradot_schemas import PaymentEvidenceEvent
from app.adapters.xtradot_webhooks import (
    WebhookVerificationError,
    decode_webhook_body,
    verify_webhook_signature,
)
from app.api.routes import forge_webhooks
from app.db.base import Base
from app.db.session import get_db
from app.models.bank import Bank
from app.models.enums import BankStatus
from app.models.xtradot_webhook import XtradotWebhookReceipt
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from app.services.payment_evidence import (
    ProviderEventConflictError,
    append_unique_events,
    event_deduplication_key,
)
from app.services.xtradot_webhook_worker import process_xtradot_webhook_receipt


INTERNAL_BASE = "http://bank-api.ingress-apisix.svc.cluster.local/v1"
API_KEY = "xtradot-test-key-do-not-log"
NOW = datetime(2026, 11, 9, 12, 0, tzinfo=timezone.utc)


def make_client(handler):
    transport = httpx.MockTransport(handler)
    return XtradotClient(
        base_url=INTERNAL_BASE,
        api_key=API_KEY,
        http_client=httpx.Client(transport=transport),
        clock=lambda: NOW,
    )


def test_lookup_normalizes_pending_and_keeps_amount_as_decimal_string():
    def handler(request):
        assert request.method == "GET"
        assert request.url.path == "/v1/transfers/TRF-123"
        assert request.headers["x-api-key"] == API_KEY
        return httpx.Response(200, json={
            "status": "success",
            "message": "Found",
            "data": {
                "reference": "TRF-123",
                "status": "pending",
                "amount": "75000.00",
                "currency": "NGN",
                "occurred_at": "2026-11-09T11:59:55Z",
            },
            "meta": None,
            "request_id": "req-safe-1",
        })

    with make_client(handler) as client:
        observed = client.get_transfer("TRF-123")

    assert observed.source_status == "pending"
    assert observed.amount == "75000.00"
    assert observed.safe_request_id == "req-safe-1"
    assert observed.environment == "sandbox"
    assert observed.evidence_basis == "sandbox_provider_response"


def test_client_preserves_undocumented_provider_status_without_interpreting_it():
    def handler(_request):
        return httpx.Response(200, json={
            "status": "success",
            "data": {"reference": "TRF-status", "status": "provider-specific-final-state"},
        })

    with make_client(handler) as client:
        observed = client.get_transfer("TRF-status")

    assert observed.source_status == "provider-specific-final-state"
    assert observed.requery_required is True


def test_timeout_becomes_unknown_without_automatic_resend():
    calls = []

    def handler(request):
        calls.append((request.method, request.url.path))
        return httpx.Response(504, json={
            "status": "error",
            "error": {"code": "TIMEOUT", "message": "timed out"},
            "request_id": "req-timeout",
        })

    with make_client(handler) as client:
        observed = client.get_transfer("TRF-timeout")

    assert observed.source_status == "outcome_unknown"
    assert observed.requery_required is True
    assert observed.evidence_basis == "transport_timeout"
    assert calls == [("GET", "/v1/transfers/TRF-timeout")]


def test_requery_uses_only_the_requery_endpoint_and_caller_supplied_contract():
    captured = []

    def handler(request):
        captured.append(request)
        return httpx.Response(200, json={
            "status": "success",
            "data": {"reference": "TRF-2", "status": "successful"},
            "request_id": "req-2",
        })

    request_body = {"reference": "TRF-2"}
    with make_client(handler) as client:
        observed = client.requery_interbank_transfer("TRF-2", request_body=request_body)

    assert captured[0].method == "POST"
    assert captured[0].url.path == "/v1/transfers/interbank/requery"
    assert json.loads(captured[0].content) == request_body
    assert observed.source_status == "successful"


def test_requery_pending_is_not_treated_as_failed():
    calls = []

    def handler(request):
        calls.append((request.method, request.url.path))
        return httpx.Response(202, json={
            "status": "success",
            "data": {"reference": "TRF-pending", "status": "pending"},
        })

    with make_client(handler) as client:
        observed = client.requery_interbank_transfer(
            "TRF-pending", request_body={"reference": "TRF-pending"}
        )

    assert observed.source_status == "pending"
    assert observed.requery_required is True
    assert observed.source_status != "failed"
    assert calls == [("POST", "/v1/transfers/interbank/requery")]


def test_requery_rejects_mismatched_caller_reference_before_network_call():
    with make_client(lambda _request: pytest.fail("request must not be sent")) as client:
        with pytest.raises(ValueError, match="must match"):
            client.requery_interbank_transfer(
                "TRF-expected", request_body={"reference": "TRF-other"}
            )


def test_lookup_does_not_trust_a_response_for_another_reference():
    def handler(_request):
        return httpx.Response(200, json={
            "status": "success",
            "data": {"reference": "OTHER", "status": "successful"},
        })

    with make_client(handler) as client:
        with pytest.raises(XtradotAPIError, match="reference mismatch"):
            client.get_transfer("TRF-requested")


@pytest.mark.parametrize("status_code", [401, 429, 503])
def test_provider_errors_are_sanitized_and_not_retried(status_code):
    calls = 0

    def handler(_request):
        nonlocal calls
        calls += 1
        return httpx.Response(status_code, json={
            "status": "error",
            "error": {"code": "RATE_LIMIT", "message": API_KEY},
        })

    with make_client(handler) as client:
        with pytest.raises(XtradotAPIError) as raised:
            client.get_transfer("TRF-429")

    assert calls == 1
    assert API_KEY not in str(raised.value)
    assert raised.value.status_code == status_code


def test_unknown_reference_is_reported_as_missing_not_failed():
    def handler(_request):
        return httpx.Response(404, json={
            "status": "error",
            "error": {"code": "NOT_FOUND", "message": "No transfer"},
            "request_id": "req-missing",
        })

    with make_client(handler) as client:
        observed = client.get_transfer("TRF-missing")

    assert observed.source_status == "missing"
    assert observed.requery_required is True
    assert observed.freshness == "missing"
    assert observed.safe_request_id == "req-missing"


def test_transport_timeout_is_unknown_and_not_retried():
    calls = 0

    def handler(_request):
        nonlocal calls
        calls += 1
        raise httpx.ReadTimeout("timeout")

    with make_client(handler) as client:
        observed = client.get_transfer("TRF-timeout")

    assert calls == 1
    assert observed.source_status == "outcome_unknown"
    assert observed.requery_required is True


@pytest.mark.parametrize(
    "url",
    [
        "https://evil.example/v1",
        "http://team10.xtradot.co/v1",
        "http://bank-api.ingress-apisix.svc.cluster.local:8080/v1",
    ],
)
def test_client_rejects_unapproved_hosts_or_insecure_public_host(url):
    with pytest.raises(XtradotConfigurationError):
        XtradotClient(base_url=url, api_key=API_KEY)


def test_client_requires_runtime_key():
    with pytest.raises(XtradotConfigurationError, match="API key"):
        XtradotClient(base_url=INTERNAL_BASE, api_key="")


def test_client_accepts_the_documented_public_sandbox_host_over_tls():
    client = XtradotClient(base_url="https://team10.xtradot.co/v1", api_key=API_KEY)
    client.close()


def _signature(body: bytes, timestamp: str, secret: str) -> str:
    return hmac.new(
        secret.encode(), timestamp.encode() + b"." + body, hashlib.sha256
    ).hexdigest()


def test_webhook_signature_accepts_valid_hmac_and_iso_timestamp():
    body = b'{"event_id":"evt-1","status":"pending"}'
    timestamp = NOW.isoformat()
    verify_webhook_signature(
        body,
        timestamp,
        _signature(body, timestamp, "webhook-secret"),
        "webhook-secret",
        now=NOW,
        timestamp_format="iso8601",
    )


@pytest.mark.parametrize(
    "timestamp,signature,secret",
    [
        ((NOW - timedelta(minutes=6)).isoformat(), "bad", "secret"),
        ((NOW + timedelta(minutes=6)).isoformat(), "bad", "secret"),
        (NOW.isoformat(), "bad", "secret"),
        (NOW.isoformat(), "bad", ""),
        ("not-a-timestamp", "bad", "secret"),
    ],
)
def test_webhook_rejects_stale_malformed_or_invalid_signatures(timestamp, signature, secret):
    with pytest.raises(WebhookVerificationError):
        verify_webhook_signature(b"{}", timestamp, signature, secret, now=NOW)


def test_webhook_decoder_preserves_decimal_precision_and_rejects_invalid_json():
    decoded = decode_webhook_body(b'{"amount":75000.10,"event_id":"evt-1"}')
    assert decoded["amount"] == Decimal("75000.10")

    with pytest.raises(WebhookVerificationError, match="valid JSON"):
        decode_webhook_body(b"{")
    with pytest.raises(WebhookVerificationError, match="JSON object"):
        decode_webhook_body(b"[]")


def make_event(bank_id, event_id, status, occurred_at, received_at=None):
    return PaymentEvidenceEvent(
        bank_id=bank_id,
        provider_event_id=event_id,
        payment_reference="TRF-123",
        event_type="transfer.status",
        source_status=status,
        amount="75000.00",
        currency="NGN",
        occurred_at=occurred_at,
        received_at=received_at or NOW,
    )


def test_duplicate_events_are_ignored_and_scope_includes_tenant():
    import uuid

    bank_a, bank_b = uuid.uuid4(), uuid.uuid4()
    first = make_event(bank_a, "same-event-id", "pending", NOW)
    replay = make_event(bank_a, "same-event-id", "failed", NOW + timedelta(seconds=1))
    other_bank = make_event(bank_b, "same-event-id", "successful", NOW)

    duplicate_delivery = make_event(
        bank_a, "same-event-id", "pending", NOW, received_at=NOW + timedelta(seconds=5)
    )
    merged = append_unique_events([first], [duplicate_delivery, other_bank])

    assert merged == [first, other_bank]
    assert event_deduplication_key(first) != event_deduplication_key(other_bank)

    with pytest.raises(ProviderEventConflictError, match="conflicting content"):
        append_unique_events([first], [replay])


def make_webhook_client(monkeypatch, *, secret="webhook-secret", event_types="transfer.updated"):
    bank_id = uuid.uuid4()
    monkeypatch.setenv("XTRADOT_WEBHOOK_SECRET", secret)
    monkeypatch.setenv("XTRADOT_BANK_ID", str(bank_id))
    monkeypatch.setenv("XTRADOT_SUPPORTED_EVENTS", event_types)
    monkeypatch.setenv("XTRADOT_WEBHOOK_TIMESTAMP_FORMAT", "iso8601")
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    sessions = sessionmaker(bind=engine, expire_on_commit=False)
    with sessions() as db:
        db.add(
            Bank(
                id=bank_id,
                name="Forge Sandbox Bank",
                slug=f"forge-{str(bank_id)[:8]}",
                contact_email="forge-test@example.invalid",
                status=BankStatus.ACTIVE,
            )
        )
        db.commit()

    def database():
        with sessions() as db:
            yield db

    app = FastAPI()
    app.include_router(forge_webhooks.router, prefix="/api/v1")
    app.dependency_overrides[get_db] = database
    return TestClient(app), sessions, engine, bank_id


def signed_headers(body, *, event_type="transfer.updated", timestamp=None, secret="webhook-secret"):
    stamp = timestamp or datetime.now(timezone.utc).isoformat()
    return {
        "x-forge-event": event_type,
        "x-forge-timestamp": stamp,
        "x-forge-signature": _signature(body, stamp, secret),
    }


def test_webhook_persists_verbatim_signed_event_and_deduplicates(monkeypatch):
    client, sessions, engine, bank_id = make_webhook_client(monkeypatch)
    try:
        body = b'{"event_id":"evt-1","unknown":"keep exactly as received"}'
        headers = signed_headers(body)
        first = client.post("/api/v1/forge/webhooks", content=body, headers=headers)
        replay = client.post("/api/v1/forge/webhooks", content=body, headers=headers)

        assert first.status_code == 202, first.text
        assert first.json()["status"] == "received"
        assert replay.status_code == 202, replay.text
        assert replay.json()["status"] == "duplicate"
        assert replay.json()["duplicate"] is True
        with sessions() as db:
            receipts = db.scalars(select(XtradotWebhookReceipt)).all()
            assert len(receipts) == 1
            receipt = receipts[0]
            assert receipt.bank_id == bank_id
            assert receipt.provider == "xtradot" and receipt.environment == "sandbox"
            assert receipt.event_id == "evt-1"
            assert receipt.event_type == "transfer.updated"
            assert receipt.raw_body == body
            assert receipt.raw_timestamp == headers["x-forge-timestamp"]
            assert receipt.signature_valid is True
            assert receipt.status == "received"
            receipt_id = receipt.id
        with sessions() as db:
            processed = process_xtradot_webhook_receipt(
                db, receipt_id=receipt_id, bank_id=bank_id
            )
            assert processed["status"] == "processed"
        with sessions() as db:
            receipt = db.get(XtradotWebhookReceipt, receipt_id)
            assert receipt is not None
            assert receipt.raw_body == body
            assert receipt.status == "processed"
            assert receipt.processed_at is not None
    finally:
        client.close()
        engine.dispose()


@pytest.mark.parametrize(
    "event_type,body",
    [
        ("not-configured", b'{"event_id":"evt-unknown"}'),
        ("transfer.updated", b'{"different_field":"no event id"}'),
        ("transfer.updated", b"not-json"),
    ],
)
def test_unknown_event_or_missing_payload_key_is_saved_as_ignored(monkeypatch, event_type, body):
    client, sessions, engine, _ = make_webhook_client(monkeypatch)
    try:
        response = client.post(
            "/api/v1/forge/webhooks",
            content=body,
            headers=signed_headers(body, event_type=event_type),
        )
        assert response.status_code == 202, response.text
        assert response.json()["status"] == "ignored"
        with sessions() as db:
            receipt = db.scalars(select(XtradotWebhookReceipt)).one()
            assert receipt.raw_body == body
            assert receipt.signature_valid is True
            assert receipt.status == "ignored"
    finally:
        client.close()
        engine.dispose()


def test_missing_secret_is_unavailable_without_accepting_or_persisting(monkeypatch):
    client, sessions, engine, _ = make_webhook_client(monkeypatch, secret="")
    try:
        body = b'{"event_id":"evt-no-secret"}'
        response = client.post(
            "/api/v1/forge/webhooks",
            content=body,
            headers={"x-forge-event": "transfer.updated"},
        )
        assert response.status_code == 503, response.text
        with sessions() as db:
            assert db.scalars(select(XtradotWebhookReceipt)).all() == []
    finally:
        client.close()
        engine.dispose()


def test_invalid_signature_is_rejected_without_persisting(monkeypatch):
    client, sessions, engine, _ = make_webhook_client(monkeypatch)
    try:
        body = b'{"event_id":"evt-forged"}'
        headers = signed_headers(body)
        headers["x-forge-signature"] = "0" * 64
        response = client.post("/api/v1/forge/webhooks", content=body, headers=headers)
        assert response.status_code == 401
        with sessions() as db:
            assert db.scalars(select(XtradotWebhookReceipt)).all() == []
    finally:
        client.close()
        engine.dispose()


def test_stale_signature_is_rejected_without_persisting(monkeypatch):
    client, sessions, engine, _ = make_webhook_client(monkeypatch)
    try:
        body = b'{"event_id":"evt-stale"}'
        stamp = (datetime.now(timezone.utc) - timedelta(minutes=6)).isoformat()
        response = client.post(
            "/api/v1/forge/webhooks",
            content=body,
            headers=signed_headers(body, timestamp=stamp),
        )
        assert response.status_code == 401
        with sessions() as db:
            assert db.scalars(select(XtradotWebhookReceipt)).all() == []
    finally:
        client.close()
        engine.dispose()


def test_unconfigured_timestamp_format_is_saved_ignored_not_guessed(monkeypatch):
    client, sessions, engine, _ = make_webhook_client(monkeypatch)
    monkeypatch.setenv("XTRADOT_WEBHOOK_TIMESTAMP_FORMAT", "")
    try:
        body = b'{"event_id":"evt-no-format"}'
        response = client.post(
            "/api/v1/forge/webhooks",
            content=body,
            headers=signed_headers(body),
        )
        assert response.status_code == 202
        assert response.json()["status"] == "ignored"
        with sessions() as db:
            receipt = db.scalars(select(XtradotWebhookReceipt)).one()
            assert receipt.signature_valid is True
            assert receipt.status == "ignored"
    finally:
        client.close()
        engine.dispose()


def test_webhook_body_size_is_bounded(monkeypatch):
    client, _, engine, _ = make_webhook_client(monkeypatch)
    try:
        response = client.post(
            "/api/v1/forge/webhooks",
            content=b"x" * (forge_webhooks.MAX_WEBHOOK_BODY_BYTES + 1),
            headers={"content-type": "application/octet-stream"},
        )
        assert response.status_code == 413
    finally:
        client.close()
        engine.dispose()


def test_worker_processing_is_bank_scoped(monkeypatch):
    client, sessions, engine, bank_id = make_webhook_client(monkeypatch)
    try:
        body = b'{"event_id":"evt-isolated"}'
        response = client.post(
            "/api/v1/forge/webhooks",
            content=body,
            headers=signed_headers(body),
        )
        receipt_id = uuid.UUID(response.json()["receipt_id"])
        with sessions() as db:
            with pytest.raises(LookupError, match="not found for this bank"):
                process_xtradot_webhook_receipt(
                    db, receipt_id=receipt_id, bank_id=uuid.uuid4()
                )
        with sessions() as db:
            processed = process_xtradot_webhook_receipt(
                db, receipt_id=receipt_id, bank_id=bank_id
            )
            assert processed["status"] == "processed"
    finally:
        client.close()
        engine.dispose()
