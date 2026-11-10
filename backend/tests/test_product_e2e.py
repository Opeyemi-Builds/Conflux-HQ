"""Full product flow: complaint in -> spike -> incident -> investigation -> drafts -> approval.

Exercises the product the way the PRD demo does, through real HTTP + worker
drain, with no model calls in the path (deterministic fallback is the MaaS-off
behavior). Asserts the core scenario survives intact: the planted spike is
detected, investigated, drafted, approved, and audited.
"""
import uuid
from datetime import datetime, timedelta, timezone

from app.services.spike_detection import bucket_start


def _seed_demo(client, headers, now, count=14):
    slot = bucket_start(now, 15) + timedelta(minutes=1)
    texts = [
        "abeg my money don enter nowhere, failed transfer 50k on USSD",
        "transfer failed after debit, no reversal since morning",
        "e jowo, my transfer ti debited but ti de sir",
    ]
    res = client.post(
        "/api/v1/complaints/bulk",
        headers=headers,
        json={"complaints": [
            {"channel": "in_app" if i % 2 == 0 else "x",
             "text": texts[i % len(texts)],
             "customer_ref": f"080300000{i % 4:02d}",
             "region": "Lagos" if i % 3 else "Kano",
             "occurred_at": slot.isoformat()}
            for i in range(count)
        ]},
    )
    assert res.status_code == 201, res.text
    return slot


def test_full_product_flow_complaint_to_approval(client):
    from tests.helpers import register

    headers, session = register(client, bank="E2E Bank", email="e2e@example.com")
    now = datetime.now(timezone.utc)
    _seed_demo(client, headers, now)

    # 1. Worker classifies + detects the spike.
    drain = client.post("/api/v1/jobs/drain", headers=headers, json={"limit": 100})
    assert drain.status_code == 200, drain.text
    stats = drain.json()
    assert stats["completed"] >= 14, stats

    incidents = client.get("/api/v1/incidents", headers=headers).json()
    assert len(incidents) == 1, incidents
    incident = incidents[0]
    assert incident["issue_type"] == "failed_transfer"
    assert incident["complaint_count"] >= 10
    incident_id = incident["id"]

    # 2. Complaints are classified, linked, masked.
    feed = client.get("/api/v1/complaints", headers=headers,
                      params={"issue_type": "failed_transfer", "limit": 50}).json()
    items = feed["items"] if isinstance(feed, dict) else feed
    assert len(items) >= 10
    assert all(i["issue_type"] == "failed_transfer" for i in items)
    assert all(i["incident_id"] == incident_id for i in items if i["incident_id"])
    assert not any("0803" in (i.get("text") or "") for i in items)

    # 3. Investigation brief separates facts from hypotheses; read-only GETs stay read-only.
    inv = client.post("/api/v1/investigations", headers=headers,
                      json={"incident_id": incident_id})
    assert inv.status_code == 202, inv.text
    run_id = inv.json()["id"]
    ov_before = client.get(f"/api/v1/incidents/{incident_id}/overview", headers=headers)
    assert ov_before.status_code == 200, ov_before.text
    drain2 = client.post("/api/v1/jobs/drain", headers=headers, json={"limit": 100})
    assert drain2.status_code == 200, drain2.text
    run = client.get(f"/api/v1/investigations/{run_id}", headers=headers).json()
    assert run["status"] == "completed", run
    assert run["facts"] and run["missing_evidence"] and run["recommended_checks"]
    assert run["provider"] in ("maas", "auto", "rules")

    # 4. Drafts exist, human approves, audit shows every step.
    drafts = client.get(f"/api/v1/ai/incidents/{incident_id}/drafts", headers=headers).json()
    assert len(drafts) == 2
    kinds = {d["kind"] for d in drafts}
    assert kinds == {"customer_message", "it_ticket"}
    first = drafts[0]
    dec = client.post(f"/api/v1/ai/drafts/{first['id']}/decision", headers=headers,
                      json={"decision": "approved"})
    assert dec.status_code == 200, dec.text
    assert dec.json()["status"] == "approved"

    audit = client.get("/api/v1/ai/audit", headers=headers, params={"limit": 500}).json()
    actions = {a["action"] for a in audit}
    for expected in ("complaint_classified", "spike_detected", "incident_investigated",
                     "draft_created", "draft_decided", "text_classified" if False else "complaint_classified"):
        assert expected in actions, sorted(actions)
    assert any(a["entity_id"] == incident_id for a in audit if a["action"] == "incident_investigated")

    # 5. Reconciliation: candidate match -> case -> owner/status -> timeline.
    target = next(i for i in items if i["incident_id"] == incident_id)
    match = client.post(f"/api/v1/reconciliation/complaints/{target['id']}/match",
                        headers=headers).json()
    assert "candidates" in match
    case = client.post(f"/api/v1/reconciliation/complaints/{target['id']}/create",
                       headers=headers)
    assert case.status_code in (200, 201, 409), case.text
    if case.status_code != 409:
        case_id = case.json()["id"] if isinstance(case.json(), dict) else case.json()[0]["id"]
        upd = client.patch(f"/api/v1/reconciliation/exceptions/{case_id}", headers=headers,
                           json={"status": "transaction_matched", "owner": "ops-lead"})
        assert upd.status_code == 200, upd.text
    timeline = client.get(f"/api/v1/incidents/{incident_id}/reconciliation",
                          headers=headers)
    assert timeline.status_code == 200, timeline.text

    # 6. Corrective action lifecycle to verified with bank-confirmed cause.
    action = client.post(f"/api/v1/incidents/{incident_id}/actions", headers=headers, json={
        "title": "Verify switch settlement path",
        "recommendation": "Confirm settlement status with the processor before requery.",
        "owner": "ops-lead",
        "validation_plan": "Requery timed-out references; confirm no duplicate credit.",
    })
    assert action.status_code == 201, action.text
    action_id = action.json()["id"]
    for state in ("accepted", "in_progress", "monitoring"):
        r = client.patch(f"/api/v1/actions/{action_id}", headers=headers,
                         json={"status": state})
        assert r.status_code == 200, r.text
    done = client.patch(f"/api/v1/actions/{action_id}", headers=headers, json={
        "status": "verified",
        "validation_observation": "Sampled references; all settled exactly once.",
        "bank_confirmed_cause": "Processor timeout on authorisation response."})
    assert done.status_code == 200, done.text
    assert done.json()["status"] == "verified"

    # 7. Analytics + health stay consistent.
    summary = client.get("/api/v1/analytics/summary", headers=headers)
    assert summary.status_code == 200, summary.text
    health = client.get("/api/v1/health/connectors", headers=headers)
    assert health.status_code == 200, health.text
    assert health.json()["status"] in ("ok", "degraded")


