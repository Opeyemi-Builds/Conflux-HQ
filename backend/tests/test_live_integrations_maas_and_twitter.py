"""End-to-end integration tests verifying Huawei MaaS and X (Twitter) Live Adapter protocols and pipeline execution.

Validates exact contracts against forge-2026-agent-reference.md:
1. Huawei MaaS:
   - Endpoint: http://huawei-maas.ingress-apisix.svc.cluster.local/openai/v1/chat/completions
   - Auth Header: 'apikey: <team-key>' (strictly NO 'Authorization: Bearer')
   - Reasoning disabled via chat_template_kwargs: {"thinking": False}
   - Model inference in Complaint Classification, Grounded Incident Investigation, and Drafts
   - Resilient parsing (raw JSON, fenced markdown, conversational text)
   - Downstream persistence into Database (Complaints, InvestigationRuns, Drafts)
2. Twitter Live Adapter & Monitor:
   - Query compilation specifically scoped for a single target bank (and handles)
   - Recent Search API v2 request/response protocol (Authorization: Bearer <token>)
   - Multi-tenant attribution, PII masking, author pseudonymization, and deduplication
   - Guardrails: daily read limit ($0.005/post) and spending cap enforcement
   - End-to-end handoff into Complaint Queue -> MaaS Classification -> Incident Spike Detection
"""

import json
import uuid
from datetime import datetime, timezone

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.adapters.x_adapter import (
    XAdapter,
    compile_combined_search_query,
    compile_desired_rules,
    diff_stream_rules,
    get_x_adapter_status,
)
from app.ai.agent.loop import run_investigation_loop
from app.ai.classifier import classify
from app.ai.drafts import create_drafts
from app.ai.investigation import (
    InvestigationBrief,
    investigate_with_fallback,
    maas_investigate,
    validate_brief,
)
from app.ai.providers.classify import classify_with_fallback, maas_classify
from app.ai.providers.maas import MaasConfig, MaasError, chat_completion, parse_json_text
from app.ai.providers.settings import maas_active, maas_config_from_settings, maas_key_from_settings
from app.core.config import get_settings
from app.models import Bank, BankAlias, Complaint, Incident, InvestigationRun, Job, SocialReceipt
from app.models.enums import BankStatus, Channel, IncidentStatus, IssueType, JobKind, JobStatus
from app.services.worker import drain_jobs
from tests.test_social import setup


@pytest.fixture
def mock_maas_env(monkeypatch):
    """Configures environment matching Forge cluster secrets and configmap."""
    monkeypatch.setenv("AI_PROVIDER", "maas")
    monkeypatch.setenv("MAAS_ENABLED", "true")
    monkeypatch.setenv("MAAS_MODEL", "glm-5.2")
    monkeypatch.setenv("MAAS_BASE_URL", "http://huawei-maas.ingress-apisix.svc.cluster.local/openai/v1")
    monkeypatch.setenv("GATEWAY_KEY", "forge-team-test-key-xyz123")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


# ==============================================================================
# SECTION 1: HUAWEI MAAS INTEGRATION TESTS
# ==============================================================================


