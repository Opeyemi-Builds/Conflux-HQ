from app.ai.classifier import validate_evidence_phrases
from app.ai.fallback import PAYMENT_TO_ISSUE_TYPE, rules_classify
from app.core.privacy import mask_pii
from app.models.enums import IssueType


def test_payment_category_mapping_preserves_existing_issue_types():
    assert set(PAYMENT_TO_ISSUE_TYPE) == {
        "debited_not_credited",
        "failed_transfer",
        "pending_transfer",
        "delayed_settlement",
        "reversed_not_refunded",
        "double_debit",
        "duplicate_payment",
        "card_atm_failure",
        "pos_failure",
        "processor_timeout",
        "switch_outage",
        "fees",
        "fraud_scam",
        "account_takeover",
        "unknown_payment_issue",
    }
    assert all(isinstance(issue_type, IssueType) for issue_type in PAYMENT_TO_ISSUE_TYPE.values())


def test_rules_classify_payment_complaints_with_specific_categories():
    cases = {
        "I was debited but the receiver was not credited": "debited_not_credited",
        "My transfer is still pending": "pending_transfer",
        "My settlement is delayed": "delayed_settlement",
        "The transfer reversed but I was not refunded": "reversed_not_refunded",
        "I made a duplicate payment": "duplicate_payment",
        "ATM debited me but cash did not come out": "card_atm_failure",
        "POS terminal debited my card twice": "pos_failure",
        "The processor timed out during my transfer": "processor_timeout",
        "The payment switch is down": "switch_outage",
        "Why was I charged this fee": "fees",
        "A fake bank agent asked for my OTP": "fraud_scam",
        "Someone took over my account": "account_takeover",
        "My transfer failed": "failed_transfer",
        "I have an issue with a payment": "unknown_payment_issue",
        "How do I apply for a loan": None,
    }

    for text, expected in cases.items():
        result = rules_classify(text)
        assert result.payment_category == expected, text
        assert result.explanation
        assert all(phrase.lower() in text.lower() for phrase in result.evidence_phrases)


def test_invalid_evidence_is_removed_and_caps_confidence():
    result = rules_classify("My transfer failed")
    result.confidence = 0.9
    result.evidence_phrases = ["transfer failed", "not present in complaint"]

    validated = validate_evidence_phrases(result, "My transfer failed")

    assert validated.evidence_phrases == ["transfer failed"]
    assert validated.confidence == 0.9


def test_all_invalid_evidence_is_removed_and_caps_confidence():
    result = rules_classify("My transfer failed")
    result.confidence = 0.9
    result.evidence_phrases = ["made up evidence"]

    validated = validate_evidence_phrases(result, "My transfer failed")

    assert validated.evidence_phrases == []
    assert validated.confidence == 0.5


def test_bvn_is_masked_only_with_nearby_bvn_label():
    assert mask_pii("BVN: 12345678901") == "BVN: [BVN]"
    assert mask_pii("Reference 12345678901") == "Reference 12345678901"


def test_classification_endpoint_persists_specific_fields_and_routes_low_confidence(
    authed, monkeypatch
):
    complaint = authed.post(
        "/api/v1/complaints",
        json={"channel": "in_app", "text": "My transfer failed"},
    ).json()
    result = rules_classify("My transfer failed")
    result.confidence = 0.69
    monkeypatch.setattr(
        "app.api.routes.complaints.ai_classify_complaint_text",
        lambda text, channel: (result, "rules"),
    )

    response = authed.post(f"/api/v1/complaints/{complaint['id']}/classify")

    assert response.status_code == 200
    body = response.json()
    assert body["payment_category"] == "failed_transfer"
    assert body["classification_explanation"]
    assert body["evidence_phrases"] == ["transfer failed"]
    assert body["review_status"] == "needs_review"
    assert body["routing_queue"] == "human_review"


def test_confidence_at_threshold_uses_standard_queue(authed, monkeypatch):
    complaint = authed.post(
        "/api/v1/complaints",
        json={"channel": "in_app", "text": "My transfer failed"},
    ).json()
    result = rules_classify("My transfer failed")
    result.confidence = 0.70
    monkeypatch.setattr(
        "app.api.routes.complaints.ai_classify_complaint_text",
        lambda text, channel: (result, "rules"),
    )

    response = authed.post(f"/api/v1/complaints/{complaint['id']}/classify")

    assert response.status_code == 200
    assert response.json()["review_status"] == "auto"
    assert response.json()["routing_queue"] == "standard"


def test_low_confidence_ad_hoc_classification_requires_review(authed):
    response = authed.post(
        "/api/v1/ai/classify",
        json={"text": "This bank is useless", "channel": "in_app"},
    )

    assert response.status_code == 200
    assert response.json()["review_status"] == "needs_review"
    assert response.json()["routing_queue"] == "human_review"
    assert response.json()["method"] == "rules_fallback"
