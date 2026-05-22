"""REST API for event review — teacher and director queues.

Endpoints:
    GET  /api/events/pending/teacher/{center_id}   — teacher queue
    GET  /api/events/pending/director/{center_id}   — director queue (flagged)
    GET  /api/events/history/{center_id}            — approved/rejected history
    POST /api/events/{center_id}/batch-approve      — batch approve by child
    GET  /api/events/{center_id}/{event_id}         — single event detail
    POST /api/events/{center_id}/{event_id}/approve — approve event
    POST /api/events/{center_id}/{event_id}/reject  — reject event
    PATCH /api/events/{center_id}/{event_id}        — inline edit
"""
import logging
import time
from datetime import datetime, timezone
from typing import List, Optional
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.services.narrative import generate_narrative
from backend.storage.database import SessionLocal, get_db
from backend.utils.safe_logging import safe_log
from backend.utils.auth_tokens import TokenPayload
from backend.utils.pilot_auth import require_parent_owns_child, require_role
from backend.storage.events_handlers import (
    approve_event,
    batch_approve_events,
    get_approved_events_for_child,
    get_child_by_name,
    get_event,
    get_events_history,
    get_events_pending_director,
    get_events_pending_teacher,
    reject_event,
    update_event,
)
from backend.storage.models import Center as CenterModel, Event
from backend.storage.narrative_handlers import get_narrative, upsert_narrative

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/events", tags=["events"])


# ─── Background narrative refresh ────────────────────────────

# Debounce: tracks the last time a refresh was triggered per (center_id, child_id, date).
# Prevents N sequential single-event approvals from firing N GPT-4o calls.
# Safe because asyncio is single-threaded — the check+set below has no await between
# them, so it's atomic within the event loop.
_narrative_refresh_last_triggered: dict[tuple, datetime] = {}
_NARRATIVE_REFRESH_COOLDOWN_SECONDS = 120  # 2 minutes


async def _refresh_narrative_if_exists(center_id: UUID, child_id: UUID, event_date) -> None:
    """Regenerate the daily narrative for a child if one already exists for that date.

    Runs as a background task after event approval so the parent sees an updated
    summary without the director needing to manually trigger EOD reports.
    Only regenerates — never creates a narrative that didn't exist yet.
    Debounced: subsequent calls within 2 minutes for the same child+date are skipped.

    **Time guard**: Only regenerates *after* the center's local 5 PM (EOD hour).
    Before 5 PM, the narrative should not be refreshed on every approval — the
    scheduled 5 PM run handles creation, and mid-day approvals should not trigger
    GPT-4o calls or show premature narratives to parents.

    Uses the center's local timezone to determine the target date — late-night events
    (e.g. 10:50 PM ET) have event_time in UTC on the *next* UTC calendar day, but the
    narrative lives on the *local* calendar date.
    """

    now = datetime.now(timezone.utc)

    db = SessionLocal()
    try:
        # Resolve center's local date so late-night events (e.g. 10:50 PM ET = next UTC day)
        # still match the narrative stored for the local calendar date.
        center = db.query(CenterModel).filter(CenterModel.id == center_id).first()
        tz_str = (center.timezone if center else None) or "America/New_York"
        try:
            local_now = datetime.now(ZoneInfo(tz_str))
            target_date = local_now.date()
        except (ZoneInfoNotFoundError, Exception):
            local_now = now
            target_date = event_date

        # ── Time guard: skip regeneration before EOD (5 PM local) ──
        # Mid-day approvals should NOT regenerate narratives. The scheduler handles
        # creation at 5 PM, and only post-EOD approvals should update the narrative.
        _EOD_HOUR = 17
        if local_now.hour < _EOD_HOUR:
            logger.debug(
                f"Narrative refresh skipped — only {local_now.hour}:00 local, "
                f"before EOD ({_EOD_HOUR}:00) for center {center_id}"
            )
            return

        key = (str(center_id), str(child_id), str(target_date))

        # Debounce check — atomic: no await between the read and the write
        last_triggered = _narrative_refresh_last_triggered.get(key)
        if last_triggered and (now - last_triggered).total_seconds() < _NARRATIVE_REFRESH_COOLDOWN_SECONDS:
            logger.debug(f"Narrative refresh debounced for child {child_id} on {target_date}")
            return
        _narrative_refresh_last_triggered[key] = now

        # Evict entries older than 10 minutes to prevent unbounded memory growth
        cutoff = now.timestamp() - 600
        stale = [k for k, v in _narrative_refresh_last_triggered.items() if v.timestamp() < cutoff]
        for k in stale:
            del _narrative_refresh_last_triggered[k]

        existing = get_narrative(db, center_id, child_id, target_date)
        if not existing or existing.admin_override:
            return  # Nothing to refresh

        safe_log(
            logger, "info", "narrative_refresh.triggered",
            child_id=str(child_id),
            target_date=str(target_date),
            trigger="event_approval",
        )

        refresh_start = time.monotonic()
        result = await generate_narrative(db, center_id, child_id, target_date)
        upsert_narrative(
            db,
            center_id=center_id,
            child_id=child_id,
            target_date=target_date,
            **{k: result[k] for k in ("headline", "body", "tone", "photo_captions")},
        )
        safe_log(
            logger, "info", "narrative_refresh.completed",
            child_id=str(child_id),
            target_date=str(target_date),
            duration_ms=int((time.monotonic() - refresh_start) * 1000),
        )
    except Exception as e:
        safe_log(
            logger, "error", "narrative_refresh.failed",
            child_id=str(child_id),
            target_date=str(event_date),
            error_type=type(e).__name__,
        )
    finally:
        db.close()



