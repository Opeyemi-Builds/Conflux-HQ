import uuid

import pytest

from app.ai.agent.tools import ALLOWED_TOOL_NAMES
from app.main import app


EXPECTED_ENDPOINTS = {
    ("get", "/api/v1/fraud/cases"),
    ("get", "/api/v1/fraud/cases/{case_id}"),
    ("patch", "/api/v1/fraud/cases/{case_id}"),
    ("post", "/api/v1/ai/clusters/refresh"),
    ("get", "/api/v1/ai/clusters"),
    ("get", "/api/v1/ai/clusters/{cluster_id}"),
    ("get", "/api/v1/ai/reputation/summary"),
    ("post", "/api/v1/ai/incidents/{incident_id}/investigate"),
    ("get", "/api/v1/ai/incidents/{incident_id}/drafts"),
    ("get", "/api/v1/ai/incidents/{incident_id}/audit"),
    ("post", "/api/v1/complaints/{complaint_id}/classify"),
}


def test_ai_workstream_endpoints_are_registered_in_openapi():
    paths = app.openapi()["paths"]
    actual = {
        (method.lower(), path)
        for path, operations in paths.items()
        for method in operations
    }
    assert EXPECTED_ENDPOINTS <= actual


@pytest.mark.parametrize(
    ("method", "path", "payload"),
    [
        ("get", "/api/v1/fraud/cases", None),
        ("get", f"/api/v1/fraud/cases/{uuid.uuid4()}", None),
        ("patch", f"/api/v1/fraud/cases/{uuid.uuid4()}", {"status": "under_review"}),
        ("post", "/api/v1/ai/clusters/refresh", {}),
        ("get", "/api/v1/ai/clusters", None),
        ("get", f"/api/v1/ai/clusters/{uuid.uuid4()}", None),
        ("get", "/api/v1/ai/reputation/summary", None),
        ("post", f"/api/v1/ai/incidents/{uuid.uuid4()}/investigate", None),
        ("get", f"/api/v1/ai/incidents/{uuid.uuid4()}/drafts", None),
        ("get", f"/api/v1/ai/incidents/{uuid.uuid4()}/audit", None),
        ("post", f"/api/v1/complaints/{uuid.uuid4()}/classify", None),
    ],
)
def test_workstream_endpoints_require_authentication(client, method, path, payload):
    response = getattr(client, method)(path, json=payload) if payload is not None else getattr(client, method)(path)
    assert response.status_code == 401, response.text


def test_new_ai_routes_and_tools_cannot_move_money():
    forbidden = ("refund", "reverse", "execute", "block", "transfer")
    new_paths = [
        path
        for path in app.openapi()["paths"]
        if path.startswith("/api/v1/fraud/")
        or path.startswith("/api/v1/ai/clusters")
        or path.startswith("/api/v1/ai/reputation")
    ]
    assert new_paths
    assert all(not any(word in path.casefold() for word in forbidden) for path in new_paths)
    assert all(not any(word in name.casefold() for word in forbidden) for name in ALLOWED_TOOL_NAMES)
