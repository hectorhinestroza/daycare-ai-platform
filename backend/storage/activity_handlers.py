"""CRUD operations for the activity log (audit trail).

Every admin action (approve, reject, edit, batch approve) is logged here
for compliance and debugging. All queries filter by center_id.
"""

import json
import uuid
from typing import List, Optional

from sqlalchemy.orm import Session

from backend.storage.models import ActivityLog


def log_activity(
    db: Session,
    center_id: uuid.UUID,
    action: str,
    event_id: Optional[uuid.UUID] = None,
    actor_id: Optional[uuid.UUID] = None,
    actor_type: str = "system",
    details: Optional[dict] = None,
) -> ActivityLog:
    """Create an audit log entry."""
    entry = ActivityLog(
        id=uuid.uuid4(),
        center_id=center_id,
        event_id=event_id,
        actor_id=actor_id,
        actor_type=actor_type,
        action=action,
        details=json.dumps(details) if details else None,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


def get_activity_log(
    db: Session,
    center_id: uuid.UUID,
    event_id: Optional[uuid.UUID] = None,
    action: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> List[ActivityLog]:
    """Get paginated activity log entries, optionally filtered."""
    q = db.query(ActivityLog).filter(ActivityLog.center_id == center_id)
    if event_id:
        q = q.filter(ActivityLog.event_id == event_id)
    if action:
        q = q.filter(ActivityLog.action == action)
    return q.order_by(ActivityLog.created_at.desc()).limit(limit).offset(offset).all()
