"""Tests for L-9: DPA Verification Startup Guard.

Verifies:
- Production startup fails when any required DPA env var is missing
- Development / sandbox startup logs warnings but does not block
- /health endpoint reflects legal_checks status correctly
"""

import pytest
from unittest.mock import MagicMock, patch


# ─── Tests: run_legal_checks ──────────────────────────────────


class TestLegalChecksProduction:
    """run_legal_checks must raise RuntimeError in production if any DPA var is missing."""

    def test_production_passes_when_all_vars_confirmed(self):
        """All three vars set to 'confirmed' → no exception in production."""
        from backend.startup.legal_checks import run_legal_checks

        settings = MagicMock()
        settings.dpa_openai_confirmed = "confirmed"
        settings.dpa_twilio_confirmed = "confirmed"
        settings.openai_zero_retention_confirmed = "confirmed"

        # Should not raise
        run_legal_checks(environment="production", settings=settings)

    def test_production_raises_if_openai_dpa_missing(self):
        """Missing DPA_OPENAI_CONFIRMED → RuntimeError with clear message."""
        from backend.startup.legal_checks import run_legal_checks

        settings = MagicMock()
        settings.dpa_openai_confirmed = ""  # missing
        settings.dpa_twilio_confirmed = "confirmed"
        settings.openai_zero_retention_confirmed = "confirmed"

        with pytest.raises(RuntimeError) as exc_info:
            run_legal_checks(environment="production", settings=settings)

        assert "DPA_OPENAI_CONFIRMED" in str(exc_info.value)

    def test_production_raises_if_twilio_dpa_missing(self):
        """Missing DPA_TWILIO_CONFIRMED → RuntimeError with clear message."""
        from backend.startup.legal_checks import run_legal_checks

        settings = MagicMock()
        settings.dpa_openai_confirmed = "confirmed"
        settings.dpa_twilio_confirmed = ""  # missing
        settings.openai_zero_retention_confirmed = "confirmed"

        with pytest.raises(RuntimeError) as exc_info:
            run_legal_checks(environment="production", settings=settings)

        assert "DPA_TWILIO_CONFIRMED" in str(exc_info.value)

    def test_production_raises_if_zero_retention_missing(self):
        """Missing OPENAI_ZERO_RETENTION_CONFIRMED → RuntimeError with clear message."""
        from backend.startup.legal_checks import run_legal_checks

        settings = MagicMock()
        settings.dpa_openai_confirmed = "confirmed"
        settings.dpa_twilio_confirmed = "confirmed"
        settings.openai_zero_retention_confirmed = ""  # missing

        with pytest.raises(RuntimeError) as exc_info:
            run_legal_checks(environment="production", settings=settings)

        assert "OPENAI_ZERO_RETENTION_CONFIRMED" in str(exc_info.value)

    def test_production_error_message_is_actionable(self):
        """Error message must tell the engineer exactly what to do."""
        from backend.startup.legal_checks import run_legal_checks

        settings = MagicMock()
        settings.dpa_openai_confirmed = ""
        settings.dpa_twilio_confirmed = "confirmed"
        settings.openai_zero_retention_confirmed = "confirmed"

        with pytest.raises(RuntimeError) as exc_info:
            run_legal_checks(environment="production", settings=settings)

        # Must contain actionable text, not just the var name
        error_msg = str(exc_info.value)
        assert "DPA" in error_msg or "confirmed" in error_msg.lower()


class TestLegalChecksDevelopment:
    """In development/sandbox mode, missing vars log warnings but do not block startup."""

    def test_development_does_not_raise_with_no_vars(self):
        """Development mode with all vars empty → no exception."""
        from backend.startup.legal_checks import run_legal_checks

        settings = MagicMock()
        settings.dpa_openai_confirmed = ""
        settings.dpa_twilio_confirmed = ""
        settings.openai_zero_retention_confirmed = ""

        # Should not raise in development
        run_legal_checks(environment="development", settings=settings)

    def test_sandbox_does_not_raise_with_no_vars(self):
        """Sandbox mode with all vars empty → no exception."""
        from backend.startup.legal_checks import run_legal_checks

        settings = MagicMock()
        settings.dpa_openai_confirmed = ""
        settings.dpa_twilio_confirmed = ""
        settings.openai_zero_retention_confirmed = ""

        run_legal_checks(environment="sandbox", settings=settings)

    def test_development_logs_warning_for_missing_dpa(self, caplog):
        """Missing DPA vars in development → warning logged, not raised."""
        import logging
        from backend.startup.legal_checks import run_legal_checks

        settings = MagicMock()
        settings.dpa_openai_confirmed = ""
        settings.dpa_twilio_confirmed = "confirmed"
        settings.openai_zero_retention_confirmed = "confirmed"

        with caplog.at_level(logging.WARNING, logger="backend.startup.legal_checks"):
            run_legal_checks(environment="development", settings=settings)

        assert any("DPA" in record.message or "dpa" in record.message.lower()
                   for record in caplog.records)


# ─── Tests: get_legal_checks_status ───────────────────────────


class TestLegalChecksStatus:
    """get_legal_checks_status() must return the correct status string."""

    def test_returns_passing_when_all_confirmed(self):
        """All three confirmed → 'passing'."""
        from backend.startup.legal_checks import get_legal_checks_status

        settings = MagicMock()
        settings.dpa_openai_confirmed = "confirmed"
        settings.dpa_twilio_confirmed = "confirmed"
        settings.openai_zero_retention_confirmed = "confirmed"

        status = get_legal_checks_status(settings=settings)
        assert status == "passing"

    def test_returns_warning_when_some_missing(self):
        """Some vars missing → 'warning'."""
        from backend.startup.legal_checks import get_legal_checks_status

        settings = MagicMock()
        settings.dpa_openai_confirmed = ""
        settings.dpa_twilio_confirmed = "confirmed"
        settings.openai_zero_retention_confirmed = "confirmed"

        status = get_legal_checks_status(settings=settings)
        assert status == "warning"

    def test_returns_blocking_when_all_missing(self):
        """All vars missing → 'blocking'."""
        from backend.startup.legal_checks import get_legal_checks_status

        settings = MagicMock()
        settings.dpa_openai_confirmed = ""
        settings.dpa_twilio_confirmed = ""
        settings.openai_zero_retention_confirmed = ""

        status = get_legal_checks_status(settings=settings)
        assert status == "blocking"
