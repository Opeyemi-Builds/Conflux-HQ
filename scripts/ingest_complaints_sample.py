#!/usr/bin/env python3
"""
Sample script demonstrating multi-channel complaint intake via POST /api/v1/complaints.
"""

import os
import requests

API_BASE = os.getenv("CONFLUX_API_BASE", "http://127.0.0.1:8000/api/v1")
AUTH_TOKEN = os.getenv("CONFLUX_TOKEN", "")

SAMPLE_COMPLAINTS = [
    {
        "channel": "x",
        "text": "@ZymicBank I was debited 12,000 for POS transaction at Ikeja City Mall but merchant claimed decline! Kindly reverse!",
        "customer_id": "cust_ng_001",
        "region": "Lagos",
    },
    {
        "channel": "in_app",
        "text": "Transfer failed but my account was debited 50,000 NGN. Session ID: 0000132411110255410001.",
        "customer_id": "cust_ng_002",
        "region": "Abuja",
    },
    {
        "channel": "call",
        "text": "Customer reported fraudulent transfer of 250,000 after SIM swap alert on MTN line.",
        "customer_id": "cust_ng_003",
        "region": "Rivers",
    }
]

def ingest_samples():
    headers = {"Content-Type": "application/json"}
    if AUTH_TOKEN:
        headers["Authorization"] = f"Bearer {AUTH_TOKEN}"

    for comp in SAMPLE_COMPLAINTS:
        res = requests.post(f"{API_BASE}/complaints", json=comp, headers=headers)
        print(f"[{comp['channel'].upper()}] Status {res.status_code}: {res.text[:80]}")

if __name__ == "__main__":
    ingest_samples()