def test_maas_chat_completion_protocol_and_headers(monkeypatch, mock_maas_env):
    """Verifies that MaaS chat completions request strictly matches the Forge specification."""
    captured_request = {}

    class MockResponse:
        status_code = 200

        def json(self):
            return {
                "id": "chatcmpl-test-01",
                "object": "chat.completion",
                "created": 1700000000,
                "model": "glm-5.2",
                "choices": [
                    {
                        "index": 0,
                        "message": {
                            "role": "assistant",
                            "content": json.dumps({
                                "issue_type": "failed_transfer",
                                "severity": "high",
                                "sentiment": "negative",
                                "language": "pidgin",
                                "mentioned_amount": 50000.0,
                                "mentioned_time": None,
                                "is_fraud": False,
                                "short_summary": "Customer debited 50k without credit.",
                                "confidence": 0.95,
                            }),
                        },
                        "finish_reason": "stop",
                    }
                ],
                "usage": {"prompt_tokens": 42, "completion_tokens": 28, "total_tokens": 70},
            }

    def fake_post(url, headers=None, json=None, timeout=None):
        captured_request["url"] = url
        captured_request["headers"] = headers
        captured_request["json"] = json
        captured_request["timeout"] = timeout
        return MockResponse()

    monkeypatch.setattr(httpx, "post", fake_post)

    cfg = maas_config_from_settings(get_settings())
    key = maas_key_from_settings(get_settings())

    assert maas_active(get_settings()) is True
    assert key == "forge-team-test-key-xyz123"

    result = chat_completion(
        messages=[
            {"role": "system", "content": "You are a Nigerian banking classifier."},
            {"role": "user", "content": "abeg they debit my 50k since yesterday no alert"},
        ],
        config=cfg,
        gateway_key=key,
        json_mode=True,
    )

    # 1. URL strictly follows Huawei MaaS ingress on Forge
    assert captured_request["url"] == "http://huawei-maas.ingress-apisix.svc.cluster.local/openai/v1/chat/completions"

    # 2. Auth header strictly uses 'apikey', NEVER 'Authorization' or 'x-api-key'
    assert "apikey" in captured_request["headers"]
    assert captured_request["headers"]["apikey"] == "forge-team-test-key-xyz123"
    assert "Authorization" not in captured_request["headers"]

    # 3. Payload includes model, temperature=0, and reasoning disabled via chat_template_kwargs
    body = captured_request["json"]
    assert body["model"] == "glm-5.2"
    assert body["temperature"] == 0
    assert body.get("chat_template_kwargs") == {"thinking": False}

    # 4. Result telemetry and parsed output
    assert result.payload["issue_type"] == "failed_transfer"
    assert result.payload["language"] == "pidgin"
    assert result.input_tokens == 42
    assert result.output_tokens == 28


def test_maas_resilient_json_parsing():
    """Verifies that model output wrapped in markdown code fences or conversational text is parsed cleanly."""
    valid_data = {"issue_type": "pos", "severity": "medium", "confidence": 0.88}

    # 1. Standard raw JSON
    assert parse_json_text(json.dumps(valid_data)) == valid_data

    # 2. Markdown code fences
    fenced = f"```json\n{json.dumps(valid_data)}\n```"
    assert parse_json_text(fenced) == valid_data

    # 3. Conversational preamble & postamble with code fences
    chatty = f"Here is the classification JSON:\n```json\n{json.dumps(valid_data)}\n```\nHope this helps!"
    assert parse_json_text(chatty) == valid_data

    # 4. Conversational wrapping without code fences
    wrapped = f"The identified result is {json.dumps(valid_data)}. Please review."
    assert parse_json_text(wrapped) == valid_data

    # 5. Non-JSON string raises MaasError('malformed')
    with pytest.raises(MaasError) as exc:
        parse_json_text("Sorry, I cannot process this message.")
    assert exc.value.kind == "malformed"


