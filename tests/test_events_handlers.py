"""Tests for CRUD operations and multi-tenant isolation.

Uses SQLite in-memory database for fast tests without Postgres dependency.
"""

import uuid

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.storage.database import Base
from backend.storage.events_handlers import (
    approve_event,
    create_event,
    create_event_from_base,
    get_event,
    get_events_by_child,
    get_events_pending_director,
    get_events_pending_teacher,
    get_teacher_by_phone,
    reject_event,
)
from backend.storage.models import Center, Room, Teacher
from schemas.events import BaseEvent, EventType

# ─── Fixtures ─────────────────────────────────────────────────

@pytest.fixture
def db():
    """Create a fresh SQLite in-memory DB for each test."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


@pytest.fixture
def center_a(db):
    """Create Center A for multi-tenant tests."""
    center = Center(id=uuid.uuid4(), name="Sunshine Academy")
    db.add(center)
    db.commit()
    return center


@pytest.fixture
def center_b(db):
    """Create Center B for multi-tenant tests."""
    center = Center(id=uuid.uuid4(), name="Rainbow Kids")
    db.add(center)
    db.commit()
    return center


@pytest.fixture
def teacher_a(db, center_a):
    """Create a teacher for Center A."""
    room = Room(id=uuid.uuid4(), center_id=center_a.id, name="Butterflies")
    db.add(room)
    db.commit()
    teacher = Teacher(
        id=uuid.uuid4(),
        center_id=center_a.id,
        name="Ms. Rodriguez",
        phone="+1234567890",
        room_id=room.id,
    )
    db.add(teacher)
    db.commit()
    return teacher


# ─── Event CRUD Tests ─────────────────────────────────────────

class TestEventCRUD:
    def test_create_event(self, db, center_a):
        event = create_event(
            db=db,
            center_id=center_a.id,
            child_name="Jason",
            event_type="food",
            raw_transcript="Jason ate mac and cheese",
            review_tier="teacher",
            confidence_score=0.95,
            details="Ate mac and cheese for lunch",
        )
        assert event.id is not None
        assert event.child_name == "Jason"
        assert event.event_type == "food"
        assert event.status == "PENDING"
        assert event.center_id == center_a.id

    def test_get_event(self, db, center_a):
        event = create_event(
            db=db, center_id=center_a.id,
            child_name="Emma", event_type="nap",
            raw_transcript="Emma napped",
        )
        found = get_event(db, event.id, center_a.id)
        assert found is not None
        assert found.child_name == "Emma"

    def test_approve_event(self, db, center_a):
        event = create_event(
            db=db, center_id=center_a.id,
            child_name="Jason", event_type="food",
            raw_transcript="Jason ate lunch",
        )
        approved = approve_event(db, event.id, center_a.id)
        assert approved.status == "APPROVED"
        assert approved.reviewed_at is not None

    def test_reject_event(self, db, center_a):
        event = create_event(
            db=db, center_id=center_a.id,
            child_name="Jason", event_type="food",
            raw_transcript="Jason ate lunch",
        )
        rejected = reject_event(db, event.id, center_a.id)
        assert rejected.status == "REJECTED"

    def test_get_events_by_child(self, db, center_a):
        create_event(db=db, center_id=center_a.id, child_name="Jason",
                     event_type="food", raw_transcript="food")
        create_event(db=db, center_id=center_a.id, child_name="Jason",
                     event_type="nap", raw_transcript="nap")
        create_event(db=db, center_id=center_a.id, child_name="Emma",
                     event_type="potty", raw_transcript="potty")

        jason_events = get_events_by_child(db, center_a.id, "Jason")
        assert len(jason_events) == 2

        emma_events = get_events_by_child(db, center_a.id, "Emma")
        assert len(emma_events) == 1


# ─── Review Queue Tests ──────────────────────────────────────

class TestReviewQueues:
    def test_teacher_queue(self, db, center_a):
        """Teacher queue shows events with review_tier=teacher and status=PENDING."""
        create_event(db=db, center_id=center_a.id, child_name="Jason",
                     event_type="food", raw_transcript="food",
                     review_tier="teacher")
        create_event(db=db, center_id=center_a.id, child_name="Emma",
                     event_type="incident", raw_transcript="incident",
                     review_tier="director", needs_director_review=True)

        teacher_events = get_events_pending_teacher(db, center_a.id)
        assert len(teacher_events) == 1
        assert teacher_events[0].child_name == "Jason"

    def test_director_queue(self, db, center_a):
        """Director queue shows only flagged events."""
        create_event(db=db, center_id=center_a.id, child_name="Jason",
                     event_type="food", raw_transcript="food",
                     review_tier="teacher")
        create_event(db=db, center_id=center_a.id, child_name="Emma",
                     event_type="incident", raw_transcript="incident",
                     review_tier="director", needs_director_review=True)

        director_events = get_events_pending_director(db, center_a.id)
        assert len(director_events) == 1
        assert director_events[0].child_name == "Emma"

    def test_approved_events_leave_queue(self, db, center_a):
        """Once approved, events no longer appear in pending queues."""
        event = create_event(db=db, center_id=center_a.id, child_name="Jason",
                             event_type="food", raw_transcript="food",
                             review_tier="teacher")
        approve_event(db, event.id, center_a.id)

        teacher_events = get_events_pending_teacher(db, center_a.id)
        assert len(teacher_events) == 0


# ─── Multi-Tenant Isolation Tests ─────────────────────────────

class TestMultiTenantIsolation:
    def test_center_a_cannot_see_center_b_events(self, db, center_a, center_b):
        """Center A's events are invisible to Center B queries."""
        create_event(db=db, center_id=center_a.id, child_name="Jason",
                     event_type="food", raw_transcript="food")
        create_event(db=db, center_id=center_b.id, child_name="Emma",
                     event_type="nap", raw_transcript="nap")

        a_events = get_events_by_child(db, center_a.id, "Jason")
        assert len(a_events) == 1

        # Center B trying to see Jason → should find nothing
        cross_events = get_events_by_child(db, center_b.id, "Jason")
        assert len(cross_events) == 0

    def test_cannot_approve_event_from_another_center(self, db, center_a, center_b):
        """Center B cannot approve Center A's events."""
        event = create_event(db=db, center_id=center_a.id, child_name="Jason",
                             event_type="food", raw_transcript="food")

        # Center B tries to approve Center A's event
        result = approve_event(db, event.id, center_b.id)
        assert result is None  # not found

        # Event should still be PENDING
        original = get_event(db, event.id, center_a.id)
        assert original.status == "PENDING"

    def test_teacher_queue_isolated(self, db, center_a, center_b):
        """Teacher queues are center-scoped."""
        create_event(db=db, center_id=center_a.id, child_name="Jason",
                     event_type="food", raw_transcript="food",
                     review_tier="teacher")
        create_event(db=db, center_id=center_b.id, child_name="Emma",
                     event_type="nap", raw_transcript="nap",
                     review_tier="teacher")

        a_queue = get_events_pending_teacher(db, center_a.id)
        b_queue = get_events_pending_teacher(db, center_b.id)

        assert len(a_queue) == 1
        assert a_queue[0].child_name == "Jason"
        assert len(b_queue) == 1
        assert b_queue[0].child_name == "Emma"


# ─── Teacher Lookup Tests ─────────────────────────────────────

class TestTeacherLookup:
    def test_find_teacher_by_phone(self, db, teacher_a):
        teacher = get_teacher_by_phone(db, "+1234567890")
        assert teacher is not None
        assert teacher.name == "Ms. Rodriguez"

    def test_teacher_not_found(self, db):
        teacher = get_teacher_by_phone(db, "+9999999999")
        assert teacher is None


# ─── create_event_from_base Tests ─────────────────────────────

class TestCreateFromBase:
    def test_create_from_pydantic_model(self, db, center_a):
        """Verify Pydantic BaseEvent → SQLAlchemy Event conversion."""
        base = BaseEvent(
            id=uuid.uuid4(),
            center_id=str(center_a.id),
            child_name="Jason",
            event_type=EventType.FOOD,
            confidence_score=0.95,
            review_tier="teacher",
            needs_director_review=False,
            needs_review=False,
            raw_transcript="Jason ate mac and cheese",
        )
        event = create_event_from_base(db, base)
        assert event.child_name == "Jason"
        assert event.event_type == "food"
        assert event.confidence_score == 0.95
        assert event.status == "PENDING"
