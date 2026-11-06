from app.ai.classifier import fallback_classify
from app.ai.agent.loop import run_investigation_loop
from app.ai.agent.tools import ALLOWED_TOOL_NAMES, run_tool
from app.ai.runtime import gemini_schema
from app.models.enums import IssueType
from app.ai.schemas import ClassificationResult


def test_pidgin_failed_transfer_falls_back():
    result = fallback_classify("my money don enter nowhere, failed transfer on USSD")
    assert result.issue_type == IssueType.FAILED_TRANSFER
    assert result.language == "pidgin"


def test_scam_routes_to_fraud():
    result = fallback_classify("a fake agent asked for my OTP")
    assert result.issue_type == IssueType.FRAUD_SCAM
    assert result.is_fraud


def test_ai_complaint_endpoint_and_investigation(authed):
    complaint = authed.post("/api/v1/complaints", json={
        "channel": "in_app", "text": "my money don enter nowhere"
    }).json()
    classified = authed.post(f"/api/v1/complaints/{complaint['id']}/classify")
    assert classified.status_code == 200
    assert classified.json()["issue_type"] == "failed_transfer"

    spike = authed.post("/api/v1/complaints/bulk", json={"complaints": [
        {"channel": "in_app", "text": "failed transfer after debit", "issue_type": "failed_transfer",
         "occurred_at": "2026-11-06T10:31:00Z"}
        for _ in range(12)
    ]})
    assert spike.status_code == 201
    incidents = authed.post("/api/v1/incidents/detect", json={"now": "2026-11-06T10:40:00Z"})
    if incidents.status_code == 200 and incidents.json():
        incident_id = incidents.json()[0]["id"]
        investigated = authed.post(f"/api/v1/ai/incidents/{incident_id}/investigate")
        assert investigated.status_code == 200
        drafts = authed.get(f"/api/v1/ai/incidents/{incident_id}/drafts")
        assert drafts.status_code == 200 and len(drafts.json()) == 2


def test_fallback_handles_pidgin_and_amount():
    result = fallback_classify("abeg my money don enter nowhere, send 20k since morning")
    assert result.issue_type == IssueType.FAILED_TRANSFER
    assert result.language == "pidgin"
    assert result.mentioned_amount == 20000


def test_fallback_recognises_mixed_nigerian_languages():
    cases = {
        "Yoruba: e jowo, my transfer ti debited but ti de sir": "yoruba_mix",
        "biko, ATM ego m no come out": "igbo_mix",
        "don Allah, my app no work": "hausa_mix",
    }
    for text, expected in cases.items():
        assert fallback_classify(text).language == expected


def test_agent_fallback_never_moves_money():
    findings, source, trace = run_investigation_loop({
        "incident": {"complaint_count": 12, "baseline": 2, "issue_type": "failed_transfer"},
        "complaints": {"channels": {"app": 12}},
        "transactions": {"observed": 20, "failed": 8, "channels": ["app"], "failed_by_processor": {}},
        "events": [],
    })
    assert source in ("rules", "llm")
    assert findings.propose_reversal_request is False
    assert "money movement" in findings.recommended_action


def test_paste_classification_endpoint(authed):
    response = authed.post("/api/v1/ai/classify", json={
        "text": "Person called, said na from bank and asked for my OTP",
        "channel": "call",
    })
    assert response.status_code == 200
    assert response.json()["issue_type"] == "fraud_scam"
    assert response.json()["source"] in ("rules", "llm")
    assert response.json()["latency_ms"] is not None


def test_gemini_structured_schema_is_provider_safe():
    schema = gemini_schema(ClassificationResult)
    assert schema["type"].lower() == "object"
    assert "issue_type" in schema["properties"]
    assert "title" not in schema


def test_investigation_tools_are_read_only_and_allowlisted():
    write_tools = {"execute_payment", "create_reversal", "move_money", "run_sql", "shell"}
    assert write_tools.isdisjoint(ALLOWED_TOOL_NAMES)
    try:
        run_tool("execute_payment", {}, {})
    except ValueError as exc:
        assert "not allowlisted" in str(exc)
    else:
        raise AssertionError("A write-capable tool unexpectedly passed the allowlist")