def test_maas_complaint_classification_pipeline(monkeypatch, mock_maas_env):
    """Verifies end-to-end complaint classification through MaaS into the database."""
    client, sessions, engine = setup(monkeypatch)
    db = sessions()
    try:
        bank = Bank(name="Access Bank", slug="access", contact_email="access@example.com", status=BankStatus.ACTIVE)
        db.add(bank)
        db.commit()

        # Mock MaaS response
        def fake_post(url, *args, **kwargs):
            class Resp:
                status_code = 200

                def json(self):
                    return {
                        "choices": [
                            {
                                "message": {
                                    "content": json.dumps({
                                        "issue_type": "failed_transfer",
                                        "severity": "high",
                                        "sentiment": "negative",
                                        "language": "pidgin",
                                        "mentioned_amount": 25000.0,
                                        "mentioned_time": None,
                                        "is_fraud": False,
                                        "short_summary": "Customer transfer of 25k failed.",
                                        "confidence": 0.92,
                                    })
                                }
                            }
                        ],
                        "usage": {"prompt_tokens": 15, "completion_tokens": 20},
                    }

            return Resp()

        monkeypatch.setattr(httpx, "post", fake_post)

        # 1. Direct classification call
        result, source = classify("abeg my 25000 naira transfer hanging since yesterday", "in_app")
        assert source == "maas"
        assert result.issue_type == "failed_transfer"
        assert result.language == "pidgin"
        assert result.mentioned_amount == 25000.0
        assert result.confidence == 0.92

        # 2. Ingest complaint and run worker classification job
        complaint = Complaint(
            bank_id=bank.id,
            channel=Channel.IN_APP,
            text="abeg my 25000 naira transfer hanging since yesterday",
            customer_ref="cust_test_1",
            occurred_at=datetime.now(timezone.utc),
            issue_type=None,  # Unclassified
        )
        db.add(complaint)
        db.commit()

        # Queue classification job
        job = Job(
            bank_id=bank.id,
            kind=JobKind.CLASSIFY_COMPLAINT,
            status=JobStatus.PENDING,
            payload={"complaint_id": str(complaint.id)},
            idempotency_key=f"classify:{complaint.id}",
        )
        db.add(job)
        db.commit()

        # Drain jobs (runs classify_complaint and subsequent detect_spikes)
        drain_result = drain_jobs(db, bank_id=bank.id)
        assert drain_result["completed"] >= 1

        # Verify complaint updated in DB
        db.refresh(complaint)
        assert complaint.issue_type == IssueType.FAILED_TRANSFER
        assert complaint.severity.value == "high"
        assert complaint.classified_at is not None
    finally:
        db.close()
        engine.dispose()


def test_maas_incident_investigation_and_brief_generation(monkeypatch, mock_maas_env):
    """Verifies grounded MaaS investigation with evidence registry validation and database persistence."""
    client, sessions, engine = setup(monkeypatch)
    db = sessions()
    try:
        bank = Bank(name="Access Bank", slug="access", contact_email="access@example.com", status=BankStatus.ACTIVE)
        db.add(bank)
        db.commit()

        incident = Incident(
            bank_id=bank.id,
            issue_type="failed_transfer",
            status=IncidentStatus.INVESTIGATING,
            started_at=datetime.now(timezone.utc),
            detected_at=datetime.now(timezone.utc),
            complaint_count=15,
            baseline=2.0,
            growth_rate=7.5,
            priority_score=0.85,
            affected_channels={"in_app": 10, "x": 5},
        )
        db.add(incident)
        db.commit()

        evidence_bundle = {
            "incident": {"issue_type": "failed_transfer", "complaint_count": 15, "baseline": 2.0},
            "complaints": {"count": 15, "channels": {"in_app": 10, "x": 5}},
            "transactions": {"observed": 40, "failed": 12, "unreversed_failed": 8, "dominant_processor": "NIBSS"},
            "events": [{"id": "evt-switch-timeout-01", "type": "network", "component": "NIBSS"}],
            "evidence_registry": {
                "complaints": [{"id": "cmp-101"}, {"id": "cmp-102"}],
                "system_events": [{"id": "evt-switch-timeout-01"}],
                "transactions": [{"id": "txn-999"}],
            },
        }

        # Mock MaaS investigation response citing valid registry IDs
        def fake_post(url, *args, **kwargs):
            class Resp:
                status_code = 200

                def json(self):
                    return {
                        "choices": [
                            {
                                "message": {
                                    "content": json.dumps({
                                        "observed_facts": [
                                            "15 complaints vs baseline 2.0 for failed_transfer.",
                                            "12 failed transactions observed via NIBSS processor.",
                                        ],
                                        "hypotheses": [
                                            {
                                                "statement": "NIBSS interbank switch latency caused transfer timeouts.",
                                                "confidence": 0.85,
                                                "evidence_ids": ["evt-switch-timeout-01"],
                                            }
                                        ],
                                        "supporting_evidence_ids": ["evt-switch-timeout-01"],
                                        "contradicting_evidence_ids": [],
                                        "missing_evidence": ["NIBSS external reconciliation confirmation"],
                                        "recommended_checks": [
                                            "verify NIBSS gateway response codes",
                                            "check switch connectivity logs",
                                        ],
                                        "recommended_owner": "switch-integration-team",
                                        "corrective_actions": [
                                            "Review-only: alert switch on-call; do not trigger automated refunds without confirmation.",
                                        ],
                                        "confidence": 0.85,
                                    })
                                }
                            }
                        ],
                        "usage": {"prompt_tokens": 120, "completion_tokens": 85},
                    }

            return Resp()

        monkeypatch.setattr(httpx, "post", fake_post)

        brief, telemetry = maas_investigate(
            evidence_bundle,
            config=maas_config_from_settings(get_settings()),
            gateway_key=maas_key_from_settings(get_settings()),
        )

        assert brief.confidence == 0.85
        assert "evt-switch-timeout-01" in brief.supporting_evidence_ids
        assert telemetry["source"] == "maas"
        assert telemetry["model"] == "glm-5.2"

        # Test loop projection onto incident
        findings, source, trace = run_investigation_loop(evidence_bundle)
        assert source == "maas"
        assert "NIBSS" in findings.headline
        assert findings.affected_switch == "NIBSS"

        # Test draft generation via MaaS
        drafts = create_drafts(db, bank.id, incident, actor="worker")
        assert len(drafts) >= 1
    finally:
        db.close()
        engine.dispose()


