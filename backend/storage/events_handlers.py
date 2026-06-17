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
from backend.storage.models import Child, Event, PendingPhoto, Photo, Room, Teacher

# Event types that must NEVER be fanned out automatically — director handles manually
_NEVER_FAN_OUT_TYPES = {"incident", "medication"}

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
    actor_id: Optional[uuid.UUID] = None,
    actor_type: str = "teacher",
) -> Event:
    """Create a DB event from a Pydantic BaseEvent (post-extraction).

    If the event meets the auto-approve threshold (teacher tier + high confidence),
    or is created by a director, it is written as APPROVED immediately and logged.
    """
    from backend.config import get_settings
    threshold = get_settings().auto_approve_confidence_threshold

    if actor_type == "director":
        auto_approved = True
    else:
        auto_approved = (
            threshold > 0
            and base_event.review_tier == "teacher"
            and base_event.confidence_score >= threshold
        )

    now = datetime.now(UTC)
    event = Event(
        id=base_event.id,
        center_id=uuid.UUID(base_event.center_id) if isinstance(base_event.center_id, str) else base_event.center_id,
        child_id=child_id,
        teacher_id=teacher_id if actor_type == "teacher" else None,
        child_name=base_event.child_name,
        event_type=base_event.event_type.value if hasattr(base_event.event_type, "value") else str(base_event.event_type),
        event_time=base_event.event_time,
        details=base_event.details,
        raw_transcript=base_event.raw_transcript,
        review_tier=base_event.review_tier,
        confidence_score=base_event.confidence_score,
        needs_director_review=base_event.needs_director_review,
        needs_review=base_event.needs_review,
        status="APPROVED" if auto_approved else base_event.status.value if hasattr(base_event.status, "value") else str(base_event.status),
        reviewed_by=actor_id if (auto_approved and actor_type == "director") else None,
        reviewed_at=now if auto_approved else None,
        applies_to_all=getattr(base_event, "applies_to_all", False),
        batch_id=getattr(base_event, "batch_id", None),
    )
    db.add(event)
    db.commit()
    db.refresh(event)

    if auto_approved:
        log_activity(
            db,
            event.center_id,
            "APPROVE" if actor_type == "director" else "AUTO_APPROVE",
            event_id=event.id,
            child_id=event.child_id,
            actor_id=actor_id,
            actor_type=actor_type,
            details={"child_name": event.child_name, "event_type": event.event_type},
        )

    return event


