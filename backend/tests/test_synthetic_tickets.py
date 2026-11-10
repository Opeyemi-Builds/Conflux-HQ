"""Tests verifying synthetic bank ticket fixtures and generator behavior."""
import json
from pathlib import Path

from app.services.synthetic_tickets import DATA_OUTPUT_PATH, generate_bank_tickets


def test_generator_determinism():
    tickets1 = generate_bank_tickets(seed=123)
    tickets2 = generate_bank_tickets(seed=123)
    assert json.dumps(tickets1) == json.dumps(tickets2)


def test_fixtures_contain_forge_triggers_and_decimal_amounts():
    tickets = generate_bank_tickets(seed=42)
    scenarios = {t["scenario"]: t for t in tickets}

    # 1. Forge .02 timeout trigger fixture
    assert "forge_timeout_reversal_trigger" in scenarios
    t_02 = scenarios["forge_timeout_reversal_trigger"]["payload"]
    assert t_02["amount"] == "25000.02"
    assert t_02["currency"] == "NGN"
    assert t_02["synthetic"] is True

    # 2. Forge .05 webhook withheld trigger fixture
    assert "forge_webhook_withheld_trigger" in scenarios
    t_05 = scenarios["forge_webhook_withheld_trigger"]["payload"]
    assert t_05["amount"] == "18000.05"
    assert t_05["currency"] == "NGN"

    # 3. Conflict fixture expects 409
    assert "conflicting_replay_drift" in scenarios
    assert scenarios["conflicting_replay_drift"]["expect_status"] == 409

    # 4. Replay fixture expects 200
    assert "identical_replay" in scenarios
    assert scenarios["identical_replay"]["expect_status"] == 200

    # 5. All payloads have string amounts or None (NO floats)
    for t in tickets:
        p = t["payload"]
        if p["amount"] is not None:
            assert isinstance(p["amount"], str)
            assert "." in p["amount"]

    # 6. Committed fixture file exists and matches
    assert DATA_OUTPUT_PATH.exists()
    file_content = json.loads(DATA_OUTPUT_PATH.read_text(encoding="utf-8"))
    assert len(file_content) == len(tickets)