# ─── Response Schemas ─────────────────────────────────────────


class EventOut(BaseModel):
    """Event response schema for the review console."""

    id: UUID
    center_id: UUID
    child_id: Optional[UUID] = None
    teacher_id: Optional[UUID] = None
    child_name: str
    event_type: str
    event_time: Optional[datetime] = None
    details: Optional[str] = None
    raw_transcript: str
    review_tier: str
    confidence_score: float
    needs_director_review: bool
    needs_review: bool
    status: str
    reviewed_by: Optional[UUID] = None
    reviewed_at: Optional[datetime] = None
    created_at: Optional[datetime] = None
    applies_to_all: bool = False
    batch_id: Optional[UUID] = None
    teacher_name: Optional[str] = None

    model_config = {"from_attributes": True}


class EventUpdate(BaseModel):
    """Partial update schema for inline editing."""

    child_name: Optional[str] = None
    details: Optional[str] = None
    event_type: Optional[str] = None
    event_time: Optional[datetime] = None


class ActionResponse(BaseModel):
    message: str
    event: EventOut


class BatchApproveRequest(BaseModel):
    child_name: Optional[str] = None  # approve all pending for this child
    batch_id: Optional[UUID] = None   # approve all events in a fan-out group


class BatchApproveResponse(BaseModel):
    message: str
    approved_count: int


# ─── Endpoints (order matters — specific paths before catch-all) ──


@router.get(
    "/pending/teacher/{center_id}",
    response_model=List[EventOut],
    dependencies=[Depends(require_role("staff"))],
)
def list_teacher_queue(center_id: UUID, db: Session = Depends(get_db)):
    """Get all pending events for teacher review."""
    events = get_events_pending_teacher(db, center_id)
    return events


@router.get(
    "/pending/director/{center_id}",
    response_model=List[EventOut],
    dependencies=[Depends(require_role("staff"))],
)
def list_director_queue(center_id: UUID, db: Session = Depends(get_db)):
    """Get all flagged events for director review."""
    events = get_events_pending_director(db, center_id)
    return events


@router.get(
    "/history/{center_id}",
    response_model=List[EventOut],
    dependencies=[Depends(require_role("staff"))],
)
def list_event_history(
    center_id: UUID,
    status: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
):
    """Get approved/rejected events for the history view, with teacher attribution."""
    events = get_events_history(db, center_id, status=status, limit=limit, offset=offset)
    return [
        EventOut.model_validate({
            **{c.key: getattr(e, c.key) for c in e.__table__.columns},
            "applies_to_all": e.applies_to_all,
            "teacher_name": e.teacher.name if e.teacher else None,
        })
        for e in events
    ]