def fan_out_batch_event(
    db: Session,
    center_id: uuid.UUID,
    teacher_id: Optional[uuid.UUID],
    base_event,  # schemas.events.BaseEvent with applies_to_all=True
    environment: str = "development",
    room_id: Optional[uuid.UUID] = None,
    actor_id: Optional[uuid.UUID] = None,
    actor_type: str = "teacher",
) -> List[Event]:
    """Fan out a group event to one Event row per active child in the classroom.

    Rules:
    - Incidents and medication are NEVER fanned out — returned as-is for director.
    - If no room_id is passed or assigned, returns the event unchanged (director queue).
    - All fanned-out siblings share a batch_id UUID for grouped review in the UI.
    - Each fanned-out child passes through the consent gate. Children without
      active consent are skipped (the gate queues their event in
      pending_consent_queue) — they do NOT appear as siblings.
    """
    # Local import to avoid module-level circular dependency on consent_gate.
    from backend.utils.consent_gate import get_child_for_processing

    event_type_str = base_event.event_type.value if hasattr(base_event.event_type, "value") else str(base_event.event_type)

    # High-stakes types stay as a single director-queue event
    if event_type_str in _NEVER_FAN_OUT_TYPES:
        db_event = create_event_from_base(
            db, base_event,
            teacher_id=teacher_id if actor_type == "teacher" else None,
            actor_id=actor_id,
            actor_type=actor_type,
        )
        return [db_event]

    # Resolve room if not provided explicitly
    if not room_id:
        teacher = db.query(Teacher).filter(Teacher.id == teacher_id).first() if teacher_id else None
        room_id = teacher.primary_room_id if teacher else None

    if not room_id:
        # No room assigned — treat as low-confidence single event, director queue
        import logging
        logging.getLogger(__name__).warning(
            f"fan_out_batch_event: no room resolved, falling back to single event"
        )
        fallback = base_event.model_copy(update={"review_tier": "director", "needs_director_review": True, "confidence_score": 0.3})
        db_event = create_event_from_base(
            db, fallback,
            teacher_id=teacher_id if actor_type == "teacher" else None,
            actor_id=actor_id,
            actor_type=actor_type,
        )
        return [db_event]

    children = (
        db.query(Child)
        .filter(Child.center_id == center_id, Child.room_id == room_id, Child.status == "ACTIVE")
        .all()
    )

    if not children:
        # Room exists but no active children — return single event to director
        db_event = create_event_from_base(
            db, base_event,
            teacher_id=teacher_id if actor_type == "teacher" else None,
            actor_id=actor_id,
            actor_type=actor_type,
        )
        return [db_event]

    shared_batch_id = uuid.uuid4()
    created: List[Event] = []

    for child in children:
        # Per-child consent gate. Blocked children are queued in
        # pending_consent_queue; we just skip them in the fan-out.
        gated = get_child_for_processing(
            child_id=child.id,
            center_id=center_id,
            db=db,
            environment=environment,
            pipeline_stage="event_extraction_batch",
            raw_event_ref=base_event.model_dump_json(),
        )
        if gated is None:
            continue

        sibling = base_event.model_copy(update={
            "id": uuid.uuid4(),
            "child_name": child.name,
            "batch_id": shared_batch_id,
            "applies_to_all": True,
        })
        db_event = create_event_from_base(
            db, sibling,
            teacher_id=teacher_id if actor_type == "teacher" else None,
            child_id=child.id,
            actor_id=actor_id,
            actor_type=actor_type,
        )
        created.append(db_event)

    return created


def get_event(db: Session, event_id: uuid.UUID, center_id: uuid.UUID) -> Optional[Event]:
    """Get a single event, filtered by center_id."""
    return db.query(Event).filter(Event.id == event_id, Event.center_id == center_id).first()


def get_events_pending_teacher(
    db: Session,
    center_id: uuid.UUID,
    teacher_id: Optional[uuid.UUID] = None,
) -> List[Event]:
    """Get events awaiting teacher review, optionally scoped to one teacher."""
    q = db.query(Event).filter(
        Event.center_id == center_id,
        Event.status == "PENDING",
        Event.review_tier == "teacher",
    )
    if teacher_id:
        q = q.filter(Event.teacher_id == teacher_id)
    return q.order_by(Event.created_at.desc()).all()


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
    child_name: Optional[str] = None,
    reviewed_by: Optional[uuid.UUID] = None,
    batch_id: Optional[uuid.UUID] = None,
) -> int:
    """Approve all pending events for a child OR a batch group.

    Pass child_name to approve all pending events for that child (teacher UI).
    Pass batch_id to approve all events in a fan-out batch group (director use case for
    incidents/medication that were not auto-fanned-out but are reviewed together).

    Tier safety: the child_name path approves teacher-tier events only. Incidents
    and medication (review_tier="director") are reserved for the director queue
    and must not be swept up by a teacher's "approve all for child" action.
    """
    now = datetime.now(UTC)
    q = db.query(Event).filter(Event.center_id == center_id, Event.status == "PENDING")

    if batch_id:
        q = q.filter(Event.batch_id == batch_id)
    elif child_name:
        q = q.filter(Event.child_name == child_name, Event.review_tier == "teacher")
    else:
        raise ValueError("batch_approve_events requires either child_name or batch_id")

    count = q.update(
        {
            Event.status: "APPROVED",
            Event.reviewed_by: reviewed_by,
            Event.reviewed_at: now,
        },
        synchronize_session="fetch",
    )
    db.commit()
    if count > 0:
        child = None
        if child_name:
            child = get_child_by_name(db, center_id, child_name)
        log_activity(
            db,
            center_id,
            "BATCH_APPROVE",
            child_id=child.id if child else None,
            actor_id=reviewed_by,
            # Match the single-event APPROVE shape so the activity log UI can
            # read details.child_name uniformly. For batch_id (director's
            # fan-out approval) there is no single child, so use a label
            # the UI can render gracefully.
            details={
                "child_name": child_name if child_name else "the batch",
                "count": count,
                "batch_id": str(batch_id) if batch_id else None,
            },
        )
    return count


