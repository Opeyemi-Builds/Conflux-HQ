from datetime import timedelta

from tests.helpers import PASSWORD, make_token, register

API = "/api/v1"


def test_register_creates_bank_and_admin(client, fake_sb):
    headers, body = register(client)
    assert body["bank"]["name"] == "Alpha Bank" and body["bank"]["slug"] == "alpha-bank"
    assert body["user"]["role"] == "bank_admin" and body["email_confirmation_required"] is False
    me = client.get(f"{API}/auth/me", headers=headers).json()
    assert me["email"] == "admin@alpha-bank.com" and me["bank"]["name"] == "Alpha Bank"


def test_register_requires_email_confirmation_when_enabled(client, fake_sb):
    fake_sb.autoconfirm = False
    res = client.post(f"{API}/auth/register", json={
        "bank_name": "Beta Bank", "admin_full_name": "Bo Admin", "email": "bo@beta-bank.com", "password": PASSWORD})
    assert res.status_code == 201
    body = res.json()
    assert body["email_confirmation_required"] is True and body["session"] is None
    login = client.post(f"{API}/auth/login", json={"email": "bo@beta-bank.com", "password": PASSWORD})
    assert login.status_code == 403


def test_duplicate_email_and_duplicate_bank_names(client):
    register(client)
    dup = client.post(f"{API}/auth/register", json={
        "bank_name": "Other", "admin_full_name": "Ada Admin", "email": "ADMIN@alpha-bank.com", "password": PASSWORD})
    assert dup.status_code == 409
    _, second = register(client, bank="Alpha Bank", email="x@alpha-two.com")
    assert second["bank"]["slug"] == "alpha-bank-2"


def test_weak_password_and_bad_email_rejected(client):
    base = {"bank_name": "Gamma", "admin_full_name": "Gi Admin"}
    assert client.post(f"{API}/auth/register", json={**base, "email": "g@gamma.com", "password": "short1"}).status_code == 422
    assert client.post(f"{API}/auth/register", json={**base, "email": "g@gamma.com", "password": "nodigitshere"}).status_code == 422
    assert client.post(f"{API}/auth/register", json={**base, "email": "not-an-email", "password": PASSWORD}).status_code == 422


def test_login_refresh_and_wrong_password(client):
    register(client)
    ok = client.post(f"{API}/auth/login", json={"email": "admin@alpha-bank.com", "password": PASSWORD})
    assert ok.status_code == 200 and ok.json()["user"]["bank"]["name"] == "Alpha Bank"
    bad = client.post(f"{API}/auth/login", json={"email": "admin@alpha-bank.com", "password": "Wrong1234"})
    assert bad.status_code == 401 and bad.json()["detail"] == "Invalid email or password"
    refreshed = client.post(f"{API}/auth/refresh", json={"refresh_token": ok.json()["refresh_token"]})
    assert refreshed.status_code == 200 and refreshed.json()["access_token"]
    assert client.post(f"{API}/auth/refresh", json={"refresh_token": "nope"}).status_code == 401


def test_protected_routes_reject_missing_bad_and_expired_tokens(client, fake_sb):
    headers, body = register(client)
    assert client.get(f"{API}/complaints").status_code == 401
    assert client.get(f"{API}/complaints", headers={"Authorization": "Bearer garbage"}).status_code == 401
    expired = make_token(body["user"]["id"], "admin@alpha-bank.com", minutes=-5)
    assert client.get(f"{API}/complaints", headers={"Authorization": f"Bearer {expired}"}).status_code == 401
    stranger = make_token("00000000-0000-0000-0000-000000000001", "x@y.com")
    assert client.get(f"{API}/complaints", headers={"Authorization": f"Bearer {stranger}"}).status_code == 403


def test_banks_cannot_see_each_others_data(client):
    a, _ = register(client, bank="Alpha Bank", email="admin@alpha-bank.com")
    b, _ = register(client, bank="Beta Bank", email="admin@beta-bank.com")
    created = client.post(f"{API}/complaints", headers=a, json={"channel": "x", "text": "ATM kept my cash"}).json()
    assert len(client.get(f"{API}/complaints", headers=a).json()) == 1
    assert client.get(f"{API}/complaints", headers=b).json() == []
    assert client.get(f"{API}/complaints/{created['id']}", headers=b).status_code == 404
    assert client.patch(f"{API}/complaints/{created['id']}/classification", headers=b,
                        json={"issue_type": "fees"}).status_code == 404
    assert client.get(f"{API}/analytics/summary", headers=b).json()["total_complaints"] == 0


def test_invite_flow_roles_and_last_admin_guard(client, fake_sb):
    admin, body = register(client)
    inv = client.post(f"{API}/bank/members", headers=admin,
                      json={"email": "mo@alpha-bank.com", "full_name": "Mo Manager", "role": "manager"})
    assert inv.status_code == 201 and inv.json()["status"] == "invited"

    fake_sb.users["mo@alpha-bank.com"].update(password=PASSWORD, confirmed=True)  # invitee accepts
    login = client.post(f"{API}/auth/login", json={"email": "mo@alpha-bank.com", "password": PASSWORD})
    assert login.status_code == 200 and login.json()["user"]["status"] == "active"
    mgr = {"Authorization": "Bearer " + login.json()["access_token"]}

    # manager is read-only and cannot administer the bank
    assert client.get(f"{API}/complaints", headers=mgr).status_code == 200
    assert client.post(f"{API}/complaints", headers=mgr, json={"channel": "x", "text": "hi"}).status_code == 403
    assert client.post(f"{API}/bank/members", headers=mgr,
                       json={"email": "z@alpha-bank.com", "full_name": "Zed Zed"}).status_code == 403
    assert len(client.get(f"{API}/bank/members", headers=mgr).json()) == 2

    # the only admin cannot demote or disable themselves
    me_id = body["user"]["id"]
    assert client.patch(f"{API}/bank/members/{me_id}", headers=admin, json={"role": "agent"}).status_code == 400
    assert client.patch(f"{API}/bank/members/{me_id}", headers=admin, json={"status": "disabled"}).status_code == 400

    # disabling a member locks them out immediately
    mo_id = login.json()["user"]["id"]
    assert client.patch(f"{API}/bank/members/{mo_id}", headers=admin, json={"status": "disabled"}).status_code == 200
    assert client.get(f"{API}/complaints", headers=mgr).status_code == 403


def test_admin_can_update_bank_profile(client):
    admin, _ = register(client)
    res = client.patch(f"{API}/bank", headers=admin, json={"name": "Alpha Bank Plc", "cac_number": "RC123456"})
    assert res.status_code == 200 and res.json()["name"] == "Alpha Bank Plc"
