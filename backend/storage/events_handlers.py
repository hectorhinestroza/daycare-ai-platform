"""CRUD operations for events and related entities.

All queries filter by center_id for multi-tenant isolation.
This is the data access layer — never bypass it with raw SQL.
"""

import uuid
from datetime import UTC, datetime
from typing import List, Optional

from sqlalchemy.orm import Session

from backend.storage.activity_handlers import log_activity
from backend.storage.models import Child, Event, Teacher

# ─── Event CRUD ───────────────────────────────────────────────


def create_event(
    db: Session,
    center_id: uuid.UUID,
    child_name: str,
    event_type: str,
    raw_transcript: str,
    review_tier: str = "teacher",
    confidence_score: float = 0.5,
    needs_director_review: bool = False,
    needs_review: bool = False,
    event_time: Optional[datetime] = None,
    details: Optional[str] = None,
    teacher_id: Optional[uuid.UUID] = None,
    child_id: Optional[uuid.UUID] = None,
) -> Event:
    """Create and persist a new event."""
    event = Event(
        id=uuid.uuid4(),
        center_id=center_id,
        child_id=child_id,
        teacher_id=teacher_id,
        child_name=child_name,
        event_type=event_type,
        event_time=event_time,
        details=details,
        raw_transcript=raw_transcript,
        review_tier=review_tier,
        confidence_score=confidence_score,
        needs_director_review=needs_director_review,
        needs_review=needs_review,
        status="PENDING",
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


def create_event_from_base(
    db: Session,
    base_event,  # schemas.events.BaseEvent
    teacher_id: Optional[uuid.UUID] = None,
    child_id: Optional[uuid.UUID] = None,
) -> Event:
    """Create a DB event from a Pydantic BaseEvent (post-extraction)."""
    event = Event(
        id=base_event.id,
        center_id=uuid.UUID(base_event.center_id) if isinstance(base_event.center_id, str) else base_event.center_id,
        child_id=child_id,
        teacher_id=teacher_id,
        child_name=base_event.child_name,
        event_type=base_event.event_type.value,
        event_time=base_event.event_time,
        details=base_event.details,
        raw_transcript=base_event.raw_transcript,
        review_tier=base_event.review_tier,
        confidence_score=base_event.confidence_score,
        needs_director_review=base_event.needs_director_review,
        needs_review=base_event.needs_review,
        status=base_event.status.value,
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


def get_event(db: Session, event_id: uuid.UUID, center_id: uuid.UUID) -> Optional[Event]:
    """Get a single event, filtered by center_id."""
    return db.query(Event).filter(Event.id == event_id, Event.center_id == center_id).first()


def get_events_pending_teacher(db: Session, center_id: uuid.UUID) -> List[Event]:
    """Get events awaiting teacher review."""
    return (
        db.query(Event)
        .filter(
            Event.center_id == center_id,
            Event.status == "PENDING",
            Event.review_tier == "teacher",
        )
        .order_by(Event.created_at.desc())
        .all()
    )


def get_events_pending_director(db: Session, center_id: uuid.UUID) -> List[Event]:
    """Get events awaiting director review (flagged events only)."""
    return (
        db.query(Event)
        .filter(
            Event.center_id == center_id,
            Event.status == "PENDING",
            Event.needs_director_review,
        )
        .order_by(Event.created_at.desc())
        .all()
    )


def approve_event(
    db: Session,
    event_id: uuid.UUID,
    center_id: uuid.UUID,
    reviewed_by: Optional[uuid.UUID] = None,
) -> Optional[Event]:
    """Approve an event (teacher or director)."""
    event = get_event(db, event_id, center_id)
    if not event:
        return None
    event.status = "APPROVED"
    event.reviewed_by = reviewed_by
    event.reviewed_at = datetime.now(UTC)
    db.commit()
    db.refresh(event)
    log_activity(
        db,
        center_id,
        "APPROVE",
        event_id=event_id,
        actor_id=reviewed_by,
        details={"child_name": event.child_name, "event_type": event.event_type},
    )
    return event


def reject_event(
    db: Session,
    event_id: uuid.UUID,
    center_id: uuid.UUID,
    reviewed_by: Optional[uuid.UUID] = None,
) -> Optional[Event]:
    """Reject an event."""
    event = get_event(db, event_id, center_id)
    if not event:
        return None
    event.status = "REJECTED"
    event.reviewed_by = reviewed_by
    event.reviewed_at = datetime.now(UTC)
    db.commit()
    db.refresh(event)
    log_activity(
        db,
        center_id,
        "REJECT",
        event_id=event_id,
        actor_id=reviewed_by,
        details={"child_name": event.child_name, "event_type": event.event_type},
    )
    return event


def update_event(
    db: Session,
    event_id: uuid.UUID,
    center_id: uuid.UUID,
    updates: dict,
) -> Optional[Event]:
    """Inline edit an event (partial update).

    Allowed fields: child_name, details, event_type, event_time.
    """
    event = get_event(db, event_id, center_id)
    if not event:
        return None

    allowed_fields = {"child_name", "details", "event_type", "event_time"}
    old_values = {}
    for key, value in updates.items():
        if key in allowed_fields and value is not None:
            old_values[key] = getattr(event, key)
            setattr(event, key, value)

    db.commit()
    db.refresh(event)
    log_activity(
        db,
        center_id,
        "EDIT",
        event_id=event_id,
        details={"changes": {k: {"old": str(v), "new": str(updates[k])} for k, v in old_values.items()}},
    )
    return event


def get_events_by_child(
    db: Session,
    center_id: uuid.UUID,
    child_name: str,
    status: Optional[str] = None,
) -> List[Event]:
    """Get all events for a child, optionally filtered by status."""
    q = db.query(Event).filter(
        Event.center_id == center_id,
        Event.child_name == child_name,
    )
    if status:
        q = q.filter(Event.status == status)
    return q.order_by(Event.created_at.desc()).all()


def get_approved_events_for_child(
    db: Session,
    center_id: uuid.UUID,
    child_id: uuid.UUID,
    limit: int = 50,
    offset: int = 0,
) -> List[Event]:
    """Get approved events for a specific child (parent feed)."""
    return (
        db.query(Event)
        .filter(
            Event.center_id == center_id,
            Event.child_id == child_id,
            Event.status == "APPROVED",
        )
        .order_by(Event.created_at.desc())
        .limit(limit)
        .offset(offset)
        .all()
    )


def batch_approve_events(
    db: Session,
    center_id: uuid.UUID,
    child_name: str,
    reviewed_by: Optional[uuid.UUID] = None,
) -> int:
    """Approve all pending events for a child. Returns count of approved events."""
    now = datetime.now(UTC)
    count = (
        db.query(Event)
        .filter(
            Event.center_id == center_id,
            Event.child_name == child_name,
            Event.status == "PENDING",
        )
        .update(
            {
                Event.status: "APPROVED",
                Event.reviewed_by: reviewed_by,
                Event.reviewed_at: now,
            },
            synchronize_session="fetch",
        )
    )
    db.commit()
    if count > 0:
        log_activity(
            db,
            center_id,
            "BATCH_APPROVE",
            actor_id=reviewed_by,
            details={"child_name": child_name, "count": count},
        )
    return count


def get_events_history(
    db: Session,
    center_id: uuid.UUID,
    status: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
) -> List[Event]:
    """Get approved/rejected events for the history view with pagination."""
    q = db.query(Event).filter(
        Event.center_id == center_id,
        Event.status != "PENDING",
    )
    if status:
        q = q.filter(Event.status == status)
    return q.order_by(Event.reviewed_at.desc()).limit(limit).offset(offset).all()


# ─── Teacher Lookup ───────────────────────────────────────────


def get_teacher_by_phone(db: Session, phone: str) -> Optional[Teacher]:
    """Resolve phone number → teacher record (for center_id lookup)."""
    return db.query(Teacher).filter(Teacher.phone == phone, Teacher.is_active).first()


# ─── Child Management ──────────────────────────────────────────


def get_children_by_center(db: Session, center_id: uuid.UUID) -> List[Child]:
    """Get all registered children for a center."""
    return db.query(Child).filter(Child.center_id == center_id).all()


def get_child_by_name(db: Session, center_id: uuid.UUID, name: str) -> Optional[Child]:
    """Basic fuzzy/exact name lookup (System of Record resolution)."""
    # V1: Exact match (case-insensitive)
    return db.query(Child).filter(Child.center_id == center_id, Child.name.ilike(name)).first()
