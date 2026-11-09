"""Run the synthetic AI workflow against a live local Conflux HQ server."""
import json
import os
import sys
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


BASE_URL = os.getenv("BASE_URL", "http://localhost:8000/api/v1").rstrip("/")
USERNAME = os.getenv("DEMO_USERNAME", "Zymic Bank")
PASSWORD = os.getenv("DEMO_PASSWORD", "123")
checks: list[tuple[str, bool, str]] = []


def request(method: str, path: str, token: str | None = None, payload: dict | None = None):
    headers = {"Accept": "application/json"}
    body = None
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = Request(f"{BASE_URL}{path}", data=body, headers=headers, method=method)
    with urlopen(req, timeout=90) as response:
        raw = response.read()
        return response.status, json.loads(raw) if raw else None


def check(name: str, condition: bool, detail: str = "") -> None:
    checks.append((name, condition, detail))
    print(f"{'PASS' if condition else 'FAIL'} {name}{': ' + detail if detail else ''}")


def main() -> int:
    try:
        _, login = request("POST", "/auth/login", payload={"username": USERNAME, "password": PASSWORD})
        token = login["access_token"]
        check("POST /auth/login", True)

        _, seed = request("POST", "/synthetic/seed", token, {"seed": 42})
        check("POST /synthetic/seed", seed.get("complaints_created") == 1000)

        for loop_index in range(20):
            _, drained = request("POST", "/jobs/drain", token, {"limit": 1000})
            if drained.get("processed", 0) == 0:
                break
        check("POST /jobs/drain", drained.get("processed", 0) == 0, f"loops={loop_index + 1}")

        all_complaints = []
        for offset in range(0, 1000, 500):
            _, page = request("GET", f"/complaints?limit=500&offset={offset}", token)
            all_complaints.extend(page)
        complaint_by_id = {item["id"]: item for item in all_complaints}
        for complaint in all_complaints:
            if "payment_category" not in complaint or complaint.get("classification_confidence") is None:
                _, updated = request("POST", f"/complaints/{complaint['id']}/classify", token)
                complaint_by_id[complaint["id"]] = updated
        classified = list(complaint_by_id.values())
        complete = sum(
            (
                bool(item.get("payment_category"))
                or item.get("issue_type") in {"app_login", "loan", "other"}
            )
            and item.get("classification_confidence") is not None
            for item in classified
        )
        check("GET /complaints classification metadata", complete >= 900, f"{complete}/1000 enriched")

        _, fraud = request("GET", "/fraud/cases?limit=500", token)
        fraud_cases = fraud.get("items", [])
        fraud_queue_ok = bool(fraud_cases) and all(
            complaint_by_id.get(case["complaint_id"], {}).get("routing_queue") == "fraud_security"
            for case in fraud_cases
        )
        check("GET /fraud/cases", fraud_queue_ok, f"cases={len(fraud_cases)}")

        detection_at = seed["detection_at"]
        from datetime import datetime, timedelta

        detection_time = datetime.fromisoformat(detection_at.replace("Z", "+00:00"))
        window = {
            "since": (detection_time - timedelta(minutes=15)).isoformat(),
            "until": detection_time.isoformat(),
        }
        _, refreshed = request("POST", "/ai/clusters/refresh", token, window)
        _, clusters = request("GET", "/ai/clusters?min_count=2&limit=500", token)
        failed_clusters = [
            item for item in clusters["items"]
            if item.get("issue_type") == "failed_transfer"
            and item.get("complaint_count", 0) >= 10
        ]
        check(
            "POST /ai/clusters/refresh + GET /ai/clusters",
            bool(failed_clusters) and refreshed.get("cluster_count", 0) > 0,
            f"failed_transfer_clusters={len(failed_clusters)}",
        )

        _, detected = request(
            "POST",
            "/incidents/detect",
            token,
            {"now": seed["detection_at"]},
        )
        _, incidents = request("GET", "/incidents?limit=200", token)
        release_incidents = [
            item for item in incidents
            if item.get("issue_type") == "failed_transfer"
        ]
        release_incident = next(
            (
                incident for incident in release_incidents
                if any(cluster.get("related_incident_id") == incident["id"] for cluster in clusters["items"])
            ),
            release_incidents[0] if release_incidents else None,
        )
        check("POST /incidents/detect", bool(detected) or bool(release_incidents))
        investigation_ok = False
        if release_incident:
            _, investigation = request(
                "POST", f"/ai/incidents/{release_incident['id']}/investigate", token
            )
            cause = investigation.get("likely_cause") or ""
            supported = investigation.get("supporting_evidence", [])
            contradicted = investigation.get("contradicting_evidence", [])
            investigation_ok = (
                "v4.2.1" in cause
                and "email-service" not in cause
                and bool(supported)
                and bool(contradicted)
                and any(
                    "unrelated" in str(item.get("detail", "")).casefold()
                    for item in contradicted
                )
            )
        check("POST /ai/incidents/{id}/investigate", investigation_ok)

        _, reputation = request("GET", "/ai/reputation/summary", token)
        check(
            "GET /ai/reputation/summary",
            0 <= reputation["reputation_signal_index"] <= 100,
        )

        unauthenticated = [
            ("GET", "/fraud/cases", None),
            ("GET", "/ai/clusters", None),
            ("GET", "/ai/reputation/summary", None),
            ("POST", "/ai/clusters/refresh", {}),
        ]
        unauth_ok = True
        for method, path, payload in unauthenticated:
            try:
                request(method, path, payload=payload)
                unauth_ok = False
            except HTTPError as exc:
                unauth_ok = unauth_ok and exc.code == 401
        check("Authentication on new endpoints", unauth_ok)
    except (HTTPError, URLError, KeyError, ValueError, TimeoutError) as exc:
        check("Smoke workflow", False, str(exc))

    failed = [name for name, passed, _ in checks if not passed]
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
