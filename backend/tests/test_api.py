def test_health(client):
    res = client.get("/api/v1/health")
    assert res.status_code == 200 and res.json()["status"] == "ok"


def test_complaint_is_masked_on_ingest(authed):
    res = authed.post(
        "/api/v1/complaints",
        json={"channel": "x", "text": "Debit no credit, call 08031234567", "customer_ref": "08031234567"},
    )
    assert res.status_code == 201
    body = res.json()
    assert "[PHONE]" in body["text"] and "08031234567" not in body["text"]
    assert body["customer_ref"].startswith("cust_")


def test_classification_roundtrip_and_filters(authed):
    created = authed.post("/api/v1/complaints", json={"channel": "email", "text": "ATM kept my cash"}).json()
    assert authed.get("/api/v1/complaints", params={"unclassified": True}).json()[0]["id"] == created["id"]

    res = authed.patch(
        f"/api/v1/complaints/{created['id']}/classification",
        json={"issue_type": "card_atm", "severity": "high", "sentiment": "negative", "mentioned_amount": "20000"},
    )
    assert res.status_code == 200 and res.json()["issue_type"] == "card_atm"
    assert authed.get("/api/v1/complaints", params={"issue_type": "card_atm"}).json()[0]["id"] == created["id"]
    assert authed.get("/api/v1/complaints", params={"unclassified": True}).json() == []


def test_summary_and_404(authed):
    authed.post("/api/v1/complaints", json={"channel": "x", "text": "hello", "issue_type": "fees"})
    s = authed.get("/api/v1/analytics/summary").json()
    assert s["total_complaints"] == 1 and s["by_issue_type"]["fees"] == 1
    assert authed.get("/api/v1/complaints/00000000-0000-0000-0000-000000000000").status_code == 404
