from app.core.config import get_settings
from app.models import Bank, BankAlias, Complaint, SocialReceipt
from app.services.demo_auth import DEMO_BANK_ID
from tests.test_social import ADAPTER, setup


def test_multi_tenant_fanout_for_post_tagging_two_banks(monkeypatch):
    """One X post tagging two registered banks creates two complaints (one per tenant)."""
    client, sessions, engine = setup(monkeypatch)
    try:
        with sessions() as db:
            second_bank = Bank(name="Access Bank", slug="access", contact_email="access@example.com")
            db.add(second_bank)
            db.commit()
            second_bank_id = second_bank.id
            db.add_all([
                BankAlias(bank_id=DEMO_BANK_ID, value="@zymicbank", kind="handle", platform="x"),
                BankAlias(bank_id=second_bank_id, value="@accessbankplc", kind="handle", platform="x"),
            ])
            db.commit()

        # Ingest a native X v2 payload tagging both banks via matching_rules and @handles
        raw_v2 = {
            "data": {
                "id": "1854999999999999999",
                "text": "@zymicbank @accessbankplc my transfer of ₦40,000 failed after debit, call 08031234567",
                "author_id": "778899",
                "created_at": "2026-11-06T10:12:00Z",
            },
            "includes": {"users": [{"id": "778899", "username": "lagos_trader"}]},
            "matching_rules": [
                {"id": "r-1", "tag": f"tenant:{DEMO_BANK_ID}"},
                {"id": "r-2", "tag": f"tenant:{second_bank_id}"},
            ],
        }
        res = client.post("/api/v1/social/x/ingest-raw", json=raw_v2)
        assert res.status_code == 202, res.text
        body = res.json()
        assert body["accepted"] is True
        assert body["duplicate"] is False
        assert body["tenant_fanout_count"] == 2
        assert set(body["bank_ids"]) == {str(DEMO_BANK_ID), str(second_bank_id)}
        assert len(body["complaint_ids"]) == 2

        # Re-sending the same post ID is deduplicated across both tenants
        dup = client.post("/api/v1/social/x/ingest-raw", json=raw_v2).json()
        assert dup["accepted"] is True and dup["duplicate"] is True

        with sessions() as db:
            complaints = db.query(Complaint).all()
            assert len(complaints) == 2
            assert {c.bank_id for c in complaints} == {DEMO_BANK_ID, second_bank_id}
            for c in complaints:
                assert "[PHONE]" in c.text and "08031234567" not in c.text
                assert c.customer_ref.startswith("cust_") and "lagos_trader" not in c.customer_ref
            assert db.query(SocialReceipt).count() == 2
    finally:
        engine.dispose()


def test_idempotent_x_stream_rule_diff_sync(monkeypatch):
    """Rule sync adds rules on first run, is a no-op on second run, and diffs handle updates."""
    client, sessions, engine = setup(monkeypatch)
    try:
        # 1. Initial sync adds the default Zymic Bank X rule
        first_sync = client.post("/api/v1/social/x/sync-rules").json()
        assert len(first_sync["to_add"]) == 1
        assert first_sync["to_delete_ids"] == []
        assert first_sync["is_noop"] is False
        rule = first_sync["to_add"][0]
        assert rule["tag"] == f"tenant:{DEMO_BANK_ID}"
        assert "-is:retweet" in rule["value"]
        assert "@zymicbank" in rule["value"] and "to:zymicbank" in rule["value"]

        # 2. Second sync with unchanged aliases is a strict no-op
        second_sync = client.post("/api/v1/social/x/sync-rules").json()
        assert second_sync["is_noop"] is True
        assert second_sync["to_add"] == []
        assert second_sync["to_delete_ids"] == []
        assert second_sync["unchanged_count"] == 1

        # 3. Updating aliases schedules sync and diffs old rule out + new rule in
        client.put(
            "/api/v1/social/aliases",
            json={
                "aliases": [
                    {"value": "Zymic Bank", "kind": "name"},
                    {"value": "@zymic_support", "kind": "handle", "platform": "x"},
                ]
            },
        )
        third_sync = client.post("/api/v1/social/x/sync-rules").json()
        assert len(third_sync["to_add"]) == 1
        assert "@zymic_support" in third_sync["to_add"][0]["value"]
        assert len(third_sync["to_delete_ids"]) == 1
    finally:
        engine.dispose()


def test_recorded_x_replay_and_spending_cap_guardrail(monkeypatch):
    """Recorded X v2 mentions replay through XAdapter and respect the daily post cap."""
    client, sessions, engine = setup(monkeypatch)
    try:
        replay = client.post(
            "/api/v1/social/x/replay",
            json={"at": "2026-11-06T10:14:00Z", "auto_drain": False},
        )
        assert replay.status_code == 200, replay.text
        data = replay.json()
        assert data["replayed"] == 14
        assert data["accepted"] == 14
        assert data["duplicates"] == 0
        assert data["complaints_created"] >= 14

        # Replaying again is 100% deduplicated
        replay_again = client.post(
            "/api/v1/social/x/replay",
            json={"at": "2026-11-06T10:14:00Z", "auto_drain": False},
        ).json()
        assert replay_again["duplicates"] == 14
        assert replay_again["complaints_created"] == 0

        # Check status endpoint reports reads and estimated spend
        status_body = client.get("/api/v1/social/x/status").json()
        assert status_body["shared_stream_connection"] is True
        assert status_body["reads_today"] == 14
        assert status_body["estimated_cost_today_usd"] == round(14 * 0.005, 4)

        # Lower daily post limit below current reads to verify the spending cap guardrail
        monkeypatch.setattr(get_settings(), "x_daily_post_limit", 10)
        capped = client.post(
            "/api/v1/social/x/ingest-raw",
            json={
                "data": {
                    "id": "1854888888888888888",
                    "text": "@zymicbank failed transfer of 10k",
                    "created_at": "2026-11-06T10:14:00Z",
                }
            },
        ).json()
        assert capped["accepted"] is False
        assert capped["reason"] == "daily_post_cap_reached"
    finally:
        engine.dispose()


