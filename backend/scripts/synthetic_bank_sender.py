"""CLI tool simulating a bank customer support CRM system sending tickets into Conflux."""
import argparse
import json
import os
import sys
import time
from pathlib import Path

import httpx


def run_sender(
    base_url: str,
    token: str,
    fixtures_path: Path,
    compress: float = 1.0,
    bank_b_token: str | None = None,
):
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    client = httpx.Client(base_url=base_url.rstrip("/"), timeout=15.0)

    if not fixtures_path.exists():
        print(f"Error: Fixtures file not found at {fixtures_path}")
        sys.exit(1)

    fixtures = json.loads(fixtures_path.read_text(encoding="utf-8"))
    print(f"Loaded {len(fixtures)} synthetic ticket scenarios from {fixtures_path.name}")
    print(f"Target Base URL: {base_url}")
    print("-" * 80)
    print(f"{'SCENARIO':<32} | {'EXTERNAL_ID':<22} | {'EXPECT':<6} | {'ACTUAL':<6} | {'STATUS'}")
    print("-" * 80)

    success_count = 0
    start_time = time.time()

    for item in fixtures:
        scenario = item.get("scenario", "unknown")
        expected_status = item.get("expect_status", 202)
        payload = item["payload"]
        ext_id = payload.get("external_id", "-")

        delay = item.get("deliver_after_seconds", 0) / compress
        if delay > 0:
            time.sleep(delay)

        try:
            resp = client.post("/ingestion/complaints", json=payload, headers=headers)
            actual_status = resp.status_code
            passed = (actual_status == expected_status)

            if passed:
                success_count += 1
                status_str = "PASS [OK]"
            else:
                status_str = f"FAIL (got {actual_status}, expected {expected_status})"

            print(f"{scenario:<32} | {ext_id:<22} | {expected_status:<6} | {actual_status:<6} | {status_str}")

        except Exception as exc:
            print(f"{scenario:<32} | {ext_id:<22} | {expected_status:<6} | {'ERR':<6} | EXCEPTION: {exc}")

    # Optional cross-bank rejection check
    if bank_b_token:
        print("\n--- Running Cross-Bank Isolation Check ---")
        bank_b_headers = {"Authorization": f"Bearer {bank_b_token}", "Content-Type": "application/json"}
        # Bank B sending identical external_id must create an independent receipt (not conflict)
        b_payload = dict(fixtures[0]["payload"])
        resp = client.post("/ingestion/complaints", json=b_payload, headers=bank_b_headers)
        if resp.status_code == 202:
            print("Cross-Bank Delivery: PASS [OK] (Bank B successfully ingested its own independent ticket)")
            success_count += 1
        else:
            print(f"Cross-Bank Delivery: FAIL (got {resp.status_code})")

    elapsed = time.time() - start_time
    print("-" * 80)
    print(f"Completed in {elapsed:.2f}s: {success_count} scenarios verified.")


def main():
    parser = argparse.ArgumentParser(description="Synthetic Bank Ticket Sender for Conflux HQ")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000/api/v1", help="Conflux API base URL")
    parser.add_argument("--token-env", default="CFX_CONNECTOR_TOKEN", help="Environment variable containing connector token")
    parser.add_argument("--bank-b-token-env", default=None, help="Environment variable for Bank B connector token")
    parser.add_argument("--fixtures", default=None, help="Path to bank tickets JSON fixtures")
    parser.add_argument("--compress", type=float, default=10.0, help="Compression factor for delay schedule (default 10x)")

    args = parser.parse_args()

    token = os.environ.get(args.token_env)
    if not token:
        print(f"Error: Connector token not found in env var '{args.token_env}'.")
        print("Provision a connector via POST /api/v1/ingestion/connectors or set CFX_CONNECTOR_TOKEN.")
        sys.exit(1)

    bank_b_token = os.environ.get(args.bank_b_token_env) if args.bank_b_token_env else None

    fixtures_path = Path(args.fixtures) if args.fixtures else (
        Path(__file__).resolve().parents[2] / "data" / "synthetic" / "bank_tickets.json"
    )

    run_sender(
        base_url=args.base_url,
        token=token,
        fixtures_path=fixtures_path,
        compress=args.compress,
        bank_b_token=bank_b_token,
    )


if __name__ == "__main__":
    main()