# ==============================================================================
# SECTION 2: TWITTER LIVE ADAPTER & MONITOR INTEGRATION TESTS
# ==============================================================================


def test_twitter_query_compilation_for_particular_bank(monkeypatch):
    """Verifies that query generation is scoped specifically to a target bank and handles."""
    client, sessions, engine = setup(monkeypatch)
    db = sessions()
    try:
        # Bank 1: Access Bank
        bank1 = Bank(name="Access Bank PLC", slug="accessbank", contact_email="access@example.com", status=BankStatus.ACTIVE)
        db.add(bank1)
        db.flush()
        db.add(BankAlias(bank_id=bank1.id, value="@accessbankplc", kind="handle", platform="x"))
        db.add(BankAlias(bank_id=bank1.id, value="@access_more", kind="handle", platform="x"))
        db.add(BankAlias(bank_id=bank1.id, value="#AccessBank", kind="hashtag", platform="x"))

        # Bank 2: GTBank
        bank2 = Bank(name="Guaranty Trust Bank", slug="gtbank", contact_email="gtb@example.com", status=BankStatus.ACTIVE)
        db.add(bank2)
        db.flush()
        db.add(BankAlias(bank_id=bank2.id, value="@gtbank", kind="handle", platform="x"))

        db.commit()

        # 1. Query scoped specifically to Bank 1 (Access Bank)
        query_bank1 = compile_combined_search_query(db, target_bank_id=bank1.id)
        assert "@accessbankplc" in query_bank1
        assert "to:accessbankplc" in query_bank1
        assert "@access_more" in query_bank1
        assert "#accessbank" in query_bank1
        assert "-is:retweet" in query_bank1
        # Crucially, Bank 2's handle MUST NOT appear in Bank 1's query!
        assert "@gtbank" not in query_bank1

        # 2. Query scoped to an explicit handle
        query_handle = compile_combined_search_query(db, handles=["@access_support"])
        assert query_handle == "(@access_support OR to:access_support) -is:retweet"

        # 3. Stream rules compilation creates separate tenant tags
        rules = compile_desired_rules(db)
        tags = {r["tag"] for r in rules}
        assert f"tenant:{bank1.id}" in tags
        assert f"tenant:{bank2.id}" in tags
    finally:
        db.close()
        engine.dispose()


