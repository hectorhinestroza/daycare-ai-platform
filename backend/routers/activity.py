"""REST API for the activity log (audit trail).

Endpoint:
    GET /api/activity/{center_id} — paginated activity log
"""

import json
import logging
from datetime import datetime
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.storage.activity_handlers import get_activity_log
from backend.storage.database import get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/activity", tags=["activity"])


# ─── Response Schema ──────────────────────────────────────────


class ActivityLogOut(BaseModel):
    """Activity log entry response."""

    id: UUID
    center_id: UUID
    event_id: Optional[UUID] = None
    actor_id: Optional[UUID] = None
    actor_type: str
    action: str
    details: Optional[dict] = None
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


# ─── Custom serializer ───────────────────────────────────────


def _serialize_log(entry) -> dict:
    """Convert ActivityLog ORM object to response dict, parsing JSON details."""
    data = {
        "id": entry.id,
        "center_id": entry.center_id,
        "event_id": entry.event_id,
        "actor_id": entry.actor_id,
        "actor_type": entry.actor_type,
        "action": entry.action,
        "details": json.loads(entry.details) if entry.details else None,
        "created_at": entry.created_at,
    }
    return data


# ─── Endpoint ─────────────────────────────────────────────────


@router.get("/{center_id}", response_model=List[ActivityLogOut])
def list_activity_log(
    center_id: UUID,
    event_id: Optional[UUID] = None,
    action: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
):
    """Get paginated activity log for a center."""
    entries = get_activity_log(db, center_id, event_id=event_id, action=action, limit=limit, offset=offset)
    return [_serialize_log(e) for e in entries]