def test_live_x_api_v2_sync_and_recent_search_pull(monkeypatch):
    """Verify exact X API v2 request/response shapes for stream rules sync and recent search pull."""
    import httpx

    client, sessions, engine = setup(monkeypatch)
    try:
        # 1. Without X_BEARER_TOKEN, /social/x/pull returns an explicit error by default (no silent fake fallback)
        no_token = client.post(
            "/api/v1/social/x/pull",
            json={"mode": "recent_search", "max_results": 3, "auto_drain": False},
        ).json()
        assert no_token["source"] == "none"
        assert no_token["reason"] == "x_bearer_token_not_configured"

        # When fallback_to_replay=True is explicitly requested, it falls back to recorded replay
        fallback = client.post(
            "/api/v1/social/x/pull",
            json={"mode": "recent_search", "max_results": 3, "fallback_to_replay": True, "auto_drain": False},
        ).json()
        assert fallback["source"] == "replay_fallback"
        assert fallback["replayed"] == 3
        assert fallback["accepted"] == 3

        # 2. Configure X_BEARER_TOKEN and mock httpx.get / httpx.post to verify exact X v2 protocol
        monkeypatch.setattr(get_settings(), "x_bearer_token", "test-x-bearer-token-123")
        captured_calls: list[dict] = []

        class FakeResponse:
            def __init__(self, status_code: int, payload: dict):
                self.status_code = status_code
                self._payload = payload

            def raise_for_status(self):
                if self.status_code >= 400:
                    raise RuntimeError(f"HTTP {self.status_code}")

            def json(self):
                return self._payload

        def fake_get(url, headers=None, params=None, timeout=None):
            captured_calls.append({"method": "GET", "url": url, "headers": headers, "params": params})
            if url.endswith("/tweets/search/stream/rules"):
                return FakeResponse(200, {"data": [], "meta": {"sent": "2026-11-06T10:00:00Z"}})
            if url.endswith("/tweets/search/recent"):
                return FakeResponse(
                    200,
                    {
                        "data": [
                            {
                                "id": "1854777777777777001",
                                "text": "@zymicbank debited ₦25,000 on USSD, receiver never got alert!",
                                "author_id": "990011",
                                "created_at": "2026-11-06T10:15:00Z",
                                "lang": "en",
                            }
                        ],
                        "includes": {
                            "users": [
                                {"id": "990011", "username": "abuja_vendor", "name": "Abuja Vendor"}
                            ]
                        },
                        "meta": {
                            "newest_id": "1854777777777777001",
                            "oldest_id": "1854777777777777001",
                            "result_count": 1,
                        },
                    },
                )
            raise AssertionError(f"Unexpected GET {url}")

        def fake_post(url, headers=None, json=None, timeout=None):
            captured_calls.append({"method": "POST", "url": url, "headers": headers, "json": json})
            if url.endswith("/tweets/search/stream/rules"):
                added = [
                    {"id": "x-live-rule-99", "value": r["value"], "tag": r["tag"]}
                    for r in (json or {}).get("add", [])
                ]
                return FakeResponse(201, {"data": added, "meta": {"summary": {"created": len(added)}}})
            raise AssertionError(f"Unexpected POST {url}")

        monkeypatch.setattr(httpx, "get", fake_get)
        monkeypatch.setattr(httpx, "post", fake_post)

        # Reset stored stream rules first so sync-rules exercises live GET + POST
        sync_res = client.post("/api/v1/social/x/sync-rules").json()
        assert sync_res["mode"] == "live"
        assert sync_res["active_rules"][0]["id"] == "x-live-rule-99"

        # Pull recent mentions via live X API v2 Recent Search
        pull_res = client.post(
            "/api/v1/social/x/pull",
            json={"mode": "recent_search", "max_results": 5, "auto_drain": False},
        ).json()
        assert pull_res["source"] == "live_recent_search"
        assert pull_res["fetched"] == 1
        assert pull_res["accepted_count"] == 1
        assert pull_res["complaints_created"] == 1
        assert pull_res["newest_id"] == "1854777777777777001"

        # Verify exact X API v2 Recent Search query parameters & bearer auth
        search_call = [c for c in captured_calls if c["url"].endswith("/tweets/search/recent")][0]
        assert search_call["headers"]["Authorization"] == "Bearer test-x-bearer-token-123"
        assert search_call["params"]["max_results"] == 10  # clamped to X v2 minimum of 10
        assert set(search_call["params"]["tweet.fields"].split(",")) == {
            "created_at", "author_id", "lang", "public_metrics", "conversation_id",
        }
        assert search_call["params"]["expansions"] == "author_id"
        assert search_call["params"]["user.fields"] == "username,name"
        assert "@zymicbank" in search_call["params"]["query"]

        # Second pull with handle=@myaccessbank and explicit since_id scopes the query to @myaccessbank
        client.get(
            "/api/v1/social/x/pull?handle=@myaccessbank&max_results=15&since_id=1854777777777777001&auto_drain=false",
        )
        second_search = [c for c in captured_calls if c["url"].endswith("/tweets/search/recent")][1]
        assert second_search["params"]["since_id"] == "1854777777777777001"
        assert second_search["params"]["max_results"] == 15
        assert second_search["params"]["query"] == "(@myaccessbank OR to:myaccessbank) -is:retweet"
    finally:
        engine.dispose()


