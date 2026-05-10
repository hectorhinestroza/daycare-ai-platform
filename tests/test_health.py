"""Tests for the /health endpoint (pilot §4.2)."""

from fastapi.testclient import TestClient

from backend.config import get_settings
from backend.main import app


def test_health_returns_200_and_required_fields():
    client = TestClient(app)
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    for key in ("status", "git_sha", "uptime_seconds", "extraction_disabled", "legal"):
        assert key in body, f"missing field: {key}"
    assert body["status"] == "ok"
    assert isinstance(body["uptime_seconds"], int)
    assert body["uptime_seconds"] >= 0


def test_health_reports_git_sha_from_env(monkeypatch):
    monkeypatch.setenv("RAILWAY_GIT_COMMIT_SHA", "abc1234def")
    client = TestClient(app)
    r = client.get("/health")
    assert r.json()["git_sha"] == "abc1234def"


def test_health_reports_git_sha_unknown_when_unset(monkeypatch):
    monkeypatch.delenv("RAILWAY_GIT_COMMIT_SHA", raising=False)
    monkeypatch.delenv("GIT_COMMIT_SHA", raising=False)
    monkeypatch.delenv("GIT_SHA", raising=False)
    client = TestClient(app)
    r = client.get("/health")
    assert r.json()["git_sha"] == "unknown"


def test_health_surfaces_kill_switch(monkeypatch):
    monkeypatch.setenv("EXTRACTION_DISABLED", "true")
    get_settings.cache_clear()
    try:
        client = TestClient(app)
        r = client.get("/health")
        assert r.json()["extraction_disabled"] is True
    finally:
        get_settings.cache_clear()
