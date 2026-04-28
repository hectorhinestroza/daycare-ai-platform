"""Tests forLegal status observability (passive /health fields).

Verifies:
- get_legal_status_fields() returns True when env vars set to "confirmed"
- Returns False when env vars are missing or wrong value
- Returns dict with correct keys
- Application starts regardless of env var state (no startup blocker)
"""
import os
from unittest.mock import patch

from backend.startup.legal_checks import get_legal_status_fields


class TestGetLegalStatusFields:
    """get_legal_status_fields() returns passive boolean status dict."""

    def test_all_true_when_all_confirmed(self):
        """All three fields True when env vars set to 'confirmed'."""

        env = {
            "DPA_OPENAI_CONFIRMED": "confirmed",
            "DPA_TWILIO_CONFIRMED": "confirmed",
            "OPENAI_ZERO_RETENTION_CONFIRMED": "confirmed",
        }
        with patch.dict(os.environ, env, clear=False):
            status = get_legal_status_fields()

        assert status["openai_dpa_confirmed"] is True
        assert status["twilio_dpa_confirmed"] is True
        assert status["openai_zero_retention_confirmed"] is True

    def test_false_when_openai_dpa_missing(self):
        """openai_dpa_confirmed is False when DPA_OPENAI_CONFIRMED not set."""

        env = {
            "DPA_TWILIO_CONFIRMED": "confirmed",
            "OPENAI_ZERO_RETENTION_CONFIRMED": "confirmed",
        }
        with patch.dict(os.environ, env, clear=False):
            # Remove the key if present
            os.environ.pop("DPA_OPENAI_CONFIRMED", None)
            status = get_legal_status_fields()

        assert status["openai_dpa_confirmed"] is False

    def test_false_when_value_not_confirmed(self):
        """False if env var is set but not exactly 'confirmed' (e.g. 'yes', 'true')."""

        for wrong_value in ["yes", "true", "1", "TRUE", "Confirmed", ""]:
            env = {"DPA_OPENAI_CONFIRMED": wrong_value}
            with patch.dict(os.environ, env, clear=False):
                status = get_legal_status_fields()
            assert status["openai_dpa_confirmed"] is False, \
                f"Expected False for value={wrong_value!r}"

    def test_returns_all_required_keys(self):
        """Dict must have exactly the three documented keys."""

        status = get_legal_status_fields()
        required_keys = {
            "openai_dpa_confirmed",
            "twilio_dpa_confirmed",
            "openai_zero_retention_confirmed",
        }
        assert required_keys == set(status.keys())

    def test_all_false_when_no_vars_set(self):
        """All False when no env vars are set — reminder not a blocker."""

        # Remove all three vars
        clean_env = {k: v for k, v in os.environ.items()
                     if k not in {
                         "DPA_OPENAI_CONFIRMED",
                         "DPA_TWILIO_CONFIRMED",
                         "OPENAI_ZERO_RETENTION_CONFIRMED",
                     }}
        with patch.dict(os.environ, clean_env, clear=True):
            status = get_legal_status_fields()

        assert all(v is False for v in status.values()), \
            "All values should be False when env vars absent"

    def test_no_exception_raised_when_vars_missing(self):
        """Missing env vars must NEVER raise — this is observability, not enforcement."""

        clean_env = {}
        with patch.dict(os.environ, clean_env, clear=True):
            # Should complete without exception
            status = get_legal_status_fields()
        assert isinstance(status, dict)
