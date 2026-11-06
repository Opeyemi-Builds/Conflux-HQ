import uuid
from datetime import datetime, timedelta, timezone

import jwt

from app.services.supabase_client import SignUpResult, SupabaseError

TEST_SECRET = "test-secret-test-secret-test-secret-123456"
PASSWORD = "Passw0rd!x"


def make_token(user_id: str, email: str, minutes: int = 60) -> str:
    now = datetime.now(timezone.utc)
    claims = {"sub": user_id, "email": email, "aud": "authenticated", "iat": now, "exp": now + timedelta(minutes=minutes)}
    return jwt.encode(claims, TEST_SECRET, algorithm="HS256")


class FakeSupabase:
    """Stands in for Supabase Auth in tests, issuing real HS256 tokens our verifier accepts."""

    def __init__(self):
        self.users: dict[str, dict] = {}
        self.autoconfirm = True
        self.deleted: list[str] = []

    def _session(self, u: dict) -> dict:
        return {
            "access_token": make_token(u["id"], u["email"]), "refresh_token": "r-" + u["id"],
            "token_type": "bearer", "expires_in": 3600, "user": {"id": u["id"], "email": u["email"]},
        }

    def sign_up(self, email, password, metadata):
        if email in self.users:
            raise SupabaseError(422, "user_already_exists", "User already registered")
        u = {"id": str(uuid.uuid4()), "email": email, "password": password, "confirmed": self.autoconfirm}
        self.users[email] = u
        return SignUpResult(u["id"], self._session(u) if u["confirmed"] else None)

    def password_login(self, email, password):
        u = self.users.get(email)
        if not u or u["password"] != password:
            raise SupabaseError(400, "invalid_credentials", "Invalid login credentials")
        if not u["confirmed"]:
            raise SupabaseError(400, "email_not_confirmed", "Email not confirmed")
        return self._session(u)

    def refresh(self, refresh_token):
        uid = refresh_token.removeprefix("r-")
        for u in self.users.values():
            if u["id"] == uid:
                return self._session(u)
        raise SupabaseError(400, "refresh_token_not_found", "Invalid Refresh Token")

    def invite(self, email, metadata):
        if email in self.users:
            raise SupabaseError(422, "email_exists", "exists")
        u = {"id": str(uuid.uuid4()), "email": email, "password": None, "confirmed": False}
        self.users[email] = u
        return u["id"]

    def delete_user(self, user_id):
        self.deleted.append(user_id)


def register(client, bank="Alpha Bank", email="admin@alpha-bank.com", password=PASSWORD):
    res = client.post("/api/v1/auth/register", json={
        "bank_name": bank, "admin_full_name": "Ada Admin", "email": email, "password": password,
    })
    assert res.status_code == 201, res.text
    body = res.json()
    return {"Authorization": "Bearer " + body["session"]["access_token"]}, body
