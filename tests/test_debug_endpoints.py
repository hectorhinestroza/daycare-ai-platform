"""Tests for the temporary Sentry debug endpoints."""

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

import backend.storage.models  # noqa: F401
from backend.config import get_settings
from backend.main import app
from backend.utils.auth_tokens import generate_token

SECRET = "test-secret-do-not-use-in-prod-32-bytes-long-pls"


@pytest.fixture(autouse=True)
def _set_production_env(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("AUTH_TOKEN_SECRET", SECRET)
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _director_token():
    token, _ = generate_token(
        role="director", sub=uuid4(), center_id=uuid4(), secret=SECRET
    )
    return token


def _teacher_token():
    token, _ = generate_token(
        role="teacher", sub=uuid4(), center_id=uuid4(), secret=SECRET
    )
    return token


def test_sentry_test_requires_director():
    client = TestClient(app, raise_server_exceptions=False)
    headers = {"Authorization": f"Bearer {_teacher_token()}"}
    resp = client.get("/api/debug/sentry-test", headers=headers)
    assert resp.status_code == 403


def test_sentry_test_raises_for_director():
    """As a director, the endpoint raises a RuntimeError that bubbles to a 500.
    Sentry's FastAPI integration would capture it in production."""
    client = TestClient(app, raise_server_exceptions=False)
    headers = {"Authorization": f"Bearer {_director_token()}"}
    resp = client.get("/api/debug/sentry-test", headers=headers)
    assert resp.status_code == 500


def test_sentry_pii_test_raises_for_director():
    client = TestClient(app, raise_server_exceptions=False)
    headers = {"Authorization": f"Bearer {_director_token()}"}
    resp = client.get("/api/debug/sentry-pii-test", headers=headers)
    assert resp.status_code == 500
