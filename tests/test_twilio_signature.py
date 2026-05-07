"""Tests for Twilio webhook signature verification (pilot §1.3)."""

from urllib.parse import urlencode

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from twilio.request_validator import RequestValidator

from backend.config import get_settings
from backend.utils.twilio_security import _twilio_request_url, verify_twilio_signature


# ─── URL rewriting (HTTPS behind a proxy) ─────────────────────


class _FakeRequest:
    def __init__(self, url: str, headers: dict):
        self.url = url
        self.headers = {k.lower(): v for k, v in headers.items()}


def test_url_rewrite_promotes_http_to_https_when_forwarded_proto_is_https():
    req = _FakeRequest("http://app.test/webhook/whatsapp", {"x-forwarded-proto": "https"})
    assert _twilio_request_url(req) == "https://app.test/webhook/whatsapp"


def test_url_rewrite_keeps_http_when_no_proxy_header():
    req = _FakeRequest("http://app.test/webhook/whatsapp", {})
    assert _twilio_request_url(req) == "http://app.test/webhook/whatsapp"


def test_url_rewrite_does_not_double_promote_https():
    req = _FakeRequest("https://app.test/webhook/whatsapp", {"x-forwarded-proto": "https"})
    assert _twilio_request_url(req) == "https://app.test/webhook/whatsapp"


# ─── Dependency: dev/test bypass ──────────────────────────────


def _make_app() -> FastAPI:
    app = FastAPI()

    @app.post("/wh", dependencies=[__import__("fastapi").Depends(verify_twilio_signature)])
    async def handler():
        return {"ok": True}

    return app


def test_bypass_when_environment_is_development(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "development")
    get_settings.cache_clear()

    client = TestClient(_make_app())
    resp = client.post("/wh", data={"foo": "bar"})  # no signature header
    assert resp.status_code == 200
    assert resp.json() == {"ok": True}


def test_bypass_when_environment_is_test(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "test")
    get_settings.cache_clear()

    client = TestClient(_make_app())
    resp = client.post("/wh", data={"foo": "bar"})
    assert resp.status_code == 200


# ─── Dependency: production rejection ─────────────────────────


def test_production_rejects_missing_signature(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("TWILIO_AUTH_TOKEN", "fake-token")
    get_settings.cache_clear()

    client = TestClient(_make_app())
    resp = client.post("/wh", data={"foo": "bar"})
    assert resp.status_code == 403
    assert "Missing" in resp.json()["detail"]


def test_production_rejects_invalid_signature(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("TWILIO_AUTH_TOKEN", "fake-token")
    get_settings.cache_clear()

    client = TestClient(_make_app())
    resp = client.post(
        "/wh",
        data={"foo": "bar"},
        headers={"X-Twilio-Signature": "definitely-not-a-real-signature"},
    )
    assert resp.status_code == 403
    assert "Invalid" in resp.json()["detail"]


def test_production_500_when_auth_token_missing(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("TWILIO_AUTH_TOKEN", "")
    get_settings.cache_clear()

    client = TestClient(_make_app())
    resp = client.post(
        "/wh",
        data={"foo": "bar"},
        headers={"X-Twilio-Signature": "anything"},
    )
    assert resp.status_code == 500


def test_production_accepts_valid_signature(monkeypatch):
    """A real RequestValidator-signed request must pass through to the handler."""
    auth_token = "fake-token-for-test"
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("TWILIO_AUTH_TOKEN", auth_token)
    get_settings.cache_clear()

    client = TestClient(_make_app())

    params = {"foo": "bar", "MessageSid": "SM1"}
    # TestClient defaults base_url to "http://testserver". Production is HTTPS,
    # so simulate the proxy by sending X-Forwarded-Proto: https and matching it
    # in the signature.
    signed_url = "https://testserver/wh"
    validator = RequestValidator(auth_token)
    signature = validator.compute_signature(signed_url, params)

    resp = client.post(
        "/wh",
        data=params,
        headers={
            "X-Twilio-Signature": signature,
            "X-Forwarded-Proto": "https",
        },
    )
    assert resp.status_code == 200, resp.text


@pytest.fixture(autouse=True)
def _reset_settings_cache():
    """Make sure each test starts with a clean Settings cache."""
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()
