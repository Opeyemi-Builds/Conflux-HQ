"""Andrew's grounded-investigation tests: evidence IDs, hypotheses, fallback, tenancy."""
import json

import httpx
import pytest

from app.ai.clustering import cluster_complaints, jaccard
from app.ai.investigation import (
    InvestigationBrief,
    fallback_brief,
    investigate_with_fallback,
    maas_investigate,
    validate_brief,
)
from app.ai.providers.classify import classify_with_fallback
from app.ai.providers.maas import MaasConfig, MaasError


def _evidence(**overrides):
    bundle = {
        "incident": {"issue_type": "failed_transfer", "complaint_count": 12, "baseline": 2.0},
        "complaints": {"count": 12, "channels": {"in_app": 9, "x": 3}},
        "transactions": {"observed": 20, "failed": 8, "unreversed_failed": 5},
        "events": [{"type": "release", "version": "v4.2.1", "starts_at": "2026-11-06T10:00:00Z"}],
        "evidence_registry": {
            "complaints": [{"id": "cmp-1"}, {"id": "cmp-2"}],
            "system_events": [{"id": "evt-release-421"}],
            "transactions": [{"id": "txn-9"}],
        },
    }
    bundle.update(overrides)
    return bundle


def _brief_payload(**overrides):
    base = {
        "observed_facts": ["12 complaints vs baseline 2.0 for failed_transfer."],
        "hypotheses": [{"statement": "Release v4.2.1 preceded the spike; cause unconfirmed.",
                        "confidence": 0.55, "evidence_ids": ["evt-release-421"]}],
        "supporting_evidence_ids": ["evt-release-421"],
        "contradicting_evidence_ids": [],
        "missing_evidence": ["payment settlement records"],
        "recommended_checks": ["verify payment-path logs"],
        "recommended_owner": "it-oncall",
        "corrective_actions": ["Review-only: assign owner. Execution disabled."],
        "confidence": 0.55,
    }
    base.update(overrides)
    return base


def test_valid_brief_cites_only_registry_ids():
    brief = validate_brief(_brief_payload(), _evidence())
    assert isinstance(brief, InvestigationBrief)
    assert brief.supporting_evidence_ids == ["evt-release-421"]


def test_fabricated_evidence_id_rejected(monkeypatch):
    with pytest.raises(MaasError):
        validate_brief(_brief_payload(supporting_evidence_ids=["evt-does-not-exist"]),
                       _evidence())


def test_fabricated_hypothesis_evidence_rejected():
    payload = _brief_payload(hypotheses=[
        {"statement": "Ghost cause.", "confidence": 0.9, "evidence_ids": ["ghost-1"]}])
    with pytest.raises(MaasError):
        validate_brief(payload, _evidence())


def test_missing_evidence_listed_explicitly():
    brief = validate_brief(_brief_payload(), _evidence())
    assert "payment settlement records" in brief.missing_evidence


def test_maas_success_returns_telemetry_without_secrets(monkeypatch):
    body = {"choices": [{"message": {"content": json.dumps(_brief_payload())}}],
            "usage": {"prompt_tokens": 30, "completion_tokens": 12}}

    class Resp:
        status_code = 200

        def json(self):
            return body

    def fake_post(*a, **k):
        assert k["headers"]["apikey"] == "team-key"
        return Resp()

    monkeypatch.setattr(httpx, "post", fake_post)
    brief, telemetry = maas_investigate(_evidence(), config=MaasConfig(), gateway_key="team-key")
    assert brief.confidence == pytest.approx(0.55)
    assert telemetry["source"] == "maas" and telemetry["model"] == "glm-5.2"
    assert "team-key" not in json.dumps(telemetry)


def test_maas_failure_falls_back_without_losing_evidence(monkeypatch):
    def fake_post(*a, **k):
        raise httpx.ConnectTimeout("down", request=None)

    monkeypatch.setattr(httpx, "post", fake_post)
    brief, source, _ = investigate_with_fallback(_evidence(), gateway_key="k")
    assert source == "rules"
    assert any("12 complaints" in f for f in brief.observed_facts)
    assert brief.confidence <= 0.5


def test_fallback_never_moves_money_or_confirms_cause():
    brief = fallback_brief(_evidence())
    text = json.dumps(brief.model_dump())
    assert "Execution disabled; no money movement" in text
    assert "correlation, not causation" in text


def test_clustering_preserves_ids_and_bounds_groups():
    items = [
        {"id": "a", "text": "my money don enter nowhere failed transfer", "issue_type": "failed_transfer"},
        {"id": "b", "text": "money don enter nowhere failed transfer ussd", "issue_type": "failed_transfer"},
        {"id": "c", "text": "atm swallowed my card no cash", "issue_type": "card_atm"},
    ]
    clusters = cluster_complaints(items)
    assert {m for c in clusters for m in c.members} == {"a", "b", "c"}
    assert all("not proof of a common cause" in c.note for c in clusters)
    assert jaccard(items[0]["text"], items[2]["text"]) < 0.35


def test_tenant_isolation_bank_scoped_bundle():
    bank_a, bank_b = _evidence(), _evidence()
    bank_b["evidence_registry"] = {"complaints": [{"id": "other-bank-cmp"}]}
    with pytest.raises(MaasError):
        validate_brief(_brief_payload(), bank_b)  # bank A's IDs unknown in bank B
