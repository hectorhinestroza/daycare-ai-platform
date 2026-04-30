"""Tests for batch event fan-out — 'all kids ate rice and beans'."""

import uuid

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.storage.database import Base
from backend.storage.events_handlers import (
    batch_approve_events,
    fan_out_batch_event,
)
from backend.storage.models import Center, Child, Event, Room, Teacher
from schemas.events import BaseEvent, EventStatus, EventType


# ─── Fixtures ────────────────────────────────────────────────


@pytest.fixture
def db():
    """Fresh SQLite in-memory DB per test."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


@pytest.fixture
def center_id(db):
    center = Center(id=uuid.uuid4(), name="Test Academy")
    db.add(center)
    db.commit()
    return center.id


@pytest.fixture
def room(db: Session, center_id):
    r = Room(id=uuid.uuid4(), center_id=center_id, name="Toddlers")
    db.add(r)
    db.commit()
    db.refresh(r)
    return r


@pytest.fixture
def teacher(db: Session, center_id, room):
    t = Teacher(
        id=uuid.uuid4(),
        center_id=center_id,
        name="Ms. Rivera",
        phone="+15550001111",
        room_id=room.id,
    )
    db.add(t)
    db.commit()
    db.refresh(t)
    return t


@pytest.fixture
def teacher_no_room(db: Session, center_id):
    t = Teacher(
        id=uuid.uuid4(),
        center_id=center_id,
        name="Mr. Garcia",
        phone="+15550002222",
        room_id=None,
    )
    db.add(t)
    db.commit()
    db.refresh(t)
    return t


@pytest.fixture
def active_children(db: Session, center_id, room):
    children = [
        Child(
            id=uuid.uuid4(),
            center_id=center_id,
            name=name,
            room_id=room.id,
            status="ACTIVE",
        )
        for name in ["Carlos", "Sofia", "Miguel"]
    ]
    for c in children:
        db.add(c)
    db.commit()
    return children


def _make_batch_base_event(center_id, event_type=EventType.FOOD):
    """Helper: build a BaseEvent with applies_to_all=True."""
    return BaseEvent(
        id=uuid.uuid4(),
        center_id=str(center_id),
        child_name="ALL",
        event_type=event_type,
        details="Had rice and beans for lunch",
        raw_transcript="all kids had rice and beans for lunch",
        review_tier="teacher",
        confidence_score=0.95,
        needs_director_review=False,
        needs_review=False,
        status=EventStatus.PENDING,
        applies_to_all=True,
    )


# ─── Tests ───────────────────────────────────────────────────


def test_fan_out_creates_one_event_per_child(db: Session, center_id, teacher, active_children):
    """Fan-out should create N events (one per active child in the room)."""
    base_event = _make_batch_base_event(center_id)
    created = fan_out_batch_event(db, center_id, teacher.id, base_event)

    assert len(created) == 3  # Carlos, Sofia, Miguel

    # All share the same batch_id
    batch_ids = {e.batch_id for e in created}
    assert len(batch_ids) == 1
    shared_batch_id = batch_ids.pop()
    assert shared_batch_id is not None

    # Each event has applies_to_all=True and a real child name
    names = {e.child_name for e in created}
    assert names == {"Carlos", "Sofia", "Miguel"}

    for ev in created:
        assert ev.applies_to_all is True
        assert ev.details == "Had rice and beans for lunch"
        assert ev.status == "PENDING"


def test_fan_out_unique_ids(db: Session, center_id, teacher, active_children):
    """Each fanned-out event must have a unique ID."""
    base_event = _make_batch_base_event(center_id)
    created = fan_out_batch_event(db, center_id, teacher.id, base_event)
    ids = [e.id for e in created]
    assert len(ids) == len(set(ids))  # all unique


def test_no_fanout_for_incidents(db: Session, center_id, teacher, active_children):
    """Incident events are NEVER fanned out — single director-queue event."""
    base_event = _make_batch_base_event(center_id, event_type=EventType.INCIDENT)
    created = fan_out_batch_event(db, center_id, teacher.id, base_event)

    # Should return exactly 1 event regardless of child count
    assert len(created) == 1
    assert created[0].batch_id is None  # no batch grouping for incidents


def test_no_fanout_for_medication(db: Session, center_id, teacher, active_children):
    """Medication events are NEVER fanned out."""
    base_event = _make_batch_base_event(center_id, event_type=EventType.MEDICATION)
    created = fan_out_batch_event(db, center_id, teacher.id, base_event)
    assert len(created) == 1


def test_no_fanout_when_teacher_has_no_room(db: Session, center_id, teacher_no_room, active_children):
    """If teacher has no room_id, fall back to a single director-queue event."""
    base_event = _make_batch_base_event(center_id)
    created = fan_out_batch_event(db, center_id, teacher_no_room.id, base_event)

    assert len(created) == 1
    assert created[0].review_tier == "director"
    assert created[0].needs_director_review is True


def test_batch_approve_by_batch_id(db: Session, center_id, teacher, active_children):
    """Director can approve all events in a batch group by batch_id."""
    base_event = _make_batch_base_event(center_id)
    created = fan_out_batch_event(db, center_id, teacher.id, base_event)
    batch_id = created[0].batch_id

    # All should be PENDING
    assert all(e.status == "PENDING" for e in created)

    count = batch_approve_events(db, center_id, batch_id=batch_id)
    assert count == 3

    # Verify in DB
    approved = (
        db.query(Event)
        .filter(Event.batch_id == batch_id)
        .all()
    )
    assert all(e.status == "APPROVED" for e in approved)


def test_batch_approve_by_child_name_unchanged(db: Session, center_id, teacher, active_children):
    """Original child_name batch approve still works (no regression)."""
    base_event = _make_batch_base_event(center_id)
    fan_out_batch_event(db, center_id, teacher.id, base_event)

    count = batch_approve_events(db, center_id, child_name="Carlos")
    assert count == 1  # Only Carlos's event approved
