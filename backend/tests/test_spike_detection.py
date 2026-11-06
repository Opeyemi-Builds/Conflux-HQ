from datetime import datetime, timedelta, timezone

from app.services.spike_detection import bucket_start, evaluate_spike, priority_score

NOW = datetime(2026, 11, 6, 10, 30, tzinfo=timezone.utc)  # start of the current 15-min bucket
DETECT_AT = NOW + timedelta(minutes=10)


def test_quiet_history_big_jump_is_spike():
    assert evaluate_spike([2, 3, 2, 4, 3, 2, 3], 25).is_spike


def test_small_count_is_not_spike_even_above_baseline():
    assert not evaluate_spike([0] * 96, 5).is_spike


def test_normal_noise_is_not_spike():
    assert not evaluate_spike([10, 12, 9, 11, 10, 13, 12], 14).is_spike


def test_bucket_start_floors_to_15_minutes():
    assert bucket_start(datetime(2026, 11, 6, 10, 44, 59, tzinfo=timezone.utc), 15).minute == 30


def test_priority_score_bounds():
    assert 0 <= priority_score(5, 1.0) <= 100
    assert priority_score(500, 100.0) == 100


def _complaints(n, minutes_ago, issue="failed_transfer"):
    return [
        {
            "channel": "x" if i % 2 else "in_app",
            "text": "my money don enter nowhere",
            "issue_type": issue,
            "occurred_at": (NOW - timedelta(minutes=minutes_ago, seconds=i)).isoformat(),
        }
        for i in range(n)
    ]


def test_detect_creates_incident_for_planted_spike(authed):
    baseline = [c for m in (200, 180, 160, 140, 120) for c in _complaints(1, m)]
    spike = _complaints(25, -5)  # 10:35, inside the current bucket
    authed.post("/api/v1/complaints/bulk", json={"complaints": baseline + spike})

    res = authed.post("/api/v1/incidents/detect", json={"now": DETECT_AT.isoformat()})
    assert res.status_code == 200
    incidents = res.json()
    assert len(incidents) == 1
    assert incidents[0]["issue_type"] == "failed_transfer"
    assert incidents[0]["complaint_count"] == 25
    assert set(incidents[0]["affected_channels"]) == {"x", "in_app"}

    # Running detection again must not duplicate the open incident
    again = authed.post("/api/v1/incidents/detect", json={"now": DETECT_AT.isoformat()}).json()
    assert again == []
    assert len(authed.get("/api/v1/incidents").json()) == 1


def test_isolated_incident_does_not_trigger(authed):
    authed.post("/api/v1/complaints/bulk", json={"complaints": _complaints(4, -5, issue="fees")})
    res = authed.post("/api/v1/incidents/detect", json={"now": DETECT_AT.isoformat()})
    assert res.json() == []
