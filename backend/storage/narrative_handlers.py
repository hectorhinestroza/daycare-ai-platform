"""CRUD operations for DailyNarrative.

One narrative per (center_id, child_id, date) — upserted on regeneration.
"""

import json
import uuid
from datetime import date as date_type
from typing import List, Optional

from sqlalchemy.orm import Session

from backend.storage.models import DailyNarrative


def get_narrative(
    db: Session,
    center_id: uuid.UUID,
    child_id: uuid.UUID,
    target_date: date_type,
) -> Optional[DailyNarrative]:
    """Fetch the narrative for a child on a specific date."""
    return (
        db.query(DailyNarrative)
        .filter(
            DailyNarrative.center_id == center_id,
            DailyNarrative.child_id == child_id,
            DailyNarrative.date == target_date,
        )
        .first()
    )


def get_narratives_for_child(
    db: Session,
    center_id: uuid.UUID,
    child_id: uuid.UUID,
    limit: int = 30,
) -> List[DailyNarrative]:
    """Fetch narrative history for a child, newest first."""
    return (
        db.query(DailyNarrative)
        .filter(
            DailyNarrative.center_id == center_id,
            DailyNarrative.child_id == child_id,
        )
        .order_by(DailyNarrative.date.desc())
        .limit(limit)
        .all()
    )


def upsert_narrative(
    db: Session,
    center_id: uuid.UUID,
    child_id: uuid.UUID,
    target_date: date_type,
    headline: str,
    body: str,
    tone: str,
    photo_captions: Optional[dict] = None,
) -> DailyNarrative:
    """Create or overwrite the narrative for a child on a given date."""
    existing = get_narrative(db, center_id, child_id, target_date)

    if existing and not existing.admin_override:
        existing.headline = headline
        existing.body = body
        existing.tone = tone
        existing.photo_captions = json.dumps(photo_captions or {})
        db.commit()
        db.refresh(existing)
        return existing

    narrative = DailyNarrative(
        id=uuid.uuid4(),
        center_id=center_id,
        child_id=child_id,
        date=target_date,
        headline=headline,
        body=body,
        tone=tone,
        photo_captions=json.dumps(photo_captions or {}),
    )
    db.add(narrative)
    db.commit()
    db.refresh(narrative)
    return narrative