def test_twitter_recent_search_live_pull_for_bank(monkeypatch):
    """Verifies live Twitter API v2 Recent Search pull, bank attribution, masking, and deduplication."""
    client, sessions, engine = setup(monkeypatch)
    db = sessions()
    try:
        monkeypatch.setattr(get_settings(), "x_bearer_token", "test-live-x-bearer-token")

        bank = Bank(name="Access Bank", slug="accessbank", contact_email="access@example.com", status=BankStatus.ACTIVE)
        db.add(bank)
        db.flush()
        db.add(BankAlias(bank_id=bank.id, value="@accessbankplc", kind="handle", platform="x"))
        db.commit()

        captured_requests = []

        class FakeXResponse:
            def __init__(self, status_code, data):
                self.status_code = status_code
                self._data = data

            def raise_for_status(self):
                if self.status_code >= 400:
                    raise httpx.HTTPStatusError("error", request=None, response=self)

            def json(self):
                return self._data

        def fake_x_get(url, params=None, headers=None, timeout=None):
            captured_requests.append({"url": url, "params": params, "headers": headers})
            return FakeXResponse(
                200,
                {
                    "data": [
                        {
                            "id": "1854999999000000001",
                            "text": "@accessbankplc my transfer of 50,000 to Zenith failed, call me on 08031234567!",
                            "author_id": "usr_998877",
                            "created_at": "2026-11-11T08:00:00Z",
                            "lang": "en",
                        },
                        {
                            "id": "1854999999000000002",
                            "text": "@accessbankplc app login error since 7am, cannot see my account balance",
                            "author_id": "usr_112233",
                            "created_at": "2026-11-11T08:05:00Z",
                            "lang": "en",
                        },
                    ],
                    "includes": {
                        "users": [
                            {"id": "usr_998877", "username": "lagos_trader", "name": "Lagos Trader"},
                            {"id": "usr_112233", "username": "ibadan_buyer", "name": "Ibadan Buyer"},
                        ]
                    },
                    "meta": {
                        "newest_id": "1854999999000000002",
                        "oldest_id": "1854999999000000001",
                        "result_count": 2,
                    },
                },
            )

        monkeypatch.setattr(httpx, "get", fake_x_get)

        adapter = XAdapter(db)

        # Pull recent mentions targeting Bank
        pull_result = adapter.pull_recent_mentions(
            target_bank_id=bank.id,
            max_results=15,
        )

        assert pull_result["source"] == "live_recent_search"
        assert pull_result["fetched"] == 2
        assert pull_result["accepted_count"] == 2
        assert pull_result["complaints_created"] == 2
        assert pull_result["newest_id"] == "1854999999000000002"

        # Verify X API v2 query protocol
        req = captured_requests[0]
        assert req["headers"]["Authorization"] == "Bearer test-live-x-bearer-token"
        assert "@accessbankplc" in req["params"]["query"]
        assert req["params"]["max_results"] == 15

        # Verify complaints created in Database
        complaints = db.scalars(
            select(Complaint).where(Complaint.bank_id == bank.id).order_by(Complaint.occurred_at.asc())
        ).all()
        assert len(complaints) == 2

        # PII (phone number 08031234567) must be masked in DB
        assert "08031234567" not in complaints[0].text
        assert "[PHONE]" in complaints[0].text
        assert complaints[0].customer_ref.startswith("cust_")
        assert complaints[0].channel == Channel.X

        # Verify SocialReceipts created
        receipts = db.scalars(select(SocialReceipt).where(SocialReceipt.bank_id == bank.id)).all()
        assert len(receipts) == 2
        assert receipts[0].post_id == "1854999999000000001"
        assert receipts[0].platform == "x"

        # 2. Verify Deduplication: pulling the exact same tweets again creates 0 new complaints!
        pull_again = adapter.pull_recent_mentions(
            target_bank_id=bank.id,
            max_results=15,
        )
        assert pull_again["duplicates"] == 2
        assert pull_again["complaints_created"] == 0

        # Complaint count in DB is still exactly 2
        assert len(db.scalars(select(Complaint).where(Complaint.bank_id == bank.id)).all()) == 2
    finally:
        db.close()
        engine.dispose()


