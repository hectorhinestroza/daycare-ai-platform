"""CRUD operations for events and related entities.

All queries filter by center_id for multi-tenant isolation.
This is the data access layer — never bypass it with raw SQL.
"""

import uuid
from datetime import datetime, UTC
from typing import List, Optional
from sqlalchemy.orm import Session
from backend.storage.models import Event, Teacher, Child, Center


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
    return (
        db.query(Event)
        .filter(Event.id == event_id, Event.center_id == center_id)
        .first()
    )


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
            Event.needs_director_review == True,
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


# ─── Teacher Lookup ───────────────────────────────────────────

def get_teacher_by_phone(db: Session, phone: str) -> Optional[Teacher]:
    """Resolve phone number → teacher record (for center_id lookup)."""
    return (
        db.query(Teacher)
        .filter(Teacher.phone == phone, Teacher.is_active == True)
        .first()
    )


# ─── Child Management ──────────────────────────────────────────

def get_children_by_center(db: Session, center_id: uuid.UUID) -> List[Child]:
    """Get all registered children for a center."""
    return db.query(Child).filter(Child.center_id == center_id).all()


def get_child_by_name(db: Session, center_id: uuid.UUID, name: str) -> Optional[Child]:
    """Basic fuzzy/exact name lookup (System of Record resolution)."""
    # V1: Exact match (case-insensitive)
    return (
        db.query(Child)
        .filter(
            Child.center_id == center_id,
            Child.name.ilike(name)
        )
        .first()
    )
