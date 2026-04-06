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
from datetime import datetime
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.storage.database import get_db
from backend.storage.events_handlers import (
    approve_event,
    batch_approve_events,
    get_event,
    get_events_history,
    get_events_pending_director,
    get_events_pending_teacher,
    reject_event,
    update_event,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/events", tags=["events"])


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
    child_name: str


class BatchApproveResponse(BaseModel):
    message: str
    approved_count: int


# ─── Endpoints (order matters — specific paths before catch-all) ──


@router.get("/pending/teacher/{center_id}", response_model=List[EventOut])
def list_teacher_queue(center_id: UUID, db: Session = Depends(get_db)):
    """Get all pending events for teacher review."""
    events = get_events_pending_teacher(db, center_id)
    return events


@router.get("/pending/director/{center_id}", response_model=List[EventOut])
def list_director_queue(center_id: UUID, db: Session = Depends(get_db)):
    """Get all flagged events for director review."""
    events = get_events_pending_director(db, center_id)
    return events


@router.get("/history/{center_id}", response_model=List[EventOut])
def list_event_history(
    center_id: UUID,
    status: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
):
    """Get approved/rejected events for the history view."""
    events = get_events_history(db, center_id, status=status, limit=limit, offset=offset)
    return events


@router.post("/{center_id}/batch-approve", response_model=BatchApproveResponse)
def batch_approve_endpoint(
    center_id: UUID,
    body: BatchApproveRequest,
    db: Session = Depends(get_db),
):
    """Approve all pending events for a child at once."""
    count = batch_approve_events(db, center_id, body.child_name)
    logger.info(f"Batch approved {count} events for {body.child_name} in center {center_id}")
    return BatchApproveResponse(
        message=f"Approved {count} events for {body.child_name}",
        approved_count=count,
    )


# ─── Catch-all routes (must come after specific paths) ────────


@router.get("/{center_id}/{event_id}", response_model=EventOut)
def get_event_detail(center_id: UUID, event_id: UUID, db: Session = Depends(get_db)):
    """Get a single event by ID, scoped to center."""
    event = get_event(db, event_id, center_id)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    return event


@router.post("/{center_id}/{event_id}/approve", response_model=ActionResponse)
def approve_event_endpoint(center_id: UUID, event_id: UUID, db: Session = Depends(get_db)):
    """Approve a pending event."""
    event = approve_event(db, event_id, center_id)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    logger.info(f"Event {event_id} approved for center {center_id}")
    return ActionResponse(message="Event approved", event=EventOut.model_validate(event))


@router.post("/{center_id}/{event_id}/reject", response_model=ActionResponse)
def reject_event_endpoint(center_id: UUID, event_id: UUID, db: Session = Depends(get_db)):
    """Reject a pending event."""
    event = reject_event(db, event_id, center_id)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    logger.info(f"Event {event_id} rejected for center {center_id}")
    return ActionResponse(message="Event rejected", event=EventOut.model_validate(event))


@router.patch("/{center_id}/{event_id}", response_model=ActionResponse)
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
