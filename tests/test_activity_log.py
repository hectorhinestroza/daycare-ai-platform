"""Tests for the activity log API (Issue #8).

Verifies that approve/reject/edit/batch actions create audit log entries,
and that the activity log endpoint returns them correctly with filters.
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
    db.add(Center(id=CENTER_ID, name="Test Center"))
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

    def override_get_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    yield db
    app.dependency_overrides.pop(get_db, None)
    db.close()
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


def _create_event(db, center_id=CENTER_ID, status="PENDING") -> uuid.UUID:
    event_id = uuid.uuid4()
    db.add(
        Event(
            id=event_id,
            center_id=center_id,
            child_name="Jason",
            event_type="food",
            raw_transcript="Jason ate lunch",
            review_tier="teacher",
            confidence_score=0.9,
            needs_director_review=False,
            needs_review=False,
            status=status,
        )
    )
    db.commit()
    return event_id


# ─── Tests ────────────────────────────────────────────────────


def test_approve_creates_log(db_session):
    """Approving an event creates an activity log entry."""
    eid = _create_event(db_session)
    client = TestClient(app)
    client.post(f"/api/events/{CENTER_ID}/{eid}/approve")

    resp = client.get(f"/api/activity/{CENTER_ID}")
    assert resp.status_code == 200
    logs = resp.json()
    assert len(logs) >= 1
    assert logs[0]["action"] == "APPROVE"
    assert logs[0]["event_id"] == str(eid)


def test_reject_creates_log(db_session):
    """Rejecting an event creates an activity log entry."""
    eid = _create_event(db_session)
    client = TestClient(app)
    client.post(f"/api/events/{CENTER_ID}/{eid}/reject")

    resp = client.get(f"/api/activity/{CENTER_ID}")
    assert resp.status_code == 200
    logs = resp.json()
    assert len(logs) >= 1
    assert logs[0]["action"] == "REJECT"


def test_edit_creates_log(db_session):
    """Editing an event creates a log entry with old/new values."""
    eid = _create_event(db_session)
    client = TestClient(app)
    client.patch(f"/api/events/{CENTER_ID}/{eid}", json={"child_name": "Jason M."})

    resp = client.get(f"/api/activity/{CENTER_ID}")
    assert resp.status_code == 200
    logs = resp.json()
    assert len(logs) >= 1
    assert logs[0]["action"] == "EDIT"
    assert "changes" in logs[0]["details"]
    assert logs[0]["details"]["changes"]["child_name"]["new"] == "Jason M."


def test_batch_approve_creates_log(db_session):
    """Batch approving creates a single log entry with count."""
    _create_event(db_session)
    _create_event(db_session)
    client = TestClient(app)
    client.post(f"/api/events/{CENTER_ID}/batch-approve", json={"child_name": "Jason"})

    resp = client.get(f"/api/activity/{CENTER_ID}")
    assert resp.status_code == 200
    logs = resp.json()
    assert any(log["action"] == "BATCH_APPROVE" for log in logs)
    batch_log = next(log for log in logs if log["action"] == "BATCH_APPROVE")
    assert batch_log["details"]["count"] == 2


def test_filter_by_action(db_session):
    """Activity log can filter by action type."""
    eid = _create_event(db_session)
    client = TestClient(app)
    client.post(f"/api/events/{CENTER_ID}/{eid}/approve")

    eid2 = _create_event(db_session)
    client.post(f"/api/events/{CENTER_ID}/{eid2}/reject")

    resp = client.get(f"/api/activity/{CENTER_ID}?action=APPROVE")
    assert resp.status_code == 200
    logs = resp.json()
    assert all(log["action"] == "APPROVE" for log in logs)


def test_filter_by_event_id(db_session):
    """Activity log can filter by event_id."""
    eid = _create_event(db_session)
    client = TestClient(app)
    client.post(f"/api/events/{CENTER_ID}/{eid}/approve")

    resp = client.get(f"/api/activity/{CENTER_ID}?event_id={eid}")
    assert resp.status_code == 200
    logs = resp.json()
    assert len(logs) >= 1
    assert all(log["event_id"] == str(eid) for log in logs)


def test_empty_activity_log(db_session):
    """Activity log is empty when no actions taken."""
    client = TestClient(app)
    resp = client.get(f"/api/activity/{CENTER_ID}")
    assert resp.status_code == 200
    assert resp.json() == []
