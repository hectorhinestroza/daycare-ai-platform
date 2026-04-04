"""Tests for the events review API (Issue #6 — Chunk 1).

Tests all 6 endpoints:
- GET  /api/events/pending/teacher/{center_id}
- GET  /api/events/pending/director/{center_id}
- GET  /api/events/{center_id}/{event_id}
- POST /api/events/{center_id}/{event_id}/approve
- POST /api/events/{center_id}/{event_id}/reject
- PATCH /api/events/{center_id}/{event_id}
"""

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.main import app
from backend.storage.database import Base, get_db
from backend.storage.models import Center, Event, Room, Teacher

# ─── Fixtures ─────────────────────────────────────────────────

CENTER_ID = uuid.uuid4()
OTHER_CENTER_ID = uuid.uuid4()
TEACHER_ID = uuid.uuid4()
ROOM_ID = uuid.uuid4()


@pytest.fixture()
def db_session():
    """Create an isolated in-memory DB + session for each test."""
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)

    db = TestingSessionLocal()

    # Seed test data
    db.add(Center(id=CENTER_ID, name="Test Center"))
    db.add(Center(id=OTHER_CENTER_ID, name="Other Center"))
    db.add(Room(id=ROOM_ID, center_id=CENTER_ID, name="Butterflies"))
    db.add(
        Teacher(
            id=TEACHER_ID,
            center_id=CENTER_ID,
            name="Ms. Smith",
            phone="+15551234567",
            room_id=ROOM_ID,
        )
    )
    db.commit()

    # Override get_db to use this test session
    def override_get_db():
        try:
            yield db
        finally:
            pass  # don't close — fixture manages lifecycle

    app.dependency_overrides[get_db] = override_get_db

    yield db

    app.dependency_overrides.pop(get_db, None)
    db.close()
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


def _create_event(
    db,
    center_id=CENTER_ID,
    review_tier="teacher",
    needs_director_review=False,
    status="PENDING",
) -> uuid.UUID:
    """Helper to insert a test event."""
    event_id = uuid.uuid4()
    db.add(
        Event(
            id=event_id,
            center_id=center_id,
            teacher_id=TEACHER_ID,
            child_name="Jason",
            event_type="food",
            details="Ate lunch",
            raw_transcript="Jason ate lunch",
            review_tier=review_tier,
            confidence_score=0.9,
            needs_director_review=needs_director_review,
            needs_review=needs_director_review,
            status=status,
        )
    )
    db.commit()
    return event_id


# ─── Teacher Queue ────────────────────────────────────────────


def test_teacher_queue_returns_pending_teacher_events(db_session):
    eid = _create_event(db_session, review_tier="teacher")
    _create_event(db_session, review_tier="director", needs_director_review=True)

    client = TestClient(app)
    resp = client.get(f"/api/events/pending/teacher/{CENTER_ID}")
    assert resp.status_code == 200
    events = resp.json()
    assert len(events) == 1
    assert events[0]["id"] == str(eid)
    assert events[0]["review_tier"] == "teacher"


def test_teacher_queue_empty_for_other_center(db_session):
    _create_event(db_session, center_id=CENTER_ID)

    client = TestClient(app)
    resp = client.get(f"/api/events/pending/teacher/{OTHER_CENTER_ID}")
    assert resp.status_code == 200
    assert resp.json() == []


# ─── Director Queue ──────────────────────────────────────────


def test_director_queue_returns_flagged_events(db_session):
    eid = _create_event(db_session, review_tier="director", needs_director_review=True)
    _create_event(db_session, review_tier="teacher")

    client = TestClient(app)
    resp = client.get(f"/api/events/pending/director/{CENTER_ID}")
    assert resp.status_code == 200
    events = resp.json()
    assert len(events) == 1
    assert events[0]["id"] == str(eid)
    assert events[0]["needs_director_review"] is True


# ─── Get Single Event ────────────────────────────────────────


def test_get_event_detail(db_session):
    eid = _create_event(db_session)

    client = TestClient(app)
    resp = client.get(f"/api/events/{CENTER_ID}/{eid}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == str(eid)
    assert data["child_name"] == "Jason"


def test_get_event_not_found(db_session):
    fake_id = uuid.uuid4()
    client = TestClient(app)
    resp = client.get(f"/api/events/{CENTER_ID}/{fake_id}")
    assert resp.status_code == 404


def test_get_event_wrong_center(db_session):
    """Multi-tenant isolation: can't access another center's event."""
    eid = _create_event(db_session, center_id=CENTER_ID)

    client = TestClient(app)
    resp = client.get(f"/api/events/{OTHER_CENTER_ID}/{eid}")
    assert resp.status_code == 404


# ─── Approve ─────────────────────────────────────────────────


def test_approve_event(db_session):
    eid = _create_event(db_session)

    client = TestClient(app)
    resp = client.post(f"/api/events/{CENTER_ID}/{eid}/approve")
    assert resp.status_code == 200
    data = resp.json()
    assert data["message"] == "Event approved"
    assert data["event"]["status"] == "APPROVED"


def test_approve_event_not_found(db_session):
    fake_id = uuid.uuid4()
    client = TestClient(app)
    resp = client.post(f"/api/events/{CENTER_ID}/{fake_id}/approve")
    assert resp.status_code == 404


# ─── Reject ──────────────────────────────────────────────────


def test_reject_event(db_session):
    eid = _create_event(db_session)

    client = TestClient(app)
    resp = client.post(f"/api/events/{CENTER_ID}/{eid}/reject")
    assert resp.status_code == 200
    data = resp.json()
    assert data["message"] == "Event rejected"
    assert data["event"]["status"] == "REJECTED"


# ─── Edit (PATCH) ────────────────────────────────────────────


def test_edit_event_child_name(db_session):
    eid = _create_event(db_session)

    client = TestClient(app)
    resp = client.patch(
        f"/api/events/{CENTER_ID}/{eid}",
        json={"child_name": "Emma"},
    )
    assert resp.status_code == 200
    assert resp.json()["event"]["child_name"] == "Emma"


def test_edit_event_details(db_session):
    eid = _create_event(db_session)

    client = TestClient(app)
    resp = client.patch(
        f"/api/events/{CENTER_ID}/{eid}",
        json={"details": "Ate spaghetti for lunch"},
    )
    assert resp.status_code == 200
    assert resp.json()["event"]["details"] == "Ate spaghetti for lunch"


def test_edit_event_no_fields(db_session):
    eid = _create_event(db_session)

    client = TestClient(app)
    resp = client.patch(
        f"/api/events/{CENTER_ID}/{eid}",
        json={},
    )
    assert resp.status_code == 400


def test_edit_event_not_found(db_session):
    fake_id = uuid.uuid4()
    client = TestClient(app)
    resp = client.patch(
        f"/api/events/{CENTER_ID}/{fake_id}",
        json={"child_name": "Emma"},
    )
    assert resp.status_code == 404


def test_edit_event_wrong_center(db_session):
    """Multi-tenant: can't edit another center's event."""
    eid = _create_event(db_session, center_id=CENTER_ID)

    client = TestClient(app)
    resp = client.patch(
        f"/api/events/{OTHER_CENTER_ID}/{eid}",
        json={"child_name": "Hacked"},
    )
    assert resp.status_code == 404
