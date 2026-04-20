"""Parental Consent Pydantic schemas — Legal Compliance 1.

Source of truth: legal_prd_v1.md §5.2 and legal_agent_prompt.md the Legal PRD issue 1.

IMMUTABILITY RULE: parental_consent records are NEVER updated.
Consent changes (withdrawal, version upgrade) are modeled as new inserts.
There is NO ConsentUpdate schema by design.

Consent collection triggers:
    Director adds child → child status = PENDING_CONSENT
    → system emails magic link to parent
    → parent completes this consent form
    → ConsentCreate submitted → child status = ACTIVE
"""

from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class ConsentMethod(str, Enum):
    """How the consent was collected."""
    paper_scan = "paper_scan"
    docusign = "docusign"
    email_confirm = "email_confirm"


class ConsentCreate(BaseModel):
    """Schema for creating a new parental consent record.

    All four data-processing consent flags must be TRUE for the child to
    pass the consent gate and enter the AI pipeline.

    consent_ai_training is intentionally absent from required fields —
    it defaults to False and is hidden from the V1 consent form UI.
    """
    center_id: UUID
    child_id: UUID
    parent_id: UUID
    consent_version: str = "v1.0"

    # Four required consent flags — all must be True before child enters pipeline
    consent_daily_reports: bool
    consent_photos: bool
    consent_audio_processing: bool
    consent_billing_data: bool

    # AI training consent: always False in V1 — not exposed in consent form UI
    # Legal reference: legal_prd_v1.md §7.1
    consent_ai_training: bool = Field(default=False)

    # How consent was obtained
    consent_method: ConsentMethod

    # Optional: IP address for audit trail
    ip_address: Optional[str] = None


class ConsentResponse(BaseModel):
    """Read schema for a parental consent record."""
    id: UUID
    center_id: UUID
    child_id: UUID
    parent_id: UUID
    consent_version: str
    consent_daily_reports: bool
    consent_photos: bool
    consent_audio_processing: bool
    consent_billing_data: bool
    consent_ai_training: bool
    consent_method: str
    consented_at: datetime
    withdrawn_at: Optional[datetime] = None
    is_active: bool

    model_config = {"from_attributes": True}


class ConsentWithdraw(BaseModel):
    """Schema for withdrawing parental consent.

    Withdrawal does NOT delete the consent record — it inserts a new record
    with is_active=False and sets withdrawn_at on the existing record.
    All child data is deleted within 72 hours per COPPA.
    """
    reason: Optional[str] = None
