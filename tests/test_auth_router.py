"""Tests for /api/auth/whoami and /api/admin/tokens/{issue,revoke}."""

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import backend.storage.models  # noqa: F401
from backend.config import get_settings
from backend.main import app
from backend.storage.database import Base, get_db
from backend.storage.models import Admin, Center, Child, ParentContact, Room, Teacher
from backend.utils.auth_tokens import generate_token

SECRET = "test-secret-do-not-use-in-prod-32-bytes-long-pls"


@pytest.fixture
def engine_and_session(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("AUTH_TOKEN_SECRET", SECRET)
    get_settings.cache_clear()

    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    return engine, Session


@pytest.fixture
def db_and_seeds(engine_and_session):
    _, Session = engine_and_session
    db = Session()

    center = Center(id=uuid4(), name="Test Center")
    db.add(center)
    db.commit()

    room = Room(id=uuid4(), center_id=center.id, name="Toddlers")
    db.add(room)
    db.commit()

    child = Child(id=uuid4(), center_id=center.id, name="TestKid", room_id=room.id, status="ACTIVE")
    db.add(child)
    db.commit()

    parent = ParentContact(id=uuid4(), center_id=center.id, child_id=child.id, name="P", relationship_type="parent")
    db.add(parent)
    db.commit()

    teacher = Teacher(id=uuid4(), center_id=center.id, name="T", phone="+15550000001")
    db.add(teacher)
    db.commit()

    admin = Admin(id=uuid4(), center_id=center.id, email="d@example.com", name="D", role="director")
    db.add(admin)
    db.commit()

    def override_db():
        s = Session()
        try:
            yield s
        finally:
            s.close()

    app.dependency_overrides[get_db] = override_db
    yield {
        "db": db,
        "center_id": center.id,
        "child_id": child.id,
        "parent_id": parent.id,
        "teacher_id": teacher.id,
        "admin_id": admin.id,
    }
    app.dependency_overrides.pop(get_db, None)
    db.close()


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture(autouse=True)
def _reset_settings_cache():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


# ─── whoami ───────────────────────────────────────────────────


def test_whoami_returns_director_identity(client, db_and_seeds):
    seeds = db_and_seeds
    token, _ = generate_token(
        role="director", sub=seeds["admin_id"], center_id=seeds["center_id"],
        secret=SECRET,
    )
    r = client.get("/api/auth/whoami", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    body = r.json()
    assert body["role"] == "director"
    assert body["sub"] == str(seeds["admin_id"])
    assert body["center_id"] == str(seeds["center_id"])
    assert body["child_ids"] == []


def test_whoami_returns_teacher_identity(client, db_and_seeds):
    seeds = db_and_seeds
    token, _ = generate_token(
        role="teacher", sub=seeds["teacher_id"], center_id=seeds["center_id"],
        secret=SECRET,
    )
    r = client.get("/api/auth/whoami", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.json()["role"] == "teacher"


def test_whoami_parent_path_returns_child_ids(client, db_and_seeds):
    seeds = db_and_seeds
    token, _ = generate_token(
        role="parent", sub=seeds["parent_id"], center_id=seeds["center_id"],
        child_ids=[seeds["child_id"]], secret=SECRET,
    )
    r = client.get("/api/auth/whoami/parent", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    body = r.json()
    assert body["role"] == "parent"
    assert body["child_ids"] == [str(seeds["child_id"])]


# ─── issue ────────────────────────────────────────────────────


def test_issue_requires_director(client, db_and_seeds):
    seeds = db_and_seeds
    teacher_token, _ = generate_token(
        role="teacher", sub=seeds["teacher_id"], center_id=seeds["center_id"],
        secret=SECRET,
    )
    r = client.post(
        "/api/admin/tokens/issue",
        json={
            "role": "parent",
            "sub": str(seeds["parent_id"]),
            "center_id": str(seeds["center_id"]),
            "child_ids": [str(seeds["child_id"])],
        },
        headers={"Authorization": f"Bearer {teacher_token}"},
    )
    assert r.status_code == 403


def test_issue_parent_token_returns_bootstrap_url(client, db_and_seeds):
    seeds = db_and_seeds
    director_token, _ = generate_token(
        role="director", sub=seeds["admin_id"], center_id=seeds["center_id"],
        secret=SECRET,
    )
    r = client.post(
        "/api/admin/tokens/issue",
        json={
            "role": "parent",
            "sub": str(seeds["parent_id"]),
            "center_id": str(seeds["center_id"]),
            "child_ids": [str(seeds["child_id"])],
        },
        headers={"Authorization": f"Bearer {director_token}"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["token"]
    assert body["bootstrap_url"].endswith(f"?token={body['token']}")
    assert "/app" in body["bootstrap_url"]


def test_issue_rejects_unknown_parent(client, db_and_seeds):
    seeds = db_and_seeds
    director_token, _ = generate_token(
        role="director", sub=seeds["admin_id"], center_id=seeds["center_id"],
        secret=SECRET,
    )
    r = client.post(
        "/api/admin/tokens/issue",
        json={
            "role": "parent",
            "sub": str(uuid4()),
            "center_id": str(seeds["center_id"]),
            "child_ids": [str(seeds["child_id"])],
        },
        headers={"Authorization": f"Bearer {director_token}"},
    )
    assert r.status_code == 404


def test_issue_parent_requires_child_ids(client, db_and_seeds):
    seeds = db_and_seeds
    director_token, _ = generate_token(
        role="director", sub=seeds["admin_id"], center_id=seeds["center_id"],
        secret=SECRET,
    )
    r = client.post(
        "/api/admin/tokens/issue",
        json={
            "role": "parent",
            "sub": str(seeds["parent_id"]),
            "center_id": str(seeds["center_id"]),
            # no child_ids
        },
        headers={"Authorization": f"Bearer {director_token}"},
    )
    assert r.status_code == 400


# ─── revoke ───────────────────────────────────────────────────


def test_revoke_then_token_no_longer_works(client, db_and_seeds):
    seeds = db_and_seeds
    director_token, _ = generate_token(
        role="director", sub=seeds["admin_id"], center_id=seeds["center_id"],
        secret=SECRET,
    )
    # Issue a teacher token
    r = client.post(
        "/api/admin/tokens/issue",
        json={
            "role": "teacher",
            "sub": str(seeds["teacher_id"]),
            "center_id": str(seeds["center_id"]),
        },
        headers={"Authorization": f"Bearer {director_token}"},
    )
    assert r.status_code == 200
    fresh = r.json()
    teacher_token = fresh["token"]
    nonce = fresh["nonce"]

    # whoami works
    r = client.get("/api/auth/whoami", headers={"Authorization": f"Bearer {teacher_token}"})
    assert r.status_code == 200

    # Revoke
    r = client.post(
        "/api/admin/tokens/revoke",
        json={"sub": str(seeds["teacher_id"]), "nonce": nonce},
        headers={"Authorization": f"Bearer {director_token}"},
    )
    assert r.status_code == 200

    # whoami now fails
    r = client.get("/api/auth/whoami", headers={"Authorization": f"Bearer {teacher_token}"})
    assert r.status_code == 401