@router.post(
    "/{center_id}/batch-approve",
    response_model=BatchApproveResponse,
    dependencies=[Depends(require_role("staff"))],
)
def batch_approve_endpoint(
    center_id: UUID,
    body: BatchApproveRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """Approve all pending events for a child OR all events in a batch fan-out group.

    - Pass child_name: approves every pending event for that child (teacher UI).
    - Pass batch_id: approves every event in a fan-out batch group (director UI —
      used for incidents/medication that were not auto-fanned-out).
    """
    if not body.child_name and not body.batch_id:
        raise HTTPException(status_code=422, detail="Provide either child_name or batch_id")

    # Derive reviewed_by from the first matching pending event (interim until auth is wired)
    q = db.query(Event).filter(Event.center_id == center_id, Event.status == "PENDING")
    if body.batch_id:
        q = q.filter(Event.batch_id == body.batch_id)
    else:
        q = q.filter(Event.child_name == body.child_name)
    first_pending = q.first()
    reviewed_by = first_pending.teacher_id if first_pending else None

    count = batch_approve_events(
        db, center_id,
        child_name=body.child_name,
        batch_id=body.batch_id,
        reviewed_by=reviewed_by,
    )

    label = "batch group" if body.batch_id else body.child_name
    # Note: child_name in label is fine for the response message, but the
    # structured log records IDs only.
    safe_log(
        logger, "info", "event.batch_approved",
        center_id=str(center_id),
        count=count,
        batch_id=str(body.batch_id) if body.batch_id else None,
    )

    # Trigger narrative refresh for affected children
    if count > 0:
        today = datetime.now(timezone.utc).date()
        if body.child_name:
            child = get_child_by_name(db, center_id, body.child_name)
            if child:
                background_tasks.add_task(_refresh_narrative_if_exists, center_id, child.id, today)
        elif body.batch_id:
            # Fan-out: refresh narrative for all distinct children in the batch
            batch_events = (
                db.query(Event)
                .filter(Event.center_id == center_id, Event.batch_id == body.batch_id)
                .all()
            )
            seen_children = set()
            for ev in batch_events:
                if ev.child_id and ev.child_id not in seen_children:
                    seen_children.add(ev.child_id)
                    background_tasks.add_task(_refresh_narrative_if_exists, center_id, ev.child_id, today)

    return BatchApproveResponse(
        message=f"Approved {count} events for {label}",
        approved_count=count,
    )


@router.get("/feed/{center_id}/{child_id}", response_model=List[EventOut])
def parent_feed(
    center_id: UUID,
    child_id: UUID,
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
    payload: TokenPayload = Depends(require_role("any")),
):
    """Approved events for a specific child.

    Accessible by:
      - The parent of that child (token must include child_id in child_ids)
      - Any staff (teacher or director) at the center
    """
    require_parent_owns_child(child_id, payload)
    events = get_approved_events_for_child(db, center_id, child_id, limit=limit, offset=offset)
    return events


# ─── Catch-all routes (must come after specific paths) ────────


@router.get(
    "/{center_id}/{event_id}",
    response_model=EventOut,
    dependencies=[Depends(require_role("staff"))],
)
def get_event_detail(center_id: UUID, event_id: UUID, db: Session = Depends(get_db)):
    """Get a single event by ID, scoped to center."""
    event = get_event(db, event_id, center_id)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    return event


@router.post(
    "/{center_id}/{event_id}/approve",
    response_model=ActionResponse,
)
def approve_event_endpoint(
    center_id: UUID,
    event_id: UUID,
    background_tasks: BackgroundTasks,
    payload: TokenPayload = Depends(require_role("staff")),
    db: Session = Depends(get_db),
):
    """Approve a pending event.

    Tier guard: a teacher may not approve a director-tier event (incidents,
    medication, low-confidence flags). The teacher queue UI already hides
    these, but the endpoint enforces the same rule so a hand-crafted request
    can't bypass it.
    """
    existing = get_event(db, event_id, center_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Event not found")
    if payload.role == "teacher" and existing.review_tier == "director":
        raise HTTPException(
            status_code=403,
            detail="Director review required for this event",
        )

    event = approve_event(db, event_id, center_id)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    safe_log(
        logger, "info", "event.approved",
        event_id=str(event_id),
        center_id=str(center_id),
        event_type=event.event_type,
        confidence_score=event.confidence_score,
    )

    if event.child_id:
        event_date = (event.event_time or event.created_at).date()
        background_tasks.add_task(_refresh_narrative_if_exists, center_id, event.child_id, event_date)

    return ActionResponse(message="Event approved", event=EventOut.model_validate(event))


@router.post(
    "/{center_id}/{event_id}/reject",
    response_model=ActionResponse,
    dependencies=[Depends(require_role("staff"))],
)
def reject_event_endpoint(center_id: UUID, event_id: UUID, db: Session = Depends(get_db)):
    """Reject a pending event."""
    event = reject_event(db, event_id, center_id)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    safe_log(
        logger, "info", "event.rejected",
        event_id=str(event_id),
        center_id=str(center_id),
        event_type=event.event_type,
    )
    return ActionResponse(message="Event rejected", event=EventOut.model_validate(event))


@router.patch(
    "/{center_id}/{event_id}",
    response_model=ActionResponse,
    dependencies=[Depends(require_role("staff"))],
)
def edit_event_endpoint(
    center_id: UUID,
    event_id: UUID,
    body: EventUpdate,
    db: Session = Depends(get_db),
):
    """Inline edit an event (partial update)."""
    updates = body.model_dump(exclude_unset=True)
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    event = update_event(db, event_id, center_id, updates)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    logger.info(f"Event {event_id} edited: {list(updates.keys())}")
    return ActionResponse(message="Event updated", event=EventOut.model_validate(event))
