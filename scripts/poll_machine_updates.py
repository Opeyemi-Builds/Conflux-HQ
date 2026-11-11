#!/usr/bin/env python3
"""
ConfluxHQ Machine Feed Poller Reference Client
Streams real-time complaints and incidents every 5 seconds.
"""

import os
import sys
import time
import requests

API_BASE = os.getenv("CONFLUX_API_BASE", "http://127.0.0.1:8000/api/v1")
API_KEY = os.getenv("CONFLUX_API_KEY", "")

def poll_feed():
    if not API_KEY or not API_KEY.startswith("cfx_api_"):
        print("Error: Please set CONFLUX_API_KEY=cfx_api_...", file=sys.stderr)
        sys.exit(1)

    cursor = None
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Accept": "application/json",
        "User-Agent": "ConfluxHQ-MachinePoller/1.0",
    }

    print(f"[*] Starting ConfluxHQ Machine Feed Poller against {API_BASE}")
    print("[*] Polling interval: 5 seconds. Press Ctrl+C to stop.\n")

    while True:
        params = {
            "collections": "complaints,incidents",
            "limit": 20,
        }
        if cursor:
            params["since"] = cursor

        try:
            res = requests.get(f"{API_BASE}/machine/updates", headers=headers, params=params, timeout=10)
            if res.status_code == 401:
                print("[!] 401 Unauthorized: API key invalid or revoked.", file=sys.stderr)
                time.sleep(10)
                continue

            res.raise_for_status()
            data = res.json()

            items = data.get("items", [])
            cursor = data.get("cursor") or cursor
            truncated = data.get("truncated", False)

            if items:
                print(f"[+] Received {len(items)} updates (cursor: {cursor}):")
                for item in items:
                    col = item.get("collection")
                    d = item.get("data", {})
                    if col == "incidents":
                        print(f"    [INCIDENT] #{item.get('id')[:8]} - {d.get('title')} (Priority: {d.get('priority')})")
                    else:
                        print(f"    [COMPLAINT] [{d.get('channel')}] {d.get('summary') or d.get('text', '')[:60]}...")
            else:
                print(f"[-] No new events (cursor: {cursor})")

            # If truncated, poll immediately without waiting 5 seconds
            if not truncated:
                time.sleep(5)

        except requests.exceptions.RequestException as e:
            print(f"[!] Polling error: {e}", file=sys.stderr)
            time.sleep(5)

if __name__ == "__main__":
    try:
        poll_feed()
    except KeyboardInterrupt:
        print("\n[*] Poller stopped.")
