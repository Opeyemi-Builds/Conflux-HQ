from app.ai.agent.loop import fallback_findings, run_investigation_loop
from app.ai.agent.tools import ALLOWED_TOOL_NAMES
from app.ai.schemas import CandidateCause, Evidence, Findings
from app.ai.investigation import validate_findings


def release_evidence():
    return {
        "incident": {
            "issue_type": "failed_transfer",
            "started_at": "2026-11-06T10:00:00+00:00",
            "complaint_count": 30,
            "baseline": 2.0,
            "growth_rate": 15.0,
        },
        "complaints": {
            "count": 30,
            "channels": {"app": 18, "ussd": 12},
            "channel_shares": {"app": 0.6, "ussd": 0.4},
            "top_region": "Lagos",
        },
        "transactions": {
            "observed": 40,
            "failed": 20,
            "unreversed_failed": 18,
            "matched_complaints": 18,
            "failure_rate": 0.5,
            "channels": ["app", "ussd"],
            "failed_by_processor": {"demo-switch-a": 18},
            "dominant_processor": "demo-switch-a",
        },
        "events": [
            {
                "type": "release",
                "component": "transfer-service",
                "version": "v4.2.1",
                "description": "App transfer release on demo-switch-a",
                "starts_at": "2026-11-06T09:48:00+00:00",
            },
            {
                "type": "maintenance",
                "component": "email-service",
                "version": None,
                "description": "SYNTHETIC DECOY: unrelated email maintenance",
                "starts_at": "2026-11-06T05:00:00+00:00",
            },
        ],
    }


def test_fallback_names_release_and_keeps_decoy_as_contradicting_evidence():
    findings = fallback_findings(release_evidence())
    assert "v4.2.1" in findings.likely_cause
    assert "app" in " ".join(findings.affected_channels)
    assert findings.confidence == 0.5
    assert findings.method == "rules_fallback"
    assert any("decoy" in item.detail.lower() for item in findings.contradicting_evidence)
    assert findings.supporting_evidence
    assert all(item.kind in {"fact", "inference", "recommendation"} for item in findings.supporting_evidence)


def test_no_explaining_event_means_unknown_and_low_confidence():
    evidence = release_evidence()
    evidence["events"] = [evidence["events"][1]]
    findings = fallback_findings(evidence)
    assert findings.likely_cause == "unknown"
    assert findings.confidence <= 0.4
    assert findings.recommended_next_step == "Manually check the payment path and relevant system logs."
    assert all("email-service" not in cause.cause for cause in findings.candidate_causes)


def test_ungrounded_fact_is_downgraded_and_confidence_is_reduced():
    findings = Findings(
        headline="A finding",
        candidate_causes=[
            CandidateCause(
                cause="Unknown",
                confidence=0.9,
                evidence=[Evidence(source="transactions", detail="There were 999 failed transactions.", kind="fact")],
            )
        ],
        affected_channels=[],
        recommended_action="Review",
        likely_cause="Unknown",
        confidence=0.9,
        supporting_evidence=[
            Evidence(source="transactions", detail="There were 999 failed transactions.", kind="fact")
        ],
    )
    validated = validate_findings(findings, release_evidence())
    assert validated.supporting_evidence[0].kind == "inference"
    assert validated.candidate_causes[0].evidence[0].kind == "inference"
    assert validated.confidence < 0.9
    assert validated.candidate_causes[0].confidence < 0.9


def test_provider_construction_failure_falls_back(monkeypatch):
    from app.core.config import get_settings
    import anthropic

    settings = get_settings()
    monkeypatch.setattr(settings, "ai_provider", "anthropic")
    monkeypatch.setattr(settings, "anthropic_api_key", "test-key-not-used")
    monkeypatch.setattr(anthropic, "Anthropic", lambda **kwargs: (_ for _ in ()).throw(RuntimeError("offline")))
    findings, source, _ = run_investigation_loop(release_evidence())
    assert source == "rules"
    assert findings.method == "rules_fallback"


def test_agent_tools_have_no_write_or_money_movement_capability():
    forbidden = ("refund", "reverse", "block", "send", "execute", "payment_write")
    assert all(not any(word in name.casefold() for word in forbidden) for name in ALLOWED_TOOL_NAMES)
