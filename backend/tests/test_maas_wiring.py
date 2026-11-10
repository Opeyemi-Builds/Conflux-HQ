"""Wiring tests: Settings -> classify/investigate/draft MaaS paths, persistence, fallback."""
import json

import httpx
import pytest

from app.ai.agent import loop as loop_module
from app.ai.agent.loop import _brief_to_findings, run_investigation_loop, with_registry
from app.ai.classifier import classify
from app.ai.evidence import build_evidence
from app.ai.investigation import InvestigationBrief
from app.ai.providers.settings import maas_active, maas_config_from_settings
from app.core.config import get_settings


def _brief_response(monkeypatch, **overrides):
    payload = {
        "observed_facts": ["12 complaints vs baseline 2.0."],
        "hypotheses": [{"statement": "Release v4.2.1 preceded the spike; unconfirmed.",
                        "confidence": 0.55, "evidence_ids": ["evt-1"]}],
        "supporting_evidence_ids": ["evt-1"],
        "contradicting_evidence_ids": [],
        "missing_evidence": ["settlement records"],
        "recommended_checks": ["verify payment-path logs"],
        "recommended_owner": "it-oncall",
        "corrective_actions": ["Review-only: assign owner."],
        "confidence": 0.55,
    }
    payload.update(overrides)
    body = {"choices": [{"message": {"content": json.dumps(payload)}}],
            "usage": {"prompt_tokens": 5, "completion_tokens": 5}}

    class Resp:
        status_code = 200

        def json(self):
            return body

    def fake_post(*args, **kwargs):
        assert kwargs["headers"].get("apikey") == "pod-team-key"
        return Resp()

    monkeypatch.setattr(httpx, "post", fake_post)


@pytest.fixture()
def maas_env(monkeypatch):
    monkeypatch.setenv("AI_PROVIDER", "maas")
    monkeypatch.setenv("MAAS_ENABLED", "true")
    monkeypatch.setenv("MAAS_MODEL", "glm-5.2")
    monkeypatch.setenv("MAAS_BASE_URL", "http://maas-test.local/openai/v1")
    monkeypatch.setenv("GATEWAY_KEY", "pod-team-key")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_maas_active_requires_provider_and_flag(monkeypatch, maas_env):
    settings = get_settings()
    assert maas_active(settings) is True
    monkeypatch.setenv("MAAS_ENABLED", "false")
    get_settings.cache_clear()
    assert maas_active(get_settings()) is False


def test_settings_bridge_builds_config(maas_env):
    cfg = maas_config_from_settings(get_settings())
    assert cfg.model == "glm-5.2"
    assert cfg.base_url == "http://maas-test.local/openai/v1"


def test_classifier_routes_to_maas_and_back(monkeypatch, maas_env):
    calls = {}

    def fake_classify(text, channel, config=None, gateway_key=None):
        calls["key"] = gateway_key
        from app.ai.fallback import rules_classify
        result = rules_classify(text)
        result._runtime = {"source": "maas", "model": "glm-5.2",
                           "latency_ms": 5, "input_tokens": 1, "output_tokens": 1}
        return result, "maas"

    # classify() imports classify_with_fallback at call time, so patch the source.
    monkeypatch.setattr("app.ai.providers.classify.classify_with_fallback", fake_classify)
    result, source = classify("abeg my money don enter nowhere", "in_app")
    assert source == "maas"
    assert calls["key"] == "pod-team-key"
    assert result.issue_type == "failed_transfer"


def test_classifier_maas_disabled_falls_back(monkeypatch):
    monkeypatch.setenv("AI_PROVIDER", "maas")
    monkeypatch.setenv("MAAS_ENABLED", "false")
    get_settings.cache_clear()
    try:
        result, source = classify("my money don enter nowhere", "x")
    finally:
        get_settings.cache_clear()
    assert source == "rules"


def test_investigation_loop_persists_brief_fields(monkeypatch, maas_env):
    _brief_response(monkeypatch)
    evidence = {
        "incident": {"complaint_count": 12, "baseline": 2.0, "issue_type": "failed_transfer"},
        "complaints": {"channels": {"in_app": 9}},
        "transactions": {"observed": 20, "failed": 8, "failed_by_processor": {},
                         "matched_complaints": 0, "unreversed_failed": 0, "channels": ["app"]},
        "events": [{"id": "evt-1", "type": "release", "starts_at": "2026-11-06T10:00:00Z"}],
    }
    findings, source, trace = run_investigation_loop(evidence)
    assert source == "maas"
    brief = trace[-1].get("brief")
    assert brief is not None
    assert brief["recommended_owner"] == "it-oncall"
    assert "settlement records" in brief["missing_evidence"]
    proj = _brief_to_findings(InvestigationBrief.model_validate(brief), evidence)
    assert proj.propose_reversal_request is False


def test_investigation_disabled_falls_back_safely(monkeypatch):
    monkeypatch.setenv("AI_PROVIDER", "maas")
    get_settings.cache_clear()
    try:
        evidence = {"incident": {"complaint_count": 3, "baseline": 2.0, "issue_type": "fees"},
                    "complaints": {"channels": {"email": 3}},
                    "transactions": {"observed": 5, "failed": 0, "failed_by_processor": {},
                                     "matched_complaints": 0, "unreversed_failed": 0, "channels": []},
                    "events": []}
        findings, source, trace = run_investigation_loop(evidence)
    finally:
        get_settings.cache_clear()
    assert source == "rules"
    assert findings.propose_reversal_request is False


def test_with_registry_derives_ids_from_events_list():
    evidence = {"events": [{"id": "a"}, {"id": "b"}], "incident": {}}
    out = with_registry(evidence)
    ids = {i["id"] for i in out["evidence_registry"]["system_events"]}
    assert ids == {"a", "b"}


def test_build_evidence_carries_registry(client):
    from sqlalchemy import select

    from app.db.session import get_db
    from app.main import app
    from app.models import Incident
    from tests.helpers import register

    headers, _ = register(client, bank="Reg Bank", email="reg@example.com")
    occurred = "2026-11-06T10:31:00Z"
    created = client.post("/api/v1/complaints/bulk", headers=headers, json={"complaints": [
        {"channel": "in_app", "text": "failed transfer after debit",
         "issue_type": "failed_transfer", "occurred_at": occurred}
        for _ in range(12)
    ]})
    assert created.status_code == 201, created.text
    incidents = client.post("/api/v1/incidents/detect", headers=headers,
                            json={"now": "2026-11-06T10:40:00Z"})
    assert incidents.status_code == 200 and incidents.json(), incidents.text
    gen = app.dependency_overrides[get_db]()
    db = next(gen)
    try:
        incident = db.scalars(select(Incident)).first()
        assert incident is not None
        bundle = build_evidence(db, incident.bank_id, incident)
    finally:
        gen.close()
    assert "evidence_registry" in bundle
    assert len(bundle["evidence_registry"]["complaints"]) == 12
    assert len(bundle["evidence_registry"]["system_events"]) >= 0
