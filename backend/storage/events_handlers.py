"""CRUD operations for events and related entities.

All queries filter by center_id for multi-tenant isolation.
This is the data access layer — never bypass it with raw SQL.
"""
import uuid
from datetime import UTC, datetime
from typing import List, Optional

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from backend.storage.activity_handlers import log_activity
from backend.storage.models import Child, Event, PendingPhoto, Photo, Teacher

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
    """Approve an event (teacher or director).

    Also resolves child_id if not already set (best-effort name match).
    """
    event = get_event(db, event_id, center_id)
    if not event:
        return None
    event.status = "APPROVED"
    event.reviewed_by = reviewed_by
    event.reviewed_at = datetime.now(UTC)

    # Resolve child_id at approval time if still unset
    if not event.child_id and event.child_name:
        child = get_child_by_name(db, center_id, event.child_name)
        if child:
            event.child_id = child.id

    db.commit()
    db.refresh(event)
    log_activity(
        db,
        center_id,
        "APPROVE",
        event_id=event_id,
        child_id=event.child_id,
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
        child_id=event.child_id,
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
        child_id=event.child_id,
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
    """Get approved events for a specific child (parent feed).

    Matches on child_id OR child_name (case-insensitive) to handle events
    where child_id was not resolved at extraction time.
    """

    child = db.query(Child).filter(Child.id == child_id, Child.center_id == center_id).first()
    if not child:
        return []

    return (
        db.query(Event)
        .filter(
            Event.center_id == center_id,
            Event.status == "APPROVED",
            or_(
                Event.child_id == child_id,
                func.lower(Event.child_name) == func.lower(child.name),
            ),
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
        child = get_child_by_name(db, center_id, child_name)
        log_activity(
            db,
            center_id,
            "BATCH_APPROVE",
            child_id=child.id if child else None,
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
    """Fuzzy name lookup for child resolution.

    Three-pass strategy:
      1. Exact case-insensitive match ("Annie Johnson" → "Annie Johnson")
      2. First-name / prefix match ("Annie" → "Annie Johnson")
      3. Ambiguity guard: if multiple children match pass 2, return None
         (better to flag for director review than silently pick the wrong child)
    """
    if not name or not name.strip():
        return None

    name = name.strip()
    base_q = db.query(Child).filter(Child.center_id == center_id)

    # Pass 1: exact case-insensitive
    exact = base_q.filter(Child.name.ilike(name)).first()
    if exact:
        return exact

    # Pass 2: prefix match — name appears at the start of the full name
    prefix_matches = base_q.filter(Child.name.ilike(f"{name} %")).all()

    # Guard against ambiguity — two "Annies" in the same center
    if len(prefix_matches) == 1:
        return prefix_matches[0]

    # Pass 3: contains match as last resort (e.g. middle name used)
    if not prefix_matches:
        contains_matches = base_q.filter(Child.name.ilike(f"% {name} %")).all()
        if len(contains_matches) == 1:
            return contains_matches[0]

    # Ambiguous or no match — return None, let event go to director review
    return None


# ─── Photo CRUD ──────────────────────────────────────────────


def create_photo(
    db: Session,
    center_id: uuid.UUID,
    child_id: uuid.UUID,
    s3_key: str,
    caption: Optional[str] = None,
    content_type: str = "image/jpeg",
    event_id: Optional[uuid.UUID] = None,
) -> Photo:
    """Create a finalized photo record (EXIF-stripped, consent-gated)."""
    photo = Photo(
        center_id=center_id,
        child_id=child_id,
        s3_key=s3_key,
        caption=caption,
        content_type=content_type,
        event_id=event_id,
    )
    db.add(photo)
    db.commit()
    db.refresh(photo)
    return photo


def get_photos_for_child(
    db: Session,
    center_id: uuid.UUID,
    child_id: uuid.UUID,
    limit: int = 50,
) -> List[Photo]:
    """Return non-deleted photos for a child, newest first."""
    return (
        db.query(Photo)
        .filter(
            Photo.center_id == center_id,
            Photo.child_id == child_id,
            Photo.deleted_at.is_(None),
        )
        .order_by(Photo.created_at.desc())
        .limit(limit)
        .all()
    )


# ─── Pending Photo CRUD ─────────────────────────────────────


def create_pending_photo(
    db: Session,
    center_id: uuid.UUID,
    teacher_id: uuid.UUID,
    s3_temp_key: str,
    caption: Optional[str] = None,
    content_type: str = "image/jpeg",
    expires_at: Optional[datetime] = None,
) -> PendingPhoto:
    """Create a pending photo record awaiting child association."""
    pending = PendingPhoto(
        center_id=center_id,
        teacher_id=teacher_id,
        s3_temp_key=s3_temp_key,
        caption=caption,
        content_type=content_type,
        expires_at=expires_at,
    )
    db.add(pending)
    db.commit()
    db.refresh(pending)
    return pending


def get_pending_photos_by_teacher(
    db: Session, teacher_id: uuid.UUID
) -> List[PendingPhoto]:
    """Get all non-expired pending photos for a teacher."""
    return (
        db.query(PendingPhoto)
        .filter(
            PendingPhoto.teacher_id == teacher_id,
            PendingPhoto.expires_at > datetime.now(UTC),
        )
        .order_by(PendingPhoto.created_at)
        .all()
    )


def delete_pending_photo(db: Session, pending_photo_id: uuid.UUID) -> None:
    """Delete a pending photo record."""
    db.query(PendingPhoto).filter(PendingPhoto.id == pending_photo_id).delete()
    db.commit()


def get_expired_pending_photos(db: Session) -> List[PendingPhoto]:
    """Get all pending photos past their expiry time."""
    return (
        db.query(PendingPhoto)
        .filter(PendingPhoto.expires_at <= datetime.now(UTC))
        .all()
    )
