"""Public endpoints for parental consent collection.

These endpoints do NOT require typical Admin or Teacher auth.
They rely securely on the UUID magic link token.
"""

import logging
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.storage.database import get_db
from backend.storage.models import ConsentToken, ParentalConsent

logger = logging.getLogger(__name__)

router = APIRouter(tags=["consent"])


# ─── Schemas ──────────────────────────────────────────────────


class ConsentDetailOut(BaseModel):
    center_name: str
    child_first_name: str
    parent_name: str
    is_expired: bool
    is_used: bool

    model_config = {"from_attributes": True}


class SubmitConsentIn(BaseModel):
    # The 4 COPPA/legal required checkboxes
    consent_daily_reports: bool
    consent_photos: bool
    consent_audio_processing: bool
    consent_billing_data: bool
    
    # Digital signature (parent types their name)
    digital_signature: str


class SubmitConsentOut(BaseModel):
    status: str
    child_status: str


# ─── Endpoints ────────────────────────────────────────────────


@router.get("/api/consent/{token}", response_model=ConsentDetailOut)
def get_consent_details(token: UUID, db: Session = Depends(get_db)):
    """Fetch details needed to render the consent UI."""
    token_record = db.query(ConsentToken).filter(ConsentToken.token == token).first()
    
    if not token_record:
        raise HTTPException(status_code=404, detail="Consent token not found or invalid.")

    now = datetime.now(timezone.utc)
    is_expired = token_record.expires_at < now
    is_used = token_record.used_at is not None

    child = token_record.child
    center = token_record.center
    parent = token_record.parent

    # We only expose the first name to the UI for safety, just in case
    child_first_name = child.name.split(" ")[0]

    return ConsentDetailOut(
        center_name=center.name,
        child_first_name=child_first_name,
        parent_name=parent.name,
        is_expired=is_expired,
        is_used=is_used,
    )


@router.post("/api/consent/{token}", response_model=SubmitConsentOut, status_code=201)
def submit_consent(token: UUID, body: SubmitConsentIn, db: Session = Depends(get_db)):
    """Submit the parental consent form."""
    token_record = db.query(ConsentToken).filter(ConsentToken.token == token).first()
    
    if not token_record:
        raise HTTPException(status_code=404, detail="Consent token not found.")

    if token_record.used_at is not None:
        raise HTTPException(status_code=400, detail="This consent form has already been submitted.")

    if token_record.expires_at < datetime.now(timezone.utc):
        raise HTTPException(status_code=400, detail="This consent link has expired. Please contact your center.")

    # Validate all required checkboxes are checked
    if not all([body.consent_daily_reports, body.consent_photos, body.consent_audio_processing, body.consent_billing_data]):
        raise HTTPException(status_code=400, detail="All required consents must be agreed to.")

    # Create immutable consent record
    consent = ParentalConsent(
        center_id=token_record.center_id,
        child_id=token_record.child_id,
        parent_id=token_record.parent_id,
        consent_daily_reports=body.consent_daily_reports,
        consent_photos=body.consent_photos,
        consent_audio_processing=body.consent_audio_processing,
        consent_billing_data=body.consent_billing_data,
        consent_method="email_confirm",
        consented_at=datetime.now(timezone.utc),
        is_active=True,
    )
    db.add(consent)

    # Mark token used
    token_record.used_at = datetime.now(timezone.utc)

    # Activate child! 🥳
    child = token_record.child
    child.status = "ACTIVE"
    
    # Optional: Resolve any pending consent queue events! (future ticket)

    db.commit()
    logger.info(f"Parent {token_record.parent_id} granted consent for child {child.id}")

    return SubmitConsentOut(status="success", child_status="ACTIVE")
