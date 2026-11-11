#!/usr/bin/env python3
"""
Test utility to generate valid HMAC-SHA256 signed Forge webhook payloads.
"""

import hmac
import hashlib
import json
import time
import requests
import os

WEBHOOK_URL = os.getenv("CONFLUX_WEBHOOK_URL", "http://127.0.0.1:8000/api/v1/forge/webhooks")
WEBHOOK_SECRET = os.getenv("CONFLUX_WEBHOOK_SECRET", "test_forge_secret_key_123")

def send_signed_webhook():
    payload = {
        "event_id": f"evt_{int(time.time()*1000)}",
        "provider": "nibss_switch",
        "timestamp": int(time.time()),
        "data": {
            "channel": "ussd",
            "issue_type": "failed_transfer",
            "customer_text": "I was debited 45,000 for transfer to GTBank and recipient did not receive it since yesterday",
            "account_mask": "0123****89",
            "amount": 45000,
            "region": "Lagos",
        }
    }

    raw_body = json.dumps(payload, separators=(',', ':')).encode("utf-8")
    now_ts = str(int(time.time()))
    signed_payload = f"{now_ts}.".encode("utf-8") + raw_body
    signature = hmac.new(WEBHOOK_SECRET.encode("utf-8"), signed_payload, hashlib.sha256).hexdigest()

    headers = {
        "Content-Type": "application/json",
        "x-forge-event": "complaint.ingested",
        "x-forge-timestamp": now_ts,
        "x-forge-signature": signature,
    }

    print(f"[*] Dispatching signed webhook to {WEBHOOK_URL}...")
    res = requests.post(WEBHOOK_URL, data=raw_body, headers=headers)
    print(f"[+] Status: {res.status_code}")
    print(f"[+] Body: {res.text}")

if __name__ == "__main__":
    send_signed_webhook()
