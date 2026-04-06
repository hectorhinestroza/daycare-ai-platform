"""Tests for the onboarding API (Issue #9).

Covers rooms, teachers, children, and parent contacts CRUD,
plus multi-tenant isolation and status transitions.
"""

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.main import app
from backend.storage.database import Base, get_db
from backend.storage.models import Center

# ─── Fixtures ─────────────────────────────────────────────────

CENTER_ID = uuid.uuid4()
OTHER_CENTER_ID = uuid.uuid4()


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
    db.add(Center(id=OTHER_CENTER_ID, name="Other Center"))
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


# ─── Room Tests ───────────────────────────────────────────────


def test_create_room(db_session):
    client = TestClient(app)
    resp = client.post(f"/api/rooms/{CENTER_ID}", json={"name": "Butterflies"})
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Butterflies"
    assert data["center_id"] == str(CENTER_ID)


def test_list_rooms(db_session):
    client = TestClient(app)
    client.post(f"/api/rooms/{CENTER_ID}", json={"name": "Toddlers"})
    client.post(f"/api/rooms/{CENTER_ID}", json={"name": "Pre-K"})

    resp = client.get(f"/api/rooms/{CENTER_ID}")
    assert resp.status_code == 200
    assert len(resp.json()) == 2


def test_update_room(db_session):
    client = TestClient(app)
    create = client.post(f"/api/rooms/{CENTER_ID}", json={"name": "Old Name"})
    room_id = create.json()["id"]

    resp = client.patch(f"/api/rooms/{CENTER_ID}/{room_id}", json={"name": "New Name"})
    assert resp.status_code == 200
    assert resp.json()["name"] == "New Name"


def test_delete_room(db_session):
    client = TestClient(app)
    create = client.post(f"/api/rooms/{CENTER_ID}", json={"name": "Temp Room"})
    room_id = create.json()["id"]

    resp = client.delete(f"/api/rooms/{CENTER_ID}/{room_id}")
    assert resp.status_code == 204

    rooms = client.get(f"/api/rooms/{CENTER_ID}").json()
    assert len(rooms) == 0


def test_room_not_found(db_session):
    client = TestClient(app)
    fake_id = uuid.uuid4()
    resp = client.patch(f"/api/rooms/{CENTER_ID}/{fake_id}", json={"name": "X"})
    assert resp.status_code == 404


def test_rooms_multi_tenant(db_session):
    """Rooms from one center don't appear in another."""
    client = TestClient(app)
    client.post(f"/api/rooms/{CENTER_ID}", json={"name": "Room A"})
    client.post(f"/api/rooms/{OTHER_CENTER_ID}", json={"name": "Room B"})

    resp1 = client.get(f"/api/rooms/{CENTER_ID}")
    resp2 = client.get(f"/api/rooms/{OTHER_CENTER_ID}")
    assert len(resp1.json()) == 1
    assert resp1.json()[0]["name"] == "Room A"
    assert len(resp2.json()) == 1
    assert resp2.json()[0]["name"] == "Room B"


# ─── Teacher Tests ────────────────────────────────────────────


def test_create_teacher(db_session):
    client = TestClient(app)
    resp = client.post(f"/api/teachers/{CENTER_ID}", json={"name": "Ms. Smith", "phone": "+15551234567"})
    assert resp.status_code == 201
    assert resp.json()["name"] == "Ms. Smith"


def test_list_teachers(db_session):
    client = TestClient(app)
    client.post(f"/api/teachers/{CENTER_ID}", json={"name": "T1", "phone": "+1001"})
    client.post(f"/api/teachers/{CENTER_ID}", json={"name": "T2", "phone": "+1002"})

    resp = client.get(f"/api/teachers/{CENTER_ID}")
    assert resp.status_code == 200
    assert len(resp.json()) == 2


def test_update_teacher_room(db_session):
    """Assign a teacher to a room."""
    client = TestClient(app)
    room = client.post(f"/api/rooms/{CENTER_ID}", json={"name": "Ladybugs"}).json()
    teacher = client.post(f"/api/teachers/{CENTER_ID}", json={"name": "Ms. Jones", "phone": "+1003"}).json()

    resp = client.patch(
        f"/api/teachers/{CENTER_ID}/{teacher['id']}",
        json={"room_id": room["id"]},
    )
    assert resp.status_code == 200
    assert resp.json()["room_id"] == room["id"]


def test_deactivate_teacher(db_session):
    """Deactivated teachers don't appear in list."""
    client = TestClient(app)
    teacher = client.post(f"/api/teachers/{CENTER_ID}", json={"name": "Leaving", "phone": "+1004"}).json()

    client.patch(f"/api/teachers/{CENTER_ID}/{teacher['id']}", json={"is_active": False})

    resp = client.get(f"/api/teachers/{CENTER_ID}")
    assert len(resp.json()) == 0  # deactivated = hidden


# ─── Children Tests ───────────────────────────────────────────