def get_events_history(
    db: Session,
    center_id: uuid.UUID,
    status: Optional[str] = None,
    teacher_id: Optional[uuid.UUID] = None,
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
    if teacher_id:
        q = q.filter(Event.teacher_id == teacher_id)
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

    Four-pass strategy:
      1. Exact case-insensitive match ("Annie Johnson" → "Annie Johnson")
      2. First-name / prefix match ("Annie" → "Annie Johnson")
      3. Contains match as last resort (e.g. middle name used)
      4. Double-Metaphone phonetic match — catches Whisper mistranscriptions
         like "Klara" → "Clara", "Em-ee" → "Emi", "Joey" → "Joii".
      5. Ambiguity guard: if a pass finds multiple kids, return None
         (better to flag for director review than silently pick the wrong one).

    TODO(pilot v2): when the director records a pronunciation clip at
    enrollment, store it on the child row and add a Pass 5 that compares
    audio embeddings as the strongest signal.
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
    if len(prefix_matches) == 1:
        return prefix_matches[0]

    # Pass 3: contains match (e.g. middle name used)
    if not prefix_matches:
        contains_matches = base_q.filter(Child.name.ilike(f"% {name} %")).all()
        if len(contains_matches) == 1:
            return contains_matches[0]

    # Pass 4: phonetic match — Double Metaphone produces two codes per name.
    # Match if any code from the input overlaps any code from a child's name
    # (handles homophones across spellings). Iterates the full roster, fine for
    # pilot scale; would need a stored metaphone column at 1000s of kids.
    try:
        from metaphone import doublemetaphone

        def _codes(s: str) -> set[str]:
            return {c for c in doublemetaphone(s) if c}

        input_codes = _codes(name)
        # Also try the first token, so "Annie Johnson" said as "Annie" still matches
        first_token = name.split()[0] if name else ""
        if first_token and first_token != name:
            input_codes |= _codes(first_token)

        if input_codes:
            all_kids = base_q.all()
            phonetic = []
            for kid in all_kids:
                kid_codes = _codes(kid.name)
                kid_first = kid.name.split()[0] if kid.name else ""
                if kid_first and kid_first != kid.name:
                    kid_codes |= _codes(kid_first)
                if input_codes & kid_codes:
                    phonetic.append(kid)
            if len(phonetic) == 1:
                return phonetic[0]
    except ImportError:
        # metaphone package missing in this environment — silently skip
        # the phonetic pass rather than break the resolver.
        pass

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


def fan_out_photo(
    db: Session,
    center_id: uuid.UUID,
    child_ids: List[uuid.UUID],
    s3_key: str,
    caption: Optional[str] = None,
    content_type: str = "image/jpeg",
    event_id: Optional[uuid.UUID] = None,
) -> List[Photo]:
    """Create one Photo row per child, all pointing at the same S3 object.

    Used when a teacher tags multiple children in a single photo. The S3
    object is uploaded once; we duplicate only the cheap row metadata so
    each child's gallery query (`get_photos_for_child`) keeps working
    unchanged.
    """
    created: List[Photo] = []
    for child_id in child_ids:
        photo = Photo(
            center_id=center_id,
            child_id=child_id,
            s3_key=s3_key,
            caption=caption,
            content_type=content_type,
            event_id=event_id,
        )
        db.add(photo)
        created.append(photo)
    db.commit()
    for p in created:
        db.refresh(p)
    return created


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
