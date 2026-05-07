"""Tests for safe_log() and Sentry pii_scrubber()."""

import json
import logging

import pytest

from backend.utils.safe_logging import (
    PII_FIELD_NAMES,
    REDACTED,
    pii_scrubber,
    safe_log,
)


# ─── safe_log() ───────────────────────────────────────────────


def test_safe_log_emits_clean_fields(caplog, monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "production")  # avoid raising in dev
    logger = logging.getLogger("test.safe_log.clean")
    with caplog.at_level(logging.INFO, logger="test.safe_log.clean"):
        safe_log(logger, "info", "webhook.received", request_id="r1", body_length=42)

    assert len(caplog.records) == 1
    payload = json.loads(caplog.records[0].message)
    assert payload == {"event": "webhook.received", "request_id": "r1", "body_length": 42}


def test_safe_log_raises_in_dev_when_pii_passed(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "development")
    logger = logging.getLogger("test.safe_log.dev")
    with pytest.raises(ValueError) as exc_info:
        safe_log(logger, "info", "test.event", child_name="Annie")
    assert "child_name" in str(exc_info.value)


def test_safe_log_drops_pii_in_production(caplog, monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "production")
    logger = logging.getLogger("test.safe_log.prod")
    with caplog.at_level(logging.INFO, logger="test.safe_log.prod"):
        safe_log(
            logger,
            "info",
            "test.event",
            child_name="Annie",
            transcript="Annie ate lunch",
            request_id="r1",
        )

    assert len(caplog.records) == 1
    payload = json.loads(caplog.records[0].message)
    assert "child_name" not in payload
    assert "transcript" not in payload
    assert payload["request_id"] == "r1"
    assert set(payload["_dropped_pii_fields"]) == {"child_name", "transcript"}
    assert "Annie" not in caplog.records[0].message


def test_pii_field_names_covers_required_fields():
    required = {"child_name", "transcript", "raw_transcript", "body", "caption", "name"}
    assert required.issubset(PII_FIELD_NAMES)


# ─── pii_scrubber() — Sentry before_send ─────────────────────


def test_scrubber_redacts_extra_fields():
    event = {
        "extra": {
            "transcript": "Annie ate lunch",
            "child_name": "Annie",
            "request_id": "r1",
        }
    }
    out = pii_scrubber(event)
    assert out["extra"]["transcript"] == REDACTED
    assert out["extra"]["child_name"] == REDACTED
    assert out["extra"]["request_id"] == "r1"


def test_scrubber_redacts_request_data():
    event = {
        "request": {
            "data": {"body": "Annie ate lunch", "request_id": "r1"},
            "headers": {"phone": "+15551234567", "user-agent": "test"},
        }
    }
    out = pii_scrubber(event)
    assert out["request"]["data"]["body"] == REDACTED
    assert out["request"]["data"]["request_id"] == "r1"
    assert out["request"]["headers"]["phone"] == REDACTED
    assert out["request"]["headers"]["user-agent"] == "test"


def test_scrubber_redacts_stack_frame_vars():
    event = {
        "exception": {
            "values": [
                {
                    "stacktrace": {
                        "frames": [
                            {
                                "function": "extract_events",
                                "vars": {
                                    "transcript": "Annie ate lunch and napped",
                                    "child_name": "Annie",
                                    "center_id": "center-uuid",
                                },
                            }
                        ]
                    }
                }
            ]
        }
    }
    out = pii_scrubber(event)
    frame_vars = out["exception"]["values"][0]["stacktrace"]["frames"][0]["vars"]
    assert frame_vars["transcript"] == REDACTED
    assert frame_vars["child_name"] == REDACTED
    assert frame_vars["center_id"] == "center-uuid"


def test_scrubber_full_event_no_pii_leaks():
    """Acceptance test from pilot checklist §0.3."""
    event = {
        "extra": {"transcript": "Annie ate her lunch and took a nap"},
        "request": {"data": {"body": "Annie ate her lunch"}},
        "exception": {
            "values": [
                {
                    "stacktrace": {
                        "frames": [
                            {
                                "vars": {
                                    "raw_transcript": "Annie ate her lunch",
                                    "child_name": "Annie",
                                }
                            }
                        ]
                    }
                }
            ]
        },
    }
    out = pii_scrubber(event)
    serialized = json.dumps(out)
    assert "Annie" not in serialized
    assert REDACTED in serialized


def test_scrubber_handles_missing_optional_keys():
    """The scrubber must never crash on partial events."""
    assert pii_scrubber({}) == {}
    assert pii_scrubber({"extra": None}) == {"extra": None}
    assert pii_scrubber({"exception": {"values": []}}) == {"exception": {"values": []}}
    assert pii_scrubber({"exception": {"values": [{}]}}) == {"exception": {"values": [{}]}}
