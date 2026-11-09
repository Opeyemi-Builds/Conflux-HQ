"""Deterministic synthetic bank support ticket generator tailored to Forge 2026 specs."""
import json
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path


DATA_OUTPUT_PATH = Path(__file__).resolve().parents[3] / "data" / "synthetic" / "bank_tickets.json"


def generate_bank_tickets(seed: int = 42, base_time: datetime | None = None) -> list[dict]:
    """Generate a reproducible, labelled fixture set for bank complaint ingestion.
    
    Includes:
    - Call center tickets (English & Nigerian English)
    - In-app chat tickets (Pidgin English)
    - Forge Sandbox .02 trigger (Timeout then reversed)
    - Forge Sandbox .05 trigger (Webhook withheld)
    - Conflict fixture (Same external_id with modified text, expects 409)
    - Cross-bank fixture (Expects cross-bank isolation)
    - Late-arrival ticket (Simulated by delivery timing)
    """
    rng = random.Random(seed)
    anchor = (base_time or datetime(2026, 11, 9, 10, 0, 0, tzinfo=timezone.utc)).astimezone(timezone.utc)

    fixtures: list[dict] = []

    # 1. Forge 2026 Timeout Trigger (.02) - Interbank App Transfer
    fixtures.append({
        "scenario": "forge_timeout_reversal_trigger",
        "expect_status": 202,
        "payload": {
            "source_system": "zendesk_sim",
            "external_id": "TCK-SIM-20261109-001",
            "channel": "in_app",
            "occurred_at": (anchor - timedelta(minutes=15)).isoformat(),
            "text": "My transfer of ₦25,000.02 to Chukwuemeka Nwosu (GTBank 0123987001) failed after debit. App showed network error but I was debited. Please reverse my money.",
            "customer_ref": "crm-cust-9901",
            "payment_reference": "TRF-20261109-0002",
            "amount": "25000.02",
            "currency": "NGN",
            "region": "Lagos",
            "language": "en",
            "synthetic": True,
        },
        "deliver_after_seconds": 0,
    })

    # 2. Forge 2026 Webhook Withheld Trigger (.05) - Call Center
    fixtures.append({
        "scenario": "forge_webhook_withheld_trigger",
        "expect_status": 202,
        "payload": {
            "source_system": "crm_call_center",
            "external_id": "TCK-SIM-20261109-002",
            "channel": "call_center",
            "occurred_at": (anchor - timedelta(minutes=20)).isoformat(),
            "text": "Customer called from Abuja: Transferred ₦18,000.05 to Tamunotonye Briggs (UBA 0123987004). Money left account but beneficiary hasn't received value. Ref TRF-20261109-0005.",
            "customer_ref": "crm-cust-9902",
            "payment_reference": "TRF-20261109-0005",
            "amount": "18000.05",
            "currency": "NGN",
            "region": "Abuja",
            "language": "en",
            "synthetic": True,
        },
        "deliver_after_seconds": 2,
    })

    # 3. Call Center Ingestion - Double Debit Issue
    fixtures.append({
        "scenario": "call_center_double_debit",
        "expect_status": 202,
        "payload": {
            "source_system": "crm_call_center",
            "external_id": "TCK-SIM-20261109-003",
            "channel": "call",
            "occurred_at": (anchor - timedelta(minutes=35)).isoformat(),
            "text": "Caller complains of duplicate debit of ₦12,500.00 at Kano Agro Hub POS. Account was charged twice for a single transaction. Contact phone 08031234567.",
            "customer_ref": "crm-cust-9903",
            "payment_reference": "POS-20261109-1081",
            "amount": "12500.00",
            "currency": "NGN",
            "region": "Kano",
            "language": "en",
            "synthetic": True,
        },
        "deliver_after_seconds": 5,
    })

    # 4. In-App Support Ticket in Pidgin English - Failed Transfer
    fixtures.append({
        "scenario": "in_app_pidgin_failed_transfer",
        "expect_status": 202,
        "payload": {
            "source_system": "zendesk_sim",
            "external_id": "TCK-SIM-20261109-004",
            "channel": "in_app",
            "occurred_at": (anchor - timedelta(minutes=10)).isoformat(),
            "text": "Abeg I send ₦50,000 to my mama account for morning since 8am, money don comot for my balance but mama never see alert. Wetin dey happen? Ref na TRF-20261109-0020.",
            "customer_ref": "crm-cust-9904",
            "payment_reference": "TRF-20261109-0020",
            "amount": "50000.00",
            "currency": "NGN",
            "region": "Port Harcourt",
            "language": "pcm",
            "synthetic": True,
        },
        "deliver_after_seconds": 8,
    })

    # 5. Fraud Attempt / Scam Alert - Note: severity is unassigned so classifier evaluates objectively
    fixtures.append({
        "scenario": "fraud_phishing_report",
        "expect_status": 202,
        "payload": {
            "source_system": "zendesk_sim",
            "external_id": "TCK-SIM-20261109-005",
            "channel": "in_app",
            "occurred_at": (anchor - timedelta(minutes=45)).isoformat(),
            "text": "Someone called claiming to be from Bank support asking for my debit card OTP and PIN. I didn't give them but want my account protected.",
            "customer_ref": "crm-cust-9905",
            "payment_reference": None,
            "amount": None,
            "currency": None,
            "region": "Ibadan",
            "language": "en",
            "synthetic": True,
        },
        "deliver_after_seconds": 12,
    })

    # 6. Identical Replay of Ticket 001 - Expects 200 OK duplicate: true
    fixtures.append({
        "scenario": "identical_replay",
        "expect_status": 200,
        "payload": fixtures[0]["payload"],
        "deliver_after_seconds": 15,
    })

    # 7. Same external_id as Ticket 001 with differing text - Expects 409 Conflict
    conflict_payload = dict(fixtures[0]["payload"])
    conflict_payload["text"] = "MODIFIED TEXT: Customer changed statement, claims ₦40,000 was debited instead."
    conflict_payload["amount"] = "40000.00"
    fixtures.append({
        "scenario": "conflicting_replay_drift",
        "expect_status": 409,
        "payload": conflict_payload,
        "deliver_after_seconds": 18,
    })

    # 8. Late arrival ticket (Occurred 6 hours ago, delivered now)
    fixtures.append({
        "scenario": "late_arrival_ticket",
        "expect_status": 202,
        "payload": {
            "source_system": "zendesk_sim",
            "external_id": "TCK-SIM-20261109-008",
            "channel": "in_app",
            "occurred_at": (anchor - timedelta(hours=6)).isoformat(),
            "text": "Delayed logging: yesterday night transfer of ₦30,000.00 through USSD *901# timed out but customer was debited.",
            "customer_ref": "crm-cust-9908",
            "payment_reference": "USSD-20261109-8812",
            "amount": "30000.00",
            "currency": "NGN",
            "region": "Enugu",
            "language": "en",
            "synthetic": True,
        },
        "deliver_after_seconds": 22,
    })

    return fixtures


def save_bank_tickets(seed: int = 42) -> Path:
    DATA_OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    tickets = generate_bank_tickets(seed=seed)
    DATA_OUTPUT_PATH.write_text(json.dumps(tickets, indent=2), encoding="utf-8")
    return DATA_OUTPUT_PATH


if __name__ == "__main__":
    path = save_bank_tickets()
    print(f"Generated bank ticket fixtures saved to {path}")

