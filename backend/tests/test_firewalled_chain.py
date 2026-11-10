"""Firewalled end-to-end chain test: bank ingestion -> worker -> incident -> investigation -> drafts -> approval.

Rules-only by construction:
- Forces AI_PROVIDER=rules + MAAS_ENABLED=false + no keys, so classifier,
  investigation loop, and drafts all take deterministic fallback paths.
- Firewalls the network: any httpx.post (MaaS/Gemini transport) raises,
  so a single LLM call attempt fails the test instead of billing quota
  or hanging the pod.

Run: .venv/Scripts/python.exe -m pytest tests/test_firewalled_chain.py -q
"""
from datetime import timedelta

import httpx
import pytest

from app.core.config import get_settings
from app.services.spike_detection import bucket_start


@pytest.fixture()
def rules_only(monkeypatch):
    """Force deterministic fallback and firewall all outbound HTTP."""
    monkeypatch.setenv("AI_PROVIDER", "rules")
    monkeypatch.setenv("MAAS_ENABLED", "false")
    monkeypatch.delenv("GATEWAY_KEY", raising=False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("MAAS_BASE_URL", raising=False)
    get_settings.cache_clear()

    def _blocked(*args, **kwargs):
        raise AssertionError("network firewalled: LLM transport must not be called")

    monkeypatch.setattr(httpx, "post", _blocked)
    try:
        yield
    finally:
        get_settings.cache_clear()


def _make_connector(client, headers):
    res = client.post(
        "/api/v1/ingestion/connectors",
        headers=headers,
        json={"name": "Chain Sim", "source_system": "zendesk_sim", "synthetic": True},
    )
    assert res.status_code == 201, res.text
    body = res.json()
    assert body["token"].startswith("cfx_conn_")
    return body["token"]


def test_firewalled_chain_ingest_to_approval(client, rules_only):
    from tests.helpers import register

    headers, _ = register(client, bank="Chain Bank", email="chain@example.com")
    token = _make_connector(client, headers)
    conn_headers = {"Authorization": f"Bearer {token}"}

    from datetime import datetime, timezone

    now = datetime.now(timezone.utc)
    slot = bucket_start(now, 15) + timedelta(minutes=1)
    texts = [
        "abeg my money don enter nowhere, failed transfer 50k on USSD",
        "transfer failed after debit, no reversal since morning",
        "e jowo, my transfer ti debited but ti de sir",
    ]
    # 1. Ingest 14 tickets through the bank connector (202 each).
    first_ids = None
    for i in range(14):
        payload = {
            "source_system": "zendesk_sim",
            "external_id": f"CHAIN-{i:03d}",
            "channel": "in_app" if i % 2 == 0 else "call",
            "occurred_at": slot.isoformat(),
            "text": texts[i % len(texts)],
            "customer_ref": f"080300000{i % 4:02d}",
            "region": "Lagos",
            "synthetic": True,
        }
        res = client.post("/api/v1/ingestion/complaints", headers=conn_headers, json=payload)
        assert res.status_code == 202, res.text
        body = res.json()
        assert body["duplicate"] is False
        assert body["processing_status"] == "queued"
        if i == 0:
            first_ids = (payload, body)

    # 2. Idempotent replay (200) + conflict (409) prove receipt semantics.
    payload, body = first_ids
    replay = client.post("/api/v1/ingestion/complaints", headers=conn_headers, json=payload)
    assert replay.status_code == 200, replay.text
    assert replay.json()["duplicate"] is True
    assert replay.json()["complaint_id"] == body["complaint_id"]

    drift = dict(payload)
    drift["text"] = "Customer changed complaint: actually 40000 was debited!"
    conflict = client.post("/api/v1/ingestion/complaints", headers=conn_headers, json=drift)
    assert conflict.status_code == 409, conflict.text

    # 3. Drain: classify (rules) + detect + investigate. No httpx.post may fire.
    drain = client.post("/api/v1/jobs/drain", headers=headers, json={"limit": 100})
    assert drain.status_code == 200, drain.text
    stats = drain.json()
    assert stats["completed"] >= 14, stats
    assert stats["dead_lettered"] == 0, stats

    incidents = client.get("/api/v1/incidents", headers=headers).json()
    assert len(incidents) == 1, incidents
    incident = incidents[0]
    assert incident["issue_type"] == "failed_transfer"
    assert incident["complaint_count"] >= 10
    incident_id = incident["id"]

    # 4. Explicit investigation run stays rules-only.
    inv = client.post("/api/v1/investigations", headers=headers, json={"incident_id": incident_id})
    assert inv.status_code == 202, inv.text
    run_id = inv.json()["id"]
    drain2 = client.post("/api/v1/jobs/drain", headers=headers, json={"limit": 100})
    assert drain2.status_code == 200, drain2.text
    run = client.get(f"/api/v1/investigations/{run_id}", headers=headers).json()
    assert run["status"] == "completed", run
    assert run["provider"] == "rules", run
    assert run["facts"] and run["missing_evidence"] and run["recommended_checks"]

    # 5. Drafts exist (2, no reversal without matched txns), approve one -> outbox.
    drafts = client.get(f"/api/v1/ai/incidents/{incident_id}/drafts", headers=headers).json()
    assert len(drafts) == 2, drafts
    assert {d["kind"] for d in drafts} == {"customer_message", "it_ticket"}
    dec = client.post(
        f"/api/v1/ai/drafts/{drafts[0]['id']}/decision",
        headers=headers,
        json={"decision": "approved"},
    )
    assert dec.status_code == 200, dec.text
    outbox = client.get(
        "/api/v1/jobs", headers=headers, params={"kind": "dispatch_approval", "status": "pending"}
    ).json()
    assert len(outbox) == 1
    drain3 = client.post("/api/v1/jobs/drain", headers=headers, json={"limit": 100})
    assert drain3.json()["completed"] == 1

    # 6. Audit proves every step; PII stays masked.
    audit = client.get("/api/v1/ai/audit", headers=headers, params={"limit": 500}).json()
    actions = {a["action"] for a in audit}
    for expected in (
        "complaint_classified",
        "spike_detected",
        "incident_investigated",
        "draft_created",
        "draft_decided",
    ):
        assert expected in actions, sorted(actions)

    feed = client.get(
        "/api/v1/complaints", headers=headers, params={"issue_type": "failed_transfer", "limit": 50}
    ).json()
    items = feed["items"] if isinstance(feed, dict) else feed
    assert len(items) >= 10
    assert not any("0803" in (i.get("text") or "") for i in items)

    # 7. Receipt API reflects classified status after worker.
    receipts = client.get(
        "/api/v1/ingestion/receipts", headers=headers, params={"limit": 5}
    )
    assert receipts.status_code == 200
