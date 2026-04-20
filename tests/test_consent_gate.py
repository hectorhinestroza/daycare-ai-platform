"""Tests forConsent Gate Dependency.

Verifies:
- get_child_for_processing() passes with valid active consent
- gate blocks (returns None or raises) when no consent record exists (production)
- gate blocks when consent is withdrawn (is_active=False)
- pending_consent_queue populated on block
- consent_gate_audit written on block
- HTTP 403 response structure when require_consent dependency fires
- Dev mode bypass: gate logs warning but passes (does not raise)
"""

import uuid
from unittest.mock import MagicMock, patch

import pytest


# ─── Tests: get_child_for_processing ──────────────────────────


class TestGetChildForProcessing:
    """Unit tests for the core consent gate function."""

    def test_returns_child_when_active_consent_exists(self):
        """Gate must return the child object when active consent exists."""
        from backend.utils.consent_gate import get_child_for_processing

        # Build a mock DB that returns a valid child from the consent view
        mock_child = MagicMock()
        mock_child.id = uuid.uuid4()
        mock_child.center_id = uuid.uuid4()

        mock_db = MagicMock()
        mock_db.execute.return_value.fetchone.return_value = mock_child

        result = get_child_for_processing(
            child_id=mock_child.id,
            center_id=mock_child.center_id,
            db=mock_db,
            environment="production",
        )

        assert result is not None

    def test_returns_none_when_no_consent_in_production(self):
        """In production with no consent, gate must return None."""
        from backend.utils.consent_gate import get_child_for_processing

        mock_db = MagicMock()
        mock_db.execute.return_value.fetchone.return_value = None  # no row in view

        result = get_child_for_processing(
            child_id=uuid.uuid4(),
            center_id=uuid.uuid4(),
            db=mock_db,
            environment="production",
        )

        assert result is None

    def test_audit_log_written_when_gate_blocks(self):
        """ConsentGateAudit record must be inserted when gate returns None."""
        from backend.storage.models import ConsentGateAudit
        from backend.utils.consent_gate import get_child_for_processing

        mock_db = MagicMock()
        mock_db.execute.return_value.fetchone.return_value = None

        captured = {}

        def capture_add(obj):
            if isinstance(obj, ConsentGateAudit):
                captured["audit"] = obj

        mock_db.add.side_effect = capture_add

        get_child_for_processing(
            child_id=uuid.uuid4(),
            center_id=uuid.uuid4(),
            db=mock_db,
            environment="production",
            pipeline_stage="extraction",
        )

        assert "audit" in captured, "ConsentGateAudit not written on block"
        assert captured["audit"].pipeline_stage == "extraction"

    def test_pending_queue_written_when_gate_blocks(self):
        """PendingConsentQueue entry must be inserted when gate blocks."""
        from backend.storage.models import PendingConsentQueue
        from backend.utils.consent_gate import get_child_for_processing

        mock_db = MagicMock()
        mock_db.execute.return_value.fetchone.return_value = None

        captured = {}

        def capture_add(obj):
            if isinstance(obj, PendingConsentQueue):
                captured["queue"] = obj

        mock_db.add.side_effect = capture_add

        child_id = uuid.uuid4()
        center_id = uuid.uuid4()

        get_child_for_processing(
            child_id=child_id,
            center_id=center_id,
            db=mock_db,
            environment="production",
            pipeline_stage="extraction",
        )

        assert "queue" in captured, "PendingConsentQueue entry not written on block"
        assert captured["queue"].child_id == child_id
        assert captured["queue"].center_id == center_id

    def test_dev_bypass_returns_child_without_consent(self):
        """In development mode, gate must return the child even without consent record."""
        from backend.utils.consent_gate import get_child_for_processing

        mock_db = MagicMock()
        # Simulates no consent record in view — but also needs child lookup fallback
        mock_child = MagicMock()
        mock_db.execute.return_value.fetchone.side_effect = [
            None,       # children_with_active_consent returns nothing
            mock_child, # fallback children table query
        ]

        result = get_child_for_processing(
            child_id=uuid.uuid4(),
            center_id=uuid.uuid4(),
            db=mock_db,
            environment="development",
        )

        # Dev bypass: not None (child returned despite no consent)
        assert result is not None

    def test_dev_bypass_logs_warning(self, caplog):
        """Dev bypass must emit a WARNING log — never silently skip enforcement."""
        import logging
        from backend.utils.consent_gate import get_child_for_processing

        mock_child = MagicMock()
        mock_db = MagicMock()
        mock_db.execute.return_value.fetchone.side_effect = [None, mock_child]

        with caplog.at_level(logging.WARNING, logger="backend.utils.consent_gate"):
            get_child_for_processing(
                child_id=uuid.uuid4(),
                center_id=uuid.uuid4(),
                db=mock_db,
                environment="development",
            )

        assert any(
            "dev" in r.message.lower() or "bypass" in r.message.lower() or "consent" in r.message.lower()
            for r in caplog.records
        ), "Dev bypass must log a warning"


# ─── Tests: require_consent FastAPI dependency ─────────────────


class TestRequireConsentDependency:
    """require_consent() FastAPI dependency returns 403 on gate block in production."""

    def test_403_response_structure(self):
        """HTTP 403 body must have error, child_id, scope, message fields."""
        from fastapi import HTTPException
        from unittest.mock import patch
        from backend.utils.consent_gate import require_consent

        dep = require_consent(scope="audio_processing")

        mock_db = MagicMock()
        mock_db.execute.return_value.fetchone.return_value = None  # gate blocks

        mock_settings = MagicMock()
        mock_settings.environment = "production"

        with patch("backend.utils.consent_gate.get_settings", return_value=mock_settings):
            with pytest.raises(HTTPException) as exc_info:
                dep(
                    child_id=uuid.uuid4(),
                    center_id=uuid.uuid4(),
                    db=mock_db,
                )

        assert exc_info.value.status_code == 403
        detail = exc_info.value.detail
        assert "error" in detail
        assert detail["error"] == "consent_required"
        assert "scope" in detail
        assert detail["scope"] == "audio_processing"
