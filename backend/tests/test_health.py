"""Tests for the health/readiness endpoints (Phase 1 acceptance criterion)."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_health_returns_ok(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["app"]
    assert body["env"] in {"local", "prod"}


def test_ready_returns_ok(client: TestClient) -> None:
    response = client.get("/ready")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["checks"]["config"] == "ok"


def test_health_response_has_no_secret_fields(client: TestClient) -> None:
    # Defensive: the health payload must not leak configuration secrets.
    body = client.get("/health").json()
    for key in body:
        assert "token" not in key.lower()
        assert "secret" not in key.lower()
        assert "key" not in key.lower()
