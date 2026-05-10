"""Tests for the require_role FastAPI dependency."""

from uuid import uuid4

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import backend.storage.models  # noqa: F401
from backend.config import get_settings
from backend.storage.database import Base, get_db
from backend.utils.auth_tokens import generate_token, revoke_nonce
from backend.utils.pilot_auth import require_role, require_parent_owns_child

SECRET = "test-secret-do-not-use-in-prod-32-bytes-long-pls"


# ─── Test app + DB plumbing ───────────────────────────────────


@pytest.fixture
def db_engine():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    return engine


@pytest.fixture
def app(db_engine, monkeypatch):
    """FastAPI app with three test routes — staff, director, parent."""
    monkeypatch.setenv("ENVIRONMENT", "production")  # exercise real gate
    monkeypatch.setenv("AUTH_TOKEN_SECRET", SECRET)
    get_settings.cache_clear()

    Session = sessionmaker(bind=db_engine)

    def override_db():
        s = Session()
        try:
            yield s
        finally:
            s.close()

    a = FastAPI()
    a.dependency_overrides[get_db] = override_db

    @a.get("/staff")
    async def staff_route(_=Depends(require_role("staff"))):
        return {"ok": "staff"}

    @a.get("/director")
    async def director_route(_=Depends(require_role("director"))):
        return {"ok": "director"}

    @a.get("/parent")
    async def parent_route(_=Depends(require_role("parent"))):
        return {"ok": "parent"}

    return a


@pytest.fixture
def client(app):
    return TestClient(app)


@pytest.fixture(autouse=True)
def _reset_settings_cache():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


# ─── Token-required endpoints in production ───────────────────


def test_no_token_returns_401(client):
    assert client.get("/staff").status_code == 401


def test_garbage_token_returns_401(client):
    r = client.get("/staff", headers={"Authorization": "Bearer not-a-token"})
    assert r.status_code == 401


def test_wrong_secret_returns_401(client, db_engine):
    Session = sessionmaker(bind=db_engine)
    db = Session()
    token, _ = generate_token(
        role="director", sub=uuid4(), center_id=uuid4(),
        secret="some-other-secret",
    )
    r = client.get("/director", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 401
    db.close()


def test_director_token_passes_director_route(client):
    token, _ = generate_token(
        role="director", sub=uuid4(), center_id=uuid4(), secret=SECRET
    )
    r = client.get("/director", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200


def test_director_token_passes_staff_route(client):
    token, _ = generate_token(
        role="director", sub=uuid4(), center_id=uuid4(), secret=SECRET
    )
    r = client.get("/staff", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200


def test_teacher_token_passes_staff_route(client):
    token, _ = generate_token(
        role="teacher", sub=uuid4(), center_id=uuid4(), secret=SECRET
    )
    r = client.get("/staff", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200


def test_teacher_token_blocked_from_director_route(client):
    token, _ = generate_token(
        role="teacher", sub=uuid4(), center_id=uuid4(), secret=SECRET
    )
    r = client.get("/director", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 403


def test_parent_token_blocked_from_staff_route(client):
    token, _ = generate_token(
        role="parent", sub=uuid4(), center_id=uuid4(),
        child_ids=[uuid4()], secret=SECRET,
    )
    r = client.get("/staff", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 403


def test_parent_token_passes_parent_route(client):
    token, _ = generate_token(
        role="parent", sub=uuid4(), center_id=uuid4(),
        child_ids=[uuid4()], secret=SECRET,
    )
    r = client.get("/parent", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200


def test_revoked_token_returns_401(client, db_engine):
    Session = sessionmaker(bind=db_engine)
    db = Session()
    sub = uuid4()
    token, payload = generate_token(
        role="teacher", sub=sub, center_id=uuid4(), secret=SECRET
    )
    # Sanity: works pre-revoke
    assert client.get("/staff", headers={"Authorization": f"Bearer {token}"}).status_code == 200

    revoke_nonce(db, sub, payload.nonce)
    db.close()

    assert client.get("/staff", headers={"Authorization": f"Bearer {token}"}).status_code == 401


def test_expired_token_returns_401(client):
    token, _ = generate_token(
        role="director", sub=uuid4(), center_id=uuid4(),
        expires_in_days=-1, secret=SECRET,
    )
    r = client.get("/director", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 401


# ─── Dev bypass ───────────────────────────────────────────────


def test_dev_bypass_allows_no_token(monkeypatch, db_engine):
    """In development mode, an unauthenticated request still gets through."""
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.setenv("AUTH_TOKEN_SECRET", "")
    get_settings.cache_clear()

    Session = sessionmaker(bind=db_engine)

    def override_db():
        s = Session()
        try:
            yield s
        finally:
            s.close()

    a = FastAPI()
    a.dependency_overrides[get_db] = override_db

    @a.get("/dev")
    async def dev_route(_=Depends(require_role("staff"))):
        return {"ok": True}

    c = TestClient(a)
    r = c.get("/dev")  # no Authorization header
    assert r.status_code == 200


# ─── Parent ownership guard ───────────────────────────────────


def test_parent_can_access_own_child(client):
    child_id = uuid4()
    token, _ = generate_token(
        role="parent", sub=uuid4(), center_id=uuid4(),
        child_ids=[child_id], secret=SECRET,
    )
    # Build a route that uses the ownership helper
    from fastapi import APIRouter
    from backend.utils.pilot_auth import require_role as rr

    a: FastAPI = client.app  # type: ignore[attr-defined]

    router = APIRouter()

    @router.get("/feed/{cid}")
    async def feed(cid: str, payload=Depends(rr("parent"))):
        require_parent_owns_child(child_id_=__import__("uuid").UUID(cid), payload=payload) if False else require_parent_owns_child(__import__("uuid").UUID(cid), payload)
        return {"ok": True}

    a.include_router(router)
    r = client.get(f"/feed/{child_id}", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200


def test_parent_blocked_from_other_parents_child(client):
    own_child = uuid4()
    other_child = uuid4()
    token, _ = generate_token(
        role="parent", sub=uuid4(), center_id=uuid4(),
        child_ids=[own_child], secret=SECRET,
    )

    from fastapi import APIRouter
    from backend.utils.pilot_auth import require_role as rr

    a: FastAPI = client.app  # type: ignore[attr-defined]
    router = APIRouter()

    @router.get("/feed_ownership/{cid}")
    async def feed(cid: str, payload=Depends(rr("parent"))):
        require_parent_owns_child(__import__("uuid").UUID(cid), payload)
        return {"ok": True}

    a.include_router(router)
    r = client.get(f"/feed_ownership/{other_child}", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 403