def test_create_child(db_session):
    client = TestClient(app)
    resp = client.post(f"/api/children/{CENTER_ID}", json={"name": "Jason", "allergies": "peanuts"})
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Jason"
    assert data["status"] == "ENROLLED"
    assert data["allergies"] == "peanuts"


def test_list_children_filter_by_room(db_session):
    """Filter children by room_id."""
    client = TestClient(app)
    room = client.post(f"/api/rooms/{CENTER_ID}", json={"name": "Bears"}).json()
    client.post(f"/api/children/{CENTER_ID}", json={"name": "A", "room_id": room["id"]})
    client.post(f"/api/children/{CENTER_ID}", json={"name": "B"})

    resp = client.get(f"/api/children/{CENTER_ID}?room_id={room['id']}")
    assert len(resp.json()) == 1
    assert resp.json()[0]["name"] == "A"


def test_list_children_filter_by_status(db_session):
    """Filter children by status."""
    client = TestClient(app)
    client.post(f"/api/children/{CENTER_ID}", json={"name": "Active", "status": "ACTIVE"})
    client.post(f"/api/children/{CENTER_ID}", json={"name": "Waitlist", "status": "WAITLIST"})

    resp = client.get(f"/api/children/{CENTER_ID}?status=ACTIVE")
    assert len(resp.json()) == 1
    assert resp.json()[0]["name"] == "Active"


def test_get_child_detail(db_session):
    """Get child profile includes parent contacts."""
    client = TestClient(app)
    child = client.post(f"/api/children/{CENTER_ID}", json={"name": "Maya"}).json()
    client.post(
        f"/api/children/{CENTER_ID}/{child['id']}/contacts",
        json={"name": "Mom", "email": "mom@test.com", "relationship_type": "parent"},
    )

    resp = client.get(f"/api/children/{CENTER_ID}/{child['id']}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "Maya"
    assert len(data["parent_contacts"]) == 1
    assert data["parent_contacts"][0]["name"] == "Mom"


def test_update_child_status(db_session):
    """Change child status (enrollment workflow)."""
    client = TestClient(app)
    child = client.post(f"/api/children/{CENTER_ID}", json={"name": "Sam"}).json()
    assert child["status"] == "ENROLLED"

    resp = client.patch(f"/api/children/{CENTER_ID}/{child['id']}", json={"status": "ACTIVE"})
    assert resp.json()["status"] == "ACTIVE"

    resp = client.patch(f"/api/children/{CENTER_ID}/{child['id']}", json={"status": "UNENROLLED"})
    assert resp.json()["status"] == "UNENROLLED"


def test_children_multi_tenant(db_session):
    """Children in one center don't leak to another."""
    client = TestClient(app)
    client.post(f"/api/children/{CENTER_ID}", json={"name": "Alice"})
    client.post(f"/api/children/{OTHER_CENTER_ID}", json={"name": "Bob"})

    resp1 = client.get(f"/api/children/{CENTER_ID}")
    resp2 = client.get(f"/api/children/{OTHER_CENTER_ID}")
    assert len(resp1.json()) == 1
    assert resp1.json()[0]["name"] == "Alice"
    assert len(resp2.json()) == 1
    assert resp2.json()[0]["name"] == "Bob"


# ─── Parent Contact Tests ─────────────────────────────────────


def test_add_parent_contact(db_session):
    client = TestClient(app)
    child = client.post(f"/api/children/{CENTER_ID}", json={"name": "Zoe"}).json()

    resp = client.post(
        f"/api/children/{CENTER_ID}/{child['id']}/contacts",
        json={
            "name": "Dad",
            "phone": "+15559876543",
            "relationship_type": "parent",
            "can_pickup": True,
            "is_primary": True,
        },
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Dad"
    assert data["is_primary"] is True
    assert data["can_pickup"] is True


def test_list_contacts(db_session):
    client = TestClient(app)
    child = client.post(f"/api/children/{CENTER_ID}", json={"name": "Ella"}).json()
    client.post(f"/api/children/{CENTER_ID}/{child['id']}/contacts", json={"name": "Mom"})
    client.post(f"/api/children/{CENTER_ID}/{child['id']}/contacts", json={"name": "Dad"})

    resp = client.get(f"/api/children/{CENTER_ID}/{child['id']}/contacts")
    assert resp.status_code == 200
    assert len(resp.json()) == 2


def test_update_contact(db_session):
    client = TestClient(app)
    child = client.post(f"/api/children/{CENTER_ID}", json={"name": "Mia"}).json()
    contact = client.post(
        f"/api/children/{CENTER_ID}/{child['id']}/contacts", json={"name": "Grandma", "can_pickup": False}
    ).json()

    resp = client.patch(f"/api/contacts/{CENTER_ID}/{contact['id']}", json={"can_pickup": True})
    assert resp.status_code == 200
    assert resp.json()["can_pickup"] is True


def test_contact_for_nonexistent_child(db_session):
    """Adding contact for non-existent child returns 404."""
    client = TestClient(app)
    fake_id = uuid.uuid4()
    resp = client.post(f"/api/children/{CENTER_ID}/{fake_id}/contacts", json={"name": "Nobody"})
    assert resp.status_code == 404
