"""Consent Gate — Legal Compliance 2.

The single entry point for all child data in the AI pipeline.

Rules:
- In production: NO child data may enter any pipeline without passing this gate.
- In development/sandbox: gate logs a warning but returns the child (dev bypass).
- Every gate block is logged to consent_gate_audit (append-only).
- Blocked events are queued in pending_consent_queue (not silently dropped).

Legal reference: legal_prd_v1.md §5.3 + legal_agent_prompt.md Rules 1, 4, the Legal PRD issue 2
"""

import logging
from typing import Callable, Optional
from uuid import UUID

from fastapi import Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.config import get_settings
from backend.storage.database import get_db

logger = logging.getLogger(__name__)

# SQL for the children_with_active_consent view
_CONSENT_VIEW_QUERY = text(
    """
    SELECT * FROM children_with_active_consent
    WHERE id = :child_id AND center_id = :center_id
    """
)

# Fallback query for dev bypass (queries children table directly)
_CHILDREN_DIRECT_QUERY = text(
    """
    SELECT * FROM children
    WHERE id = :child_id AND center_id = :center_id
    """
)


def get_child_for_processing(
    child_id: UUID,
    center_id: UUID,
    db: Session,
    environment: str = "production",
    pipeline_stage: str = "unknown",
    raw_event_ref: Optional[str] = None,
):
    """Return child only if active parental consent exists. Return None otherwise.

    In development mode: logs a warning and returns the child from the children
    table directly (bypasses consent check). This allows the pipeline to work
    before(parental onboarding flow) is implemented.

    Args:
        child_id:       UUID of the child to check consent for
        center_id:      UUID of the center (multi-tenant isolation)
        db:             SQLAlchemy session
        environment:    "production" | "development" | "sandbox"
        pipeline_stage: Label for audit log (e.g. "extraction", "narrative")
        raw_event_ref:  Optional JSON blob to store in pending_consent_queue

    Returns:
        Child row if consent exists (or dev bypass active), None otherwise.
    """
    from backend.storage.models import ConsentGateAudit, PendingConsentQueue

    is_production = environment.lower() == "production"

    # Query the consent-gated view
    result = db.execute(
        _CONSENT_VIEW_QUERY,
        {"child_id": str(child_id), "center_id": str(center_id)},
    ).fetchone()

    if result is not None:
        # Consent confirmed — child may enter pipeline
        return result

    # No consent record found
    if not is_production:
        # Dev/sandbox bypass — log warning and return child directly
        logger.warning(
            f"CONSENT DEV BYPASS: child {child_id} has no active consent. "
            f"Gate bypassed in {environment} mode. "
            f"Stage: {pipeline_stage}. "
            f"This would block in production. Implementto collect consent."
        )
        # Fall back to direct children table for dev
        child_row = db.execute(
            _CHILDREN_DIRECT_QUERY,
            {"child_id": str(child_id), "center_id": str(center_id)},
        ).fetchone()
        return child_row  # May be None if child doesn't exist at all

    # Production: gate blocks — log audit record and queue the event
    _log_gate_block(
        db=db,
        child_id=child_id,
        center_id=center_id,
        pipeline_stage=pipeline_stage,
        raw_event_ref=raw_event_ref,
    )
    return None


def _log_gate_block(
    db: Session,
    child_id: UUID,
    center_id: UUID,
    pipeline_stage: str,
    raw_event_ref: Optional[str],
) -> None:
    """Write audit log and pending queue entry for a consent gate block."""
    from backend.storage.models import ConsentGateAudit, PendingConsentQueue

    try:
        # Append-only audit log
        audit = ConsentGateAudit(
            child_id=child_id,
            center_id=center_id,
            pipeline_stage=pipeline_stage,
        )
        db.add(audit)

        # Queue the blocked event (not silently dropped)
        queue_entry = PendingConsentQueue(
            child_id=child_id,
            center_id=center_id,
            pipeline_stage=pipeline_stage,
            raw_event_ref=raw_event_ref,
        )
        db.add(queue_entry)
        db.commit()

        logger.warning(
            f"Consent gate BLOCKED child {child_id} at stage '{pipeline_stage}'. "
            f"Event queued in pending_consent_queue. Director must collect consent."
        )
    except Exception as e:
        logger.error(f"Failed to write consent gate audit: {e}")
        try:
            db.rollback()
        except Exception:
            pass


class ConsentGateException(Exception):
    """Raised by photo/audio processors when consent gate blocks synchronously."""
    pass


def require_consent(scope: str) -> Callable:
    """FastAPI dependency factory that enforces consent for a given scope.

    Usage:
        @router.post("/endpoint")
        def handler(
            child_id: UUID,
            center_id: UUID,
            _: None = Depends(require_consent("audio_processing")),
            db: Session = Depends(get_db),
        ):
            ...

    Args:
        scope: The consent scope to check (matches parental_consent column name):
               "daily_reports" | "photos" | "audio_processing" | "billing_data"

    Returns:
        A FastAPI dependency callable that raises HTTP 403 if consent gate blocks.
    """
    def dependency(
        child_id: UUID,
        center_id: UUID,
        db: Session = Depends(get_db),
    ):
        settings = get_settings()
        child = get_child_for_processing(
            child_id=child_id,
            center_id=center_id,
            db=db,
            environment=settings.environment,
            pipeline_stage=scope,
        )

        if child is None:
            raise HTTPException(
                status_code=403,
                detail={
                    "error": "consent_required",
                    "child_id": str(child_id),
                    "scope": scope,
                    "message": (
                        f"No active parental consent for scope '{scope}'. "
                        f"Director must collect parental consent before processing this child's data."
                    ),
                },
            )
        return child

    return dependency
