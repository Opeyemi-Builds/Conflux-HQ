import uuid

from app.ai.fraud import route_fraud
from app.ai.fallback import rules_classify
from app.models import Incident, Profile
from app.models.enums import IncidentStatus, IssueType, UserRole
from app.services.complaint_service import apply_classification
from app.schemas.complaint import ComplaintClassification
from tests.helpers import make_token, register


def test_fraud_routing_priorities_for_known_person_unknown_debit_and_otp():
    known_person = route_fraud(rules_classify("My brother used my card"), "My brother used my card")
    unknown_debit = route_fraud(rules_classify("Unknown debit of N50k"), "Unknown debit of N50k")
    otp = route_fraud(rules_classify("A fake bank agent asked for my OTP"), "A fake bank agent asked for my OTP")

    assert known_person.routed and known_person.priority == "low"
    assert unknown_debit.routed and unknown_debit.priority == "critical"
    assert otp.routed and otp.priority in {"critical", "high"}


def test_twenty_synthetic_fraud_complaints_route_to_security_queue(authed):
    examples = [
        "A fake bank agent asked for my OTP",
        "Someone sent me a phishing link for my banking account",
        "My SIM swap gave someone access to my account",
        "I did not authorize this transfer from my account",
        "Someone took over my account",
        "Unknown debit of N50k",
        "A caller claiming to be bank staff requested my OTP",
        "Fake bank staff called and asked for my password",
        "Someone hacked my account and moved my money",
        "I received a suspicious phishing link by SMS",
        "Unauthorised transfer happened after a SIM swap",
        "A scammer asked me to share my OTP",
        "Someone accessed my account without permission",
        "Fake agent says send OTP before they reverse the debit",
        "I see an unknown debit on my statement",
        "Account takeover after SIM swap, abeg help",
        "Person called me claiming to be from the bank and asked for OTP",
        "Yaudarar fake bank agent asked for OTP",
        "Someone stole my login and transferred money",
        "My brother used my card without asking me",
    ]

    for text in examples:
        complaint = authed.post(
            "/api/v1/complaints",
            json={"channel": "in_app", "text": text},
        ).json()
        response = authed.post(f"/api/v1/complaints/{complaint['id']}/classify")
        assert response.status_code == 200, response.text
        assert response.json()["routing_queue"] == "fraud_security", text

    cases = authed.get("/api/v1/fraud/cases").json()
    assert cases["total"] == 20
    assert len(cases["items"]) == 20
    assert all(item["priority"] in {"critical", "high", "medium", "low"} for item in cases["items"])


def test_fraud_case_creation_is_idempotent_and_repeat_count_uses_pseudonymous_ref(authed):
    text = "Unknown debit of N50k"
    first = authed.post(
        "/api/v1/complaints",
        json={"channel": "in_app", "text": text, "customer_ref": "customer-one"},
    ).json()
    first_case = authed.post(f"/api/v1/complaints/{first['id']}/classify").json()
    repeated = authed.post(f"/api/v1/complaints/{first['id']}/classify")
    assert repeated.status_code == 200
    assert authed.get("/api/v1/fraud/cases").json()["total"] == 1

    second = authed.post(
        "/api/v1/complaints",
        json={"channel": "call", "text": text, "customer_ref": "customer-one"},
    ).json()
    authed.post(f"/api/v1/complaints/{second['id']}/classify")

    cases = authed.get("/api/v1/fraud/cases").json()["items"]
    assert len(cases) == 2
    assert {case["repeat_count"] for case in cases} == {2}
    assert first_case["routing_queue"] == "fraud_security"


def test_non_fraud_complaint_does_not_create_fraud_case(authed):
    complaint = authed.post(
        "/api/v1/complaints",
        json={"channel": "in_app", "text": "My transfer failed"},
    ).json()
    authed.post(f"/api/v1/complaints/{complaint['id']}/classify")
    assert authed.get("/api/v1/fraud/cases").json()["total"] == 0


def test_fraud_routes_require_auth_and_are_tenant_scoped(authed, client):
    alpha_authorization = authed.headers["Authorization"]
    client.headers.pop("Authorization", None)
    assert client.get("/api/v1/fraud/cases").status_code == 401

    client.headers["Authorization"] = alpha_authorization
    complaint = authed.post(
        "/api/v1/complaints",
        json={"channel": "in_app", "text": "A fake bank agent asked for my OTP"},
    ).json()
    authed.post(f"/api/v1/complaints/{complaint['id']}/classify")
    case = authed.get("/api/v1/fraud/cases").json()["items"][0]

    beta_headers, _ = register(client, bank="Beta Bank", email="admin@beta.example")
    client.headers.update(beta_headers)
    assert client.get("/api/v1/fraud/cases").json()["total"] == 0
    assert client.get(f"/api/v1/fraud/cases/{case['id']}").status_code == 404
    assert client.patch(
        f"/api/v1/fraud/cases/{case['id']}",
        json={"status": "under_review"},
    ).status_code == 404


def test_fraud_patch_audits_status_and_manager_is_read_only(authed, client):
    complaint = authed.post(
        "/api/v1/complaints",
        json={"channel": "in_app", "text": "A fake bank agent asked for my OTP"},
    ).json()
    authed.post(f"/api/v1/complaints/{complaint['id']}/classify")
    case = authed.get("/api/v1/fraud/cases").json()["items"][0]
    changed = authed.patch(
        f"/api/v1/fraud/cases/{case['id']}",
        json={"status": "under_review"},
    )
    assert changed.status_code == 200
    assert changed.json()["status"] == "under_review"
    assert authed.patch(
        f"/api/v1/fraud/cases/{case['id']}",
        json={"status": "not-a-status"},
    ).status_code == 422

    me = authed.get("/api/v1/auth/me").json()
    from app.db.session import get_db
    from app.main import app

    db_gen = app.dependency_overrides[get_db]()
    db = next(db_gen)
    try:
        profile = Profile(
            id=uuid.uuid4(),
            bank_id=uuid.UUID(me["bank"]["id"]),
            email="manager@alpha.example",
            full_name="Read Only Manager",
            role=UserRole.MANAGER,
        )
        db.add(profile)
        db.commit()
        token = make_token(str(profile.id), profile.email)
    finally:
        db.close()
    client.headers["Authorization"] = f"Bearer {token}"
    assert client.get(f"/api/v1/fraud/cases/{case['id']}").status_code == 200
    assert client.patch(
        f"/api/v1/fraud/cases/{case['id']}",
        json={"status": "closed_resolved"},
    ).status_code == 403

    client.headers["Authorization"] = authed.headers["Authorization"]
    audit = authed.get("/api/v1/ai/audit").json()
    assert any(row["action"] == "fraud_case_status_changed" for row in audit)


def test_fraud_case_does_not_create_customer_draft(authed):
    from app.db.session import get_db
    from app.main import app
    from app.ai.drafts import create_drafts

    me = authed.get("/api/v1/auth/me").json()
    db_gen = app.dependency_overrides[get_db]()
    db = next(db_gen)
    try:
        incident = Incident(
            bank_id=uuid.UUID(me["bank"]["id"]),
            issue_type=IssueType.FRAUD_SCAM,
            status=IncidentStatus.OPEN,
            started_at=__import__("datetime").datetime.now(__import__("datetime").timezone.utc),
            complaint_count=1,
        )
        db.add(incident)
        db.commit()
        drafts = create_drafts(db, incident.bank_id, incident)
        assert all(draft.kind.value != "customer_message" for draft in drafts)
    finally:
        db.close()
