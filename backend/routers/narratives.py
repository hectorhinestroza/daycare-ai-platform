"""REST API for EOD narrative generation and retrieval.

Endpoints:
    GET  /api/narratives/{center_id}/{child_id}          — narrative history (newest first)
    GET  /api/narratives/{center_id}/{child_id}/{date}   — narrative for a specific date
    POST /api/narratives/{center_id}/{child_id}/generate — generate (or regenerate) for a date
    POST /api/narratives/{center_id}/generate-all        — generate for all active children (cron)
"""

import json
import logging
from datetime import date as date_type
from datetime import datetime, timezone
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.services.narrative import generate_narrative
from backend.storage.database import get_db
from backend.storage.models import Child
from backend.storage.narrative_handlers import (
    get_narrative,
    get_narratives_for_child,
    upsert_narrative,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/narratives", tags=["narratives"])


# ─── Response Schema ──────────────────────────────────────────


class NarrativeOut(BaseModel):
    id: UUID
    center_id: UUID
    child_id: UUID
    date: date_type
    headline: str
    body: str
    tone: str
    photo_captions: dict
    published_at: Optional[datetime] = None
    admin_override: bool
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


def _serialize(n) -> dict:
    return {
        "id": n.id,
        "center_id": n.center_id,
        "child_id": n.child_id,
        "date": n.date,
        "headline": n.headline,
        "body": n.body,
        "tone": n.tone,
        "photo_captions": json.loads(n.photo_captions) if n.photo_captions else {},
        "published_at": n.published_at,
        "admin_override": n.admin_override,
        "created_at": n.created_at,
    }


# ─── Endpoints ────────────────────────────────────────────────


@router.get("/{center_id}/{child_id}", response_model=List[NarrativeOut])
def list_narratives(
    center_id: UUID,
    child_id: UUID,
    limit: int = 30,
    db: Session = Depends(get_db),
):
    """Narrative history for a child — newest first."""
    narratives = get_narratives_for_child(db, center_id, child_id, limit=limit)
    return [_serialize(n) for n in narratives]


@router.get("/{center_id}/{child_id}/{target_date}", response_model=NarrativeOut)
def get_narrative_for_date(
    center_id: UUID,
    child_id: UUID,
    target_date: date_type,
    db: Session = Depends(get_db),
):
    """Get the narrative for a specific date. Returns 404 if not yet generated."""
    narrative = get_narrative(db, center_id, child_id, target_date)
    if not narrative:
        raise HTTPException(status_code=404, detail="No narrative for this date")
    return _serialize(narrative)


@router.post("/{center_id}/{child_id}/generate", response_model=NarrativeOut)
async def generate_narrative_endpoint(
    center_id: UUID,
    child_id: UUID,
    target_date: Optional[date_type] = Query(default=None, description="Date to generate for (defaults to today UTC)"),
    db: Session = Depends(get_db),
):
    """Generate (or regenerate) an EOD narrative for a child on a given date.

    Idempotent: regenerating overwrites the existing narrative unless admin_override=True.
    """
    if target_date is None:
        target_date = datetime.now(timezone.utc).date()

    try:
        result = await generate_narrative(db, center_id, child_id, target_date)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Narrative generation failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Narrative generation failed")

    narrative = upsert_narrative(
        db,
        center_id=center_id,
        child_id=child_id,
        target_date=target_date,
        headline=result["headline"],
        body=result["body"],
        tone=result["tone"],
        photo_captions=result["photo_captions"],
    )
    return _serialize(narrative)


@router.post("/{center_id}/generate-all")
async def generate_all_narratives(
    center_id: UUID,
    target_date: Optional[date_type] = Query(default=None, description="Date to generate for (defaults to today UTC)"),
    force: bool = Query(default=False, description="Regenerate even if a narrative already exists for this date"),
    db: Session = Depends(get_db),
):
    """Generate EOD narratives for all active children in a center.

    By default skips children who already have a narrative for the target date.
    Pass force=true to regenerate everyone (e.g. to pick up late-day events).
    """
    if target_date is None:
        target_date = datetime.now(timezone.utc).date()

    children = (
        db.query(Child)
        .filter(Child.center_id == center_id, Child.status == "ACTIVE")
        .all()
    )

    if not children:
        return {"generated": 0, "failed": 0, "skipped": 0, "details": []}

    results = []
    generated = failed = skipped = 0

    for child in children:
        existing = get_narrative(db, center_id, child.id, target_date)

        # Always skip admin-overridden narratives
        if existing and existing.admin_override:
            skipped += 1
            results.append({"child_id": str(child.id), "name": child.name, "status": "skipped (admin override)"})
            continue

        # Skip if narrative already exists and force=False
        if existing and not force:
            skipped += 1
            results.append({"child_id": str(child.id), "name": child.name, "status": "skipped (already generated)"})
            continue

        try:
            result = await generate_narrative(db, center_id, child.id, target_date)
            upsert_narrative(
                db,
                center_id=center_id,
                child_id=child.id,
                target_date=target_date,
                **{k: result[k] for k in ("headline", "body", "tone", "photo_captions")},
            )
            generated += 1
            results.append({"child_id": str(child.id), "name": child.name, "status": "generated", "tone": result["tone"]})
        except Exception as e:
            failed += 1
            logger.error(f"Failed to generate narrative for {child.name} ({child.id}): {e}")
            results.append({"child_id": str(child.id), "name": child.name, "status": f"failed: {e}"})

    logger.info(f"generate-all for center {center_id} on {target_date}: {generated} generated, {failed} failed, {skipped} skipped")
    return {"generated": generated, "failed": failed, "skipped": skipped, "date": str(target_date), "details": results}
