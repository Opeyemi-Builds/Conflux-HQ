

def test_reconciliation_case_can_be_created_and_resolved(authed):
    complaint = authed.post(
        "/api/v1/complaints",
        json={
            "channel": "x",
            "text": "Transfer of NGN 25000 failed and account was debited",
        },
    )
    assert complaint.status_code == 201, complaint.text

    created = authed.post(
        "/api/v1/reconciliation/exceptions",
        json={
            "complaint_id": complaint.json()["id"],
            "exception_type": "failed_transfer",
            "settlement_status": "failed",
            "amount": "25000",
            "priority": 80,
            "approval_required": True,
        },
    )
    assert created.status_code == 201, created.text
    exception_id = created.json()["id"]

    resolved = authed.patch(
        f"/api/v1/reconciliation/exceptions/{exception_id}",
        json={"status": "resolved", "evidence_summary": "Verified by settlement report"},
    )
    assert resolved.status_code == 200, resolved.text
    assert resolved.json()["resolved_at"] is not None


def test_reconciliation_match_returns_candidates(client, authed):
    complaint = authed.post(
        "/api/v1/complaints",
        json={
            "channel": "x",
            "text": "I was debited NGN 1500 but transfer failed",
            "occurred_at": "2026-01-01T12:00:00Z",
        },
    )
    assert complaint.status_code == 201, complaint.text

    # The test exercises the route contract; transaction setup is performed through
    # the SQLAlchemy session in the service-level tests when the API has no write route.
    match = authed.post(f"/api/v1/reconciliation/complaints/{complaint.json()['id']}/match")
    assert match.status_code == 200, match.text
    assert match.json()["reason"] == "no_confident_match"
    assert match.json()["candidates"] == []


def test_reconciliation_case_is_bank_scoped(client):
    from tests.helpers import register

    alpha_headers, _ = register(client, bank="Alpha Bank", email="alpha@example.com")
    client.headers.update(alpha_headers)
    created = client.post(
        "/api/v1/reconciliation/exceptions",
        json={"exception_type": "unknown_settlement", "priority": 10},
    )
    assert created.status_code == 201
    exception_id = created.json()["id"]

    beta_headers, _ = register(client, bank="Beta Bank", email="beta@example.com")
    client.headers.update(beta_headers)
    assert client.get("/api/v1/reconciliation/exceptions").json() == []
    assert client.patch(
        f"/api/v1/reconciliation/exceptions/{exception_id}",
        json={"status": "resolved"},
    ).status_code == 404


def test_financial_review_requires_independent_admin_and_does_not_resolve_case(authed):
    from tests.helpers import make_token

    prefix = "/api/v1/reconciliation"
    created = authed.post(f"{prefix}/exceptions", json={
        "exception_type": "failed_transfer", "amount": "25000.00",
    })
    assert created.status_code == 201, created.text
    case_id = created.json()["id"]
    proposal_url = f"{prefix}/exceptions/{case_id}/proposals"
    proposal_body = {"kind": "refund", "amount": "25000.00", "reason": "Independent evidence review required"}
    proposal = authed.post(proposal_url, json=proposal_body)
    assert proposal.status_code == 201, proposal.text
    assert authed.post(proposal_url, json=proposal_body).status_code == 409

    decision_url = f"{prefix}/proposals/{proposal.json()['id']}/decision"
    assert authed.post(decision_url, json={"decision": "approved"}).status_code == 403

    for role, expected in (("agent", 403), ("bank_admin", 200)):
        email = f"review-{role.replace('_', '-')}@alpha-bank.com"
        reviewer = authed.post("/api/v1/bank/members", json={
            "email": email, "full_name": "Review Operator", "role": role,
        })
        assert reviewer.status_code == 201, reviewer.text
        reviewer_id = reviewer.json()["id"]
        decision = authed.post(decision_url, headers={
            "Authorization": f"Bearer {make_token(reviewer_id, email)}",
        }, json={"decision": "approved"})
        assert decision.status_code == expected, decision.text

    approved = authed.get(proposal_url).json()[0]
    assert approved["status"] == "approved"
    assert approved["decided_by"] == reviewer_id
    assert approved["execution_enabled"] is False
    cases = authed.get(f"{prefix}/exceptions?status=approval_required").json()
    assert any(case["id"] == case_id and case["resolved_at"] is None for case in cases)
