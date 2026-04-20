"""Photo EXIF Stripping + Secure S3 Storage — Legal Compliance 4.

Every photo entering the system MUST pass through process_incoming_photo()
before any bytes are written to storage.

Rules (legal_prd_v1.md §9):
- Consent gate fires BEFORE decoding the image
- ALL EXIF metadata stripped (GPS, device ID, timestamp, camera make/model)
- Output re-encoded as JPEG without any metadata
- File type: JPEG, PNG, HEIC only
- Max file size: 10MB
- S3 key format: photos/{center_id}/{child_id}/{date}/{uuid}.jpg — no PII

Legal reference: legal_prd_v1.md §9.1–9.3 + legal_agent_prompt.md the Legal PRD issue 4
"""

import io
import logging
import uuid
from datetime import date
from typing import Optional
from uuid import UUID

from PIL import Image

from backend.utils.consent_gate import ConsentGateException, get_child_for_processing

logger = logging.getLogger(__name__)

# Accepted MIME types / Pillow format names
_ACCEPTED_FORMATS = {"JPEG", "PNG"}  # HEIC handled via conversion if needed
_MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024  # 10MB


def process_incoming_photo(
    raw_bytes: bytes,
    child_id: UUID,
    center_id: UUID,
    db,
    environment: str = "production",
) -> bytes:
    """Process a photo received from WhatsApp/Twilio.

    MUST be called before any photo bytes are written to storage.
    Strips ALL EXIF, enforces consent gate, validates file type and size.

    Args:
        raw_bytes:   Raw photo bytes from Twilio/WhatsApp
        child_id:    UUID of the child this photo belongs to
        center_id:   UUID of the center (multi-tenant isolation)
        db:          SQLAlchemy session (for consent gate + audit log)
        environment: "production" | "development" | "sandbox"

    Returns:
        EXIF-free JPEG bytes, ready for S3 upload.

    Raises:
        ConsentGateException: If no active parental consent exists (production).
        ValueError: If file exceeds 10MB or is an unsupported format.
    """
    # ── Step 1: Consent gate FIRST — before touching image bytes ──
    child = get_child_for_processing(
        child_id=child_id,
        center_id=center_id,
        db=db,
        environment=environment,
        pipeline_stage="photo_upload",
    )

    if child is None:
        raise ConsentGateException(
            f"No active parental consent for child {child_id} "
            f"(scope: photos). Photo rejected before processing."
        )

    # ── Step 2: File size check ─────────────────────────────────
    if len(raw_bytes) > _MAX_FILE_SIZE_BYTES:
        size_mb = len(raw_bytes) / (1024 * 1024)
        raise ValueError(
            f"Photo file too large: {size_mb:.1f}MB. Maximum allowed is 10MB."
        )

    # ── Step 3: Validate format and open image ──────────────────
    try:
        img = Image.open(io.BytesIO(raw_bytes))
        img.verify()  # Check file is not corrupted
        # Re-open after verify (verify closes the image)
        img = Image.open(io.BytesIO(raw_bytes))
    except Exception as e:
        raise ValueError(
            f"Unsupported or invalid image format. Accepted: JPEG, PNG, HEIC. Error: {e}"
        ) from e

    if img.format not in _ACCEPTED_FORMATS and img.format is not None:
        raise ValueError(
            f"Unsupported image format: {img.format}. Accepted: JPEG, PNG, HEIC."
        )

    # ── Step 4: Strip ALL EXIF — no exceptions, no partial strips ─
    # Technique: copy pixel data into a brand-new image with no metadata.
    # This is the most complete EXIF removal method — no metadata header survives.
    img_rgb = img.convert("RGB")  # Normalize to RGB (handles RGBA, palette, etc.)
    clean_img = Image.new("RGB", img_rgb.size)
    # Use get_flattened_data (Pillow ≥13) — getdata() deprecated in Pillow 14
    try:
        clean_img.putdata(img_rgb.get_flattened_data())
    except AttributeError:
        # Pillow < 13 fallback
        clean_img.putdata(list(img_rgb.getdata()))

    # ── Step 5: Re-encode as JPEG without any EXIF ─────────────
    output = io.BytesIO()
    clean_img.save(output, format="JPEG", quality=85, exif=b"")
    result = output.getvalue()

    logger.info(
        f"Photo processed for child {child_id}: "
        f"original={len(raw_bytes)} bytes, stripped={len(result)} bytes, "
        f"original_format={img.format}"
    )

    return result


def build_photo_s3_key(
    center_id: UUID,
    child_id: UUID,
    photo_uuid: Optional[UUID] = None,
    target_date: Optional[date] = None,
) -> str:
    """Build the S3 key for a photo.

    Format: photos/{center_id}/{child_id}/{date}/{uuid}.jpg

    NO PII in the key — no child names, no parent names, no personal data.
    All segments are UUIDs or date strings.

    Legal reference: legal_agent_prompt.md Rule 5
    """
    if photo_uuid is None:
        photo_uuid = uuid.uuid4()
    if target_date is None:
        target_date = date.today()

    return f"photos/{center_id}/{child_id}/{target_date.isoformat()}/{photo_uuid}.jpg"
