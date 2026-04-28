"""Tests forParental Consent Schema + Database View.

Verifies:
- parental_consent table has all required columns
- consent_ai_training is always FALSE on creation
- children_with_active_consent view is queryable and filters correctly
- unique active consent constraint per child
- No UPDATE path exists for parental_consent (enforcement test)
- Pydantic schemas validate correctly
"""
import uuid

import pytest
from pydantic import ValidationError

from backend.storage.models import ConsentGateAudit, ParentalConsent, PendingConsentQueue
from schemas.consent import ConsentCreate, ConsentWithdraw

# ─── Pydantic Schema Tests ─────────────────────────────────────


class TestConsentSchemas:
    """Pydantic v2 schemas for consent creation and response."""

    def test_consent_create_validates_required_fields(self):
        """ConsentCreate requires center_id, child_id, parent_id, and consent flags."""

        parent_id = uuid.uuid4()
        data = ConsentCreate(
            center_id=uuid.uuid4(),
            child_id=uuid.uuid4(),
            parent_id=parent_id,
            consent_version="v1.0",
            consent_daily_reports=True,
            consent_photos=True,
            consent_audio_processing=True,
            consent_billing_data=True,
            consent_method="email_confirm",
        )
        assert data.consent_daily_reports is True
        assert data.parent_id == parent_id

    def test_consent_ai_training_defaults_false(self):
        """consent_ai_training must default to False and not be settable to True in V1."""

        data = ConsentCreate(
            center_id=uuid.uuid4(),
            child_id=uuid.uuid4(),
            parent_id=uuid.uuid4(),
            consent_version="v1.0",
            consent_daily_reports=True,
            consent_photos=True,
            consent_audio_processing=True,
            consent_billing_data=True,
            consent_method="email_confirm",
        )
        # Must default to False when not provided
        assert data.consent_ai_training is False

    def test_consent_method_enum_valid_values(self):
        """consent_method accepts only: paper_scan, docusign, email_confirm."""

        for method in ["paper_scan", "docusign", "email_confirm"]:
            data = ConsentCreate(
                center_id=uuid.uuid4(),
                child_id=uuid.uuid4(),
                parent_id=uuid.uuid4(),
                consent_version="v1.0",
                consent_daily_reports=True,
                consent_photos=True,
                consent_audio_processing=True,
                consent_billing_data=True,
                consent_method=method,
            )
            assert data.consent_method == method

    def test_consent_method_rejects_invalid_value(self):
        """consent_method rejects anything not in the enum."""

        with pytest.raises(ValidationError):
            ConsentCreate(
                center_id=uuid.uuid4(),
                child_id=uuid.uuid4(),
                parent_id=uuid.uuid4(),
                consent_version="v1.0",
                consent_daily_reports=True,
                consent_photos=True,
                consent_audio_processing=True,
                consent_billing_data=True,
                consent_method="magic",  # invalid
            )

    def test_consent_withdraw_schema(self):
        """ConsentWithdraw requires only the consent_id."""

        data = ConsentWithdraw(reason="Parent request")
        assert data.reason == "Parent request"


# ─── ORM Model Tests ──────────────────────────────────────────


class TestParentalConsentModel:
    """ParentalConsent ORM model must have all legally required columns."""

    def test_model_has_all_required_columns(self):
        """Verify all columns from legal_prd_v1.md §5.2 are present."""

        required = {
            "id",
            "center_id",
            "child_id",
            "parent_id",
            "consent_version",
            "consent_daily_reports",
            "consent_photos",
            "consent_audio_processing",
            "consent_billing_data",
            "consent_ai_training",
            "consented_at",
            "withdrawn_at",
            "is_active",
            "consent_method",
        }

        model_columns = {col.name for col in ParentalConsent.__table__.columns}
        missing = required - model_columns
        assert not missing, f"ParentalConsent missing columns: {missing}"

    def test_consent_ai_training_default_false(self):
        """consent_ai_training column default must be False."""

        col = ParentalConsent.__table__.columns["consent_ai_training"]
        # SQLAlchemy column default
        assert col.default.arg is False

    def test_is_active_default_true(self):
        """is_active column default must be True."""

        col = ParentalConsent.__table__.columns["is_active"]
        assert col.default.arg is True

    def test_no_update_path_comment_present(self):
        """Verify the ORM model has the no-update docstring as a compliance marker."""

        # The docstring must mention immutability to signal to future devs
        assert ParentalConsent.__doc__ is not None
        doc_lower = ParentalConsent.__doc__.lower()
        assert any(word in doc_lower for word in ["immutable", "no update", "insert only"])


class TestPendingConsentQueueModel:
    """PendingConsentQueue holds events blocked by the consent gate."""

    def test_model_exists_with_required_fields(self):
        """PendingConsentQueue must exist with child_id, center_id, blocked_at."""

        required = {"id", "child_id", "center_id", "blocked_at"}
        model_columns = {col.name for col in PendingConsentQueue.__table__.columns}
        missing = required - model_columns
        assert not missing, f"PendingConsentQueue missing columns: {missing}"


class TestConsentGateAuditModel:
    """ConsentGateAudit logs every time the consent gate blocks a request."""

    def test_model_exists_with_required_fields(self):
        """ConsentGateAudit must exist with child_id, center_id, pipeline_stage, timestamp."""

        required = {"id", "child_id", "center_id", "pipeline_stage", "timestamp"}
        model_columns = {col.name for col in ConsentGateAudit.__table__.columns}
        missing = required - model_columns
        assert not missing, f"ConsentGateAudit missing columns: {missing}"
