#!/usr/bin/env python3
"""
CLI helper to generate scoped cfx_api_ machine keys for bank admins.
Usage:
  python generate_machine_key.py --name "NOC Poller" --scopes read operate --expires 90
"""

import argparse
import os
import requests

API_BASE = os.getenv("CONFLUX_API_BASE", "http://127.0.0.1:8000/api/v1")
ADMIN_TOKEN = os.getenv("CONFLUX_ADMIN_TOKEN", "")

def main():
    parser = argparse.ArgumentParser(description="Generate ConfluxHQ machine API key")
    parser.add_argument("--name", required=True, help="Descriptive name for the key")
    parser.add_argument("--scopes", nargs="+", default=["read", "operate"], choices=["read", "operate"])
    parser.add_argument("--expires-days", type=int, default=90, help="Days until key expires (0 for never)")
    args = parser.parse_args()

    token = ADMIN_TOKEN
    if not token:
        # Prompt or try demo login
        print("[*] No CONFLUX_ADMIN_TOKEN provided, attempting demo login...")
        login_res = requests.post(f"{API_BASE}/auth/login", json={"username": "Zymic Bank", "password": "123"})
        if not login_res.ok:
            print(f"[!] Login failed: {login_res.text}")
            return
        token = login_res.json()["access_token"]

    payload = {
        "name": args.name,
        "scopes": args.scopes,
    }

    res = requests.post(
        f"{API_BASE}/api-keys",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json=payload,
    )

    if not res.ok:
        print(f"[!] Key generation failed ({res.status_code}): {res.text}")
        return

    data = res.json()
    print("\n" + "=" * 60)
    print("SUCCESS: Machine API Key Generated")
    print("=" * 60)
    print(f"Name:       {data['name']}")
    print(f"Prefix:     {data['key_prefix']}")
    print(f"Scopes:     {', '.join(data['scopes'])}")
    print(f"Token:      {data['token']}")
    print("=" * 60)
    print("WARNING: Save this token now! It will never be displayed again.")
    print("=" * 60 + "\n")

if __name__ == "__main__":
    main()
