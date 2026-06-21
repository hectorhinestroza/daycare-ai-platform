"""Public endpoints for parental consent collection.

These endpoints do NOT require typical Admin or Teacher auth.
They rely securely on the UUID magic link token.
"""

import asyncio
import logging
import threading
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.config import get_settings
from backend.services.email import send_parent_welcome_email
from backend.storage.database import get_db
from backend.storage.models import ConsentToken, ParentalConsent
from backend.utils.auth_tokens import generate_token

# Parent portal tokens live 1 year. The director can revoke via
# `revoke_nonce` if a parent loses access to their email account or shares
# the link inappropriately.
PARENT_TOKEN_EXPIRY_DAYS = 365


def _as_aware_utc(dt: datetime) -> datetime:
    """SQLite drops tzinfo on DateTime(timezone=True) round-trips; Postgres
    keeps it. Force aware UTC so comparisons work the same in tests + prod.
    """
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt

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
    is_expired = _as_aware_utc(token_record.expires_at) < now
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

    if _as_aware_utc(token_record.expires_at) < datetime.now(timezone.utc):
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

    # Mint a parent bearer token scoped to this child and email the
    # bootstrap URL so the family can open the portal immediately.
    # Failures here are non-fatal: consent is already recorded, the
    # director can re-issue a token from the console if email never lands.
    try:
        settings = get_settings()
        parent_token, _ = generate_token(
            role="parent",
            sub=token_record.parent_id,
            center_id=token_record.center_id,
            child_ids=[token_record.child_id],
            expires_in_days=PARENT_TOKEN_EXPIRY_DAYS,
        )
        portal_url = f"{settings.app_base_url.rstrip('/')}/app?token={parent_token}"

        parent = token_record.parent
        center = token_record.center
        child_first = child.name.split()[0] if child.name else "your child"

        if parent and parent.email:
            def _send():
                asyncio.run(send_parent_welcome_email(
                    to_email=parent.email,
                    parent_name=parent.name,
                    child_name=child_first,
                    center_name=center.name if center else "Your Daycare",
                    portal_url=portal_url,
                ))
            threading.Thread(target=_send, daemon=True).start()
        else:
            logger.warning(
                f"Skipping welcome email for child {child.id} — parent contact has no email"
            )
    except Exception:
        # Log full trace but don't fail the consent submission.
        logger.exception("welcome_email.dispatch_failed child_id=%s", child.id)

    return SubmitConsentOut(status="success", child_status="ACTIVE")
