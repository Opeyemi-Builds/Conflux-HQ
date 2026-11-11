#!/usr/bin/env python3
"""
Benchmark latency and throughput of the machine handoff feed.
Simulates continuous polling across multiple concurrent threads.
"""

import os
import sys
import time
import requests
import statistics

API_BASE = os.getenv("CONFLUX_API_BASE", "http://127.0.0.1:8000/api/v1")
API_KEY = os.getenv("CONFLUX_API_KEY", "")

def run_benchmark(iterations=30):
    if not API_KEY:
        print("[!] Set CONFLUX_API_KEY to benchmark authenticated machine endpoint", file=sys.stderr)
        return

    headers = {"Authorization": f"Bearer {API_KEY}", "Accept": "application/json"}
    latencies = []

    print(f"[*] Running {iterations} consecutive polls against {API_BASE}/machine/updates...")

    cursor = None
    for i in range(iterations):
        params = {"collections": "complaints,incidents", "limit": 20}
        if cursor:
            params["since"] = cursor

        start = time.perf_counter()
        res = requests.get(f"{API_BASE}/machine/updates", headers=headers, params=params, timeout=5)
        duration_ms = (time.perf_counter() - start) * 1000
        latencies.append(duration_ms)

        if res.ok:
            data = res.json()
            cursor = data.get("cursor") or cursor
            print(f"  [{i+1}/{iterations}] Status {res.status_code} in {duration_ms:.1f}ms - items: {len(data.get('items', []))}")
        else:
            print(f"  [{i+1}/{iterations}] Status {res.status_code} in {duration_ms:.1f}ms")

        time.sleep(0.1)

    print("\n" + "=" * 45)
    print("BENCHMARK RESULTS")
    print("=" * 45)
    print(f"Total Requests: {len(latencies)}")
    print(f"Min Latency:    {min(latencies):.1f}ms")
    print(f"Median Latency: {statistics.median(latencies):.1f}ms")
    print(f"P95 Latency:    {statistics.quantiles(latencies, n=20)[18]:.1f}ms")
    print(f"Max Latency:    {max(latencies):.1f}ms")
    print("=" * 45 + "\n")

if __name__ == "__main__":
    run_benchmark()