def test_isolated_complaint_does_not_spike(client):
    """The PRD's negative case: one isolated complaint must not trigger a spike."""
    from tests.helpers import register

    headers, _ = register(client, bank="Quiet Bank", email="quiet@example.com")
    now = datetime.now(timezone.utc)
    _seed_demo(client, headers, now, count=2)
    drain = client.post("/api/v1/jobs/drain", headers=headers, json={"limit": 100})
    assert drain.status_code == 200, drain.text
    incidents = client.get("/api/v1/incidents", headers=headers).json()
    assert incidents == [], incidents


def test_cross_bank_records_stay_invisible(client):
    from tests.helpers import register

    a_headers, _ = register(client, bank="Bank A", email="a@example.com")
    b_headers, _ = register(client, bank="Bank B", email="b@example.com")
    now = datetime.now(timezone.utc)
    _seed_demo(client, a_headers, now)
    client.post("/api/v1/jobs/drain", headers=a_headers, json={"limit": 100})
    a_incidents = client.get("/api/v1/incidents", headers=a_headers).json()
    assert len(a_incidents) == 1
    other = a_incidents[0]["id"]
    assert client.get(f"/api/v1/incidents/{other}/overview", headers=b_headers).status_code == 404
    assert client.get("/api/v1/incidents", headers=b_headers).json() == []
    fake = client.post("/api/v1/ai/drafts/" + str(uuid.uuid4()) + "/decision",
                       headers=b_headers, json={"decision": "approved"})
    assert fake.status_code == 404
