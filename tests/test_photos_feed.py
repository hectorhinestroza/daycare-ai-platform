"""Tests for the parent-facing photo feed."""

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.main import app
from backend.storage.database import Base, get_db
from backend.storage.models import Center, Child, Photo

engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture
def setup_db():
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()

    def override_get_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db

    center = Center(id=uuid.uuid4(), name="Test Center")
    db.add(center)
    db.commit()

    child = Child(id=uuid.uuid4(), center_id=center.id, name="Jason", status="ACTIVE")
    db.add(child)
    db.commit()

    yield db

    app.dependency_overrides.pop(get_db, None)
    Base.metadata.drop_all(bind=engine)
    db.close()


client = TestClient(app)


@patch("backend.routers.photos.generate_presigned_url")
def test_returns_photos_with_presigned_urls(mock_presign, setup_db):
    db = setup_db
    center = db.query(Center).first()
    child = db.query(Child).first()

    p1 = Photo(
        id=uuid.uuid4(),
        center_id=center.id,
        child_id=child.id,
        s3_key="photos/c/jason/2026-04-28/a.jpg",
        caption="art project",
        created_at=datetime.now(timezone.utc) - timedelta(hours=2),
    )
    p2 = Photo(
        id=uuid.uuid4(),
        center_id=center.id,
        child_id=child.id,
        s3_key="photos/c/jason/2026-04-28/b.jpg",
        caption="snack time",
        created_at=datetime.now(timezone.utc) - timedelta(minutes=10),
    )
    db.add_all([p1, p2])
    db.commit()

    mock_presign.side_effect = lambda key: f"https://example.com/{key}?sig=xyz"

    response = client.get(f"/api/photos/feed/{center.id}/{child.id}")

    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    # Newest first
    assert data[0]["caption"] == "snack time"
    assert data[1]["caption"] == "art project"
    assert data[0]["s3_url"].startswith("https://example.com/")
    assert "sig=xyz" in data[0]["s3_url"]


@patch("backend.routers.photos.generate_presigned_url")
def test_excludes_deleted_photos(mock_presign, setup_db):
    db = setup_db
    center = db.query(Center).first()
    child = db.query(Child).first()

    live = Photo(
        id=uuid.uuid4(),
        center_id=center.id,
        child_id=child.id,
        s3_key="photos/live.jpg",
        caption="live",
    )
    deleted = Photo(
        id=uuid.uuid4(),
        center_id=center.id,
        child_id=child.id,
        s3_key="photos/deleted.jpg",
        caption="deleted",
        deleted_at=datetime.now(timezone.utc),
    )
    db.add_all([live, deleted])
    db.commit()

    mock_presign.return_value = "https://example.com/x"

    response = client.get(f"/api/photos/feed/{center.id}/{child.id}")
    data = response.json()
    assert len(data) == 1
    assert data[0]["caption"] == "live"


@patch("backend.routers.photos.generate_presigned_url")
def test_scopes_by_child(mock_presign, setup_db):
    """Photos for a different child must not leak through."""
    db = setup_db
    center = db.query(Center).first()
    child = db.query(Child).first()

    other_child = Child(id=uuid.uuid4(), center_id=center.id, name="Other", status="ACTIVE")
    db.add(other_child)
    db.commit()

    db.add(Photo(id=uuid.uuid4(), center_id=center.id, child_id=child.id, s3_key="a.jpg", caption="ours"))
    db.add(Photo(id=uuid.uuid4(), center_id=center.id, child_id=other_child.id, s3_key="b.jpg", caption="theirs"))
    db.commit()

    mock_presign.return_value = "https://example.com/x"

    response = client.get(f"/api/photos/feed/{center.id}/{child.id}")
    data = response.json()
    assert len(data) == 1
    assert data[0]["caption"] == "ours"


def test_empty_when_no_photos(setup_db):
    db = setup_db
    center = db.query(Center).first()
    child = db.query(Child).first()

    response = client.get(f"/api/photos/feed/{center.id}/{child.id}")
    assert response.status_code == 200
    assert response.json() == []