def test_twitter_spending_cap_guardrail(monkeypatch):
    """Verifies that the $0.005/post daily cap prevents runaway API spending."""
    client, sessions, engine = setup(monkeypatch)
    db = sessions()
    try:
        monkeypatch.setattr(get_settings(), "x_bearer_token", "test-live-x-bearer-token")
        # Set limit to 2 posts
        monkeypatch.setattr(get_settings(), "x_daily_post_limit", 2)

        bank = Bank(name="Access Bank", slug="accessbank", contact_email="access@example.com", status=BankStatus.ACTIVE)
        db.add(bank)
        db.flush()
        db.add(BankAlias(bank_id=bank.id, value="@accessbankplc", kind="handle", platform="x"))
        db.commit()

        adapter = XAdapter(db)

        # Ingest 2 posts directly
        for i in range(2):
            adapter.ingest_raw_v2_payload(
                {
                    "data": {
                        "id": f"post_cap_test_{i}",
                        "text": "@accessbankplc debit issue",
                        "created_at": "2026-11-11T08:00:00Z",
                    }
                },
                synthetic=False,
            )

        status = get_x_adapter_status(db)
        assert status["reads_today"] == 2
        assert status["budget_remaining_reads"] == 0

        # Next pull attempt must be rejected by spending cap guardrail
        blocked = adapter.pull_recent_mentions(target_bank_id=bank.id, max_results=10)
        assert blocked["source"] == "blocked_by_cap"
        assert blocked["reason"] == "daily_post_cap_reached"
    finally:
        db.close()
        engine.dispose()


def test_twitter_to_maas_full_integration_pipeline(monkeypatch, mock_maas_env):
    """End-to-end integration: Live Twitter Pull -> Complaint Intake -> MaaS Classification -> Spike Detection."""
    client, sessions, engine = setup(monkeypatch)
    db = sessions()
    try:
        monkeypatch.setattr(get_settings(), "x_bearer_token", "test-live-x-bearer-token")

        bank = Bank(name="Access Bank", slug="accessbank", contact_email="access@example.com", status=BankStatus.ACTIVE)
        db.add(bank)
        db.flush()
        db.add(BankAlias(bank_id=bank.id, value="@accessbankplc", kind="handle", platform="x"))
        db.commit()

        # 1. Mock X API response with an ambiguous tweet that requires MaaS classification
        def fake_x_get(url, params=None, headers=None, timeout=None):
            class Resp:
                status_code = 200

                def raise_for_status(self):
                    pass

                def json(self):
                    return {
                        "data": [
                            {
                                "id": "1855111111000000001",
                                "text": "@accessbankplc e don reach 2 days my money vanish for inside app",
                                "author_id": "usr_pidgin_01",
                                "created_at": "2026-11-11T08:10:00Z",
                            }
                        ],
                        "includes": {"users": [{"id": "usr_pidgin_01", "username": "pidgin_user"}]},
                        "meta": {"result_count": 1, "newest_id": "1855111111000000001"},
                    }

            return Resp()

        # 2. Mock MaaS response for classification
        def fake_maas_post(url, *args, **kwargs):
            class Resp:
                status_code = 200

                def json(self):
                    return {
                        "choices": [
                            {
                                "message": {
                                    "content": json.dumps({
                                        "issue_type": "failed_transfer",
                                        "severity": "high",
                                        "sentiment": "negative",
                                        "language": "pidgin",
                                        "mentioned_amount": None,
                                        "mentioned_time": "2 days",
                                        "is_fraud": False,
                                        "short_summary": "Customer reports vanished funds in app.",
                                        "confidence": 0.89,
                                    })
                                }
                            }
                        ],
                        "usage": {"prompt_tokens": 30, "completion_tokens": 25},
                    }

            return Resp()

        monkeypatch.setattr(httpx, "get", fake_x_get)
        monkeypatch.setattr(httpx, "post", fake_maas_post)

        adapter = XAdapter(db)

        # Pull tweets
        pull_result = adapter.pull_recent_mentions(target_bank_id=bank.id)
        assert pull_result["complaints_created"] == 1

        # Check that job queue has the classification job
        jobs = db.scalars(select(Job).where(Job.bank_id == bank.id)).all()
        assert len(jobs) >= 1
        assert any(j.kind == JobKind.CLASSIFY_COMPLAINT for j in jobs)

        # Drain the job queue (executes MaaS classification)
        drain_result = drain_jobs(db, bank_id=bank.id)
        assert drain_result["completed"] >= 1

        # Check complaint in DB: now fully classified by MaaS!
        complaint = db.scalar(select(Complaint).where(Complaint.bank_id == bank.id))
        assert complaint is not None
        assert complaint.issue_type == IssueType.FAILED_TRANSFER
        assert complaint.sentiment.value == "negative"
        assert complaint.classified_at is not None
    finally:
        db.close()
        engine.dispose()
