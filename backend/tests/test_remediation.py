"""Opeyemi integration slice: corrective actions, investigation runs, overview, health."""
import uuid
from datetime import datetime, timedelta, timezone

from app.models.enums import IssueType


def seed_incident(client):
    """Seed one classified complaint, run detection, return the incident id."""
    now = datetime.now(timezone.utc)
    created = []
    for i in range(12):
        r = client.post(
            "/api/v1/complaints",
            json={
                "channel": "in_app",
                "text": f"Transfer of NGN 25000 failed and account debited {i}",
                "occurred_at": (now - timedelta(minutes=5)).isoformat(),
                "issue_type": "failed_transfer",
            },
        )
        assert r.status_code == 201, r.text
        created.append(r.json()["id"])
    detected = client.post("/api/v1/incidents/detect")
    assert detected.status_code == 200, detected.text
    incidents = client.get("/api/v1/incidents").json()
    assert incidents, "detection should create an incident for 12 same-bucket complaints"
    return incidents[0]["id"]


def test_corrective_action_lifecycle_and_verify_rules(authed):
    incident_id = seed_incident(authed)

    # Create
    created = authed.post(
        f"/api/v1/incidents/{incident_id}/actions",
        json={
            "title": "Engage switch vendor on timeout handling",
            "recommendation": "Confirm settlement status with the processor before requerying timed-out transfers.",
            "owner": "ops-lead",
            "validation_plan": "Requery a sample of timed-out references and confirm no duplicate credit.",
        },
    )
    assert created.status_code == 201, created.text
    action = created.json()
    assert action["status"] == "proposed"
    action_id = action["id"]

    # Invalid jump proposed -> monitoring must 409
    bad = authed.patch(f"/api/v1/actions/{action_id}", json={"status": "monitoring"})
    assert bad.status_code == 409

    # Walk the legal path
    for state in ("accepted", "in_progress", "monitoring"):
        r = authed.patch(f"/api/v1/actions/{action_id}", json={"status": state})
        assert r.status_code == 200, r.text
        assert r.json()["status"] == state

    # Verify without validation observation must 422
    noval = authed.patch(f"/api/v1/actions/{action_id}", json={"status": "verified"})
    assert noval.status_code == 422

    # Verify with evidence as bank_admin (authed fixture is admin) succeeds
    ok = authed.patch(
        f"/api/v1/actions/{action_id}",
        json={
            "status": "verified",
            "validation_observation": "Sampled 50 timed-out references; all settled exactly once.",
            "bank_confirmed_cause": "Processor timeout on authorisation response.",
        },
    )
    assert ok.status_code == 200, ok.text
    body = ok.json()
    assert body["status"] == "verified"
    assert body["verified_by"] is not None
    assert body["verified_at"] is not None

    # Terminal state cannot move
    stuck = authed.patch(f"/api/v1/actions/{action_id}", json={"status": "in_progress"})
    assert stuck.status_code == 409


def test_verify_requires_bank_admin(authed):
    incident_id = seed_incident(authed)
    created = authed.post(
        f"/api/v1/incidents/{incident_id}/actions",
        json={"title": "Check settlement file", "recommendation": "Reconcile the daily settlement file line by line."},
    )
    action_id = created.json()["id"]
    for state in ("accepted", "in_progress", "monitoring"):
        assert authed.patch(f"/api/v1/actions/{action_id}", json={"status": state}).status_code == 200

    member = authed.post(
        "/api/v1/bank/members",
        json={"email": "ops-agent@example.com", "full_name": "Ops Agent", "role": "agent"},
    )
    assert member.status_code == 201, member.text

    from tests.helpers import make_token

    agent_token = make_token(member.json()["id"], "ops-agent@example.com")
    r = authed.patch(
        f"/api/v1/actions/{action_id}",
        headers={"Authorization": f"Bearer {agent_token}"},
        json={
            "status": "verified",
            "validation_observation": "Checked.",
            "bank_confirmed_cause": "Timeout.",
        },
    )
    assert r.status_code == 403


def test_investigation_request_queues_one_job_and_get_is_readonly(authed):
    incident_id = seed_incident(authed)

    before = authed.get(f"/api/v1/incidents/{incident_id}/investigations").json()
    assert before == []

    req = authed.post("/api/v1/investigations", json={"incident_id": incident_id})
    assert req.status_code == 202, req.text
    run_id = req.json()["id"]
    assert req.json()["status"] == "requested"

    # GET overview must not create new runs or jobs
    ov1 = authed.get(f"/api/v1/incidents/{incident_id}/overview")
    assert ov1.status_code == 200, ov1.text
    ov2 = authed.get(f"/api/v1/incidents/{incident_id}/overview")
    assert ov2.status_code == 200, ov2.text
    runs = authed.get(f"/api/v1/incidents/{incident_id}/investigations").json()
    assert len(runs) == 1
    assert runs[0]["id"] == run_id

    # Drain runs the queued investigation; the run completes with facts/hypotheses split
    drained = authed.post("/api/v1/jobs/drain", json={"limit": 100})
    assert drained.status_code == 200, drained.text
    got = authed.get(f"/api/v1/investigations/{run_id}").json()
    assert got["status"] == "completed"
    assert isinstance(got["facts"], list) and isinstance(got["hypotheses"], list)

    # Overview payload shape for tomorrow's frontend
    ov = ov2.json()
    assert ov["incident_id"] == incident_id
    assert "complaints" in ov and "social_corroboration" in ov
    assert "payment_evidence" in ov and "corrective_actions" in ov
    assert "note" in ov["payment_evidence"] or "timeline" in ov["payment_evidence"]


def test_cross_bank_isolation(client):
    from tests.helpers import register

    alpha_headers, _ = register(client, bank="Alpha Bank", email="alpha@example.com")
    client.headers.update(alpha_headers)
    incident_id = seed_incident(client)

    beta_headers, _ = register(client, bank="Beta Bank", email="beta@example.com")
    client.headers.update(beta_headers)
    assert client.get(f"/api/v1/incidents/{incident_id}/overview").status_code == 404
    assert client.post("/api/v1/investigations", json={"incident_id": incident_id}).status_code == 404
    assert client.get("/api/v1/connectors/health").status_code == 200


def test_connector_health_reports_states(authed):
    r = authed.get("/api/v1/health/connectors")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] in ("ok", "degraded")
    assert "providers" in body and "database" in body["providers"]
