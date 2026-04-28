"""Tests for the pending-photo flow.

When a teacher sends a photo without prior /child context, the photo is
EXIF-stripped, parked under pending/ in S3, and a PendingPhoto row holds
it for 30 minutes. A subsequent /child command resolves outstanding
pending photos into final Photo rows. Expired pending photos are GC'd
by a scheduler job.
"""

import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.main import app
from backend.routers.whatsapp import _command_context
from backend.storage.database import Base, get_db
from backend.storage.models import Center, Child, PendingPhoto, Photo, Teacher

engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(autouse=True)
def setup_db():
    """Fresh schema per test, seeded with center + teacher + one child."""
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

    teacher = Teacher(
        id=uuid.uuid4(), center_id=center.id, name="Test Teacher", phone="+1234567890"
    )
    db.add(teacher)
    db.commit()

    child = Child(id=uuid.uuid4(), center_id=center.id, name="Jason", status="ACTIVE")
    db.add(child)
    db.commit()

    yield db

    app.dependency_overrides.pop(get_db, None)
    Base.metadata.drop_all(bind=engine)
    _command_context.clear()  # don't leak /child state across tests
    db.close()


client = TestClient(app)


# ─── Photo intake ───────────────────────────────────────────


class TestPhotoWithoutContext:
    """Photo arrives before /child is set → parks as pending."""

    @patch("backend.routers.whatsapp.upload_photo")
    @patch("backend.routers.whatsapp.strip_exif")
    @patch("backend.routers.whatsapp.delete_twilio_media", new_callable=AsyncMock)
    @patch("backend.routers.whatsapp.download_twilio_media", new_callable=AsyncMock)
    def test_creates_pending_photo_row(
        self, mock_download, mock_delete_twilio, mock_strip, mock_upload, setup_db
    ):
        db = setup_db
        teacher = db.query(Teacher).first()

        mock_download.return_value = (b"raw_jpeg_bytes", "image/jpeg")
        mock_strip.return_value = b"clean_jpeg_bytes"

        response = client.post(
            "/webhook/whatsapp",
            data={
                "From": "+1234567890",
                "Body": "playtime",
                "NumMedia": "1",
                "MediaUrl0": "https://api.twilio.com/media/x",
                "MediaContentType0": "image/jpeg",
            },
        )

        assert response.status_code == 200
        assert "assign it to a child" in response.text

        pending = db.query(PendingPhoto).all()
        assert len(pending) == 1
        assert pending[0].teacher_id == teacher.id
        assert pending[0].caption == "playtime"
        assert pending[0].s3_temp_key.startswith(f"pending/{teacher.center_id}/{teacher.id}/")
        # 30-min TTL window — give a generous tolerance for clock drift.
        # SQLite drops tzinfo on round-trip, so normalize both sides to naive UTC.
        expires = pending[0].expires_at
        if expires.tzinfo is not None:
            expires = expires.replace(tzinfo=None)
        ttl = expires - datetime.now(UTC).replace(tzinfo=None)
        assert timedelta(minutes=29) < ttl <= timedelta(minutes=30)

        # No final Photo row should exist yet
        assert db.query(Photo).count() == 0
        # EXIF strip ran on the raw bytes
        mock_strip.assert_called_once_with(b"raw_jpeg_bytes")
        # S3 upload used the pending key
        upload_args = mock_upload.call_args
        assert upload_args.args[0] == b"clean_jpeg_bytes"
        assert upload_args.args[1].startswith(f"pending/{teacher.center_id}/")


class TestPhotoWithContext:
    """Photo arrives after /child is set → goes straight to final Photo."""

    @patch("backend.routers.whatsapp.get_child_for_processing")
    @patch("backend.routers.whatsapp.upload_photo")
    @patch("backend.routers.whatsapp.strip_exif")
    @patch("backend.routers.whatsapp.delete_twilio_media", new_callable=AsyncMock)
    @patch("backend.routers.whatsapp.download_twilio_media", new_callable=AsyncMock)
    def test_happy_path_creates_photo(
        self,
        mock_download,
        mock_delete_twilio,
        mock_strip,
        mock_upload,
        mock_consent,
        setup_db,
    ):
        db = setup_db
        child = db.query(Child).first()

        mock_download.return_value = (b"raw", "image/jpeg")
        mock_strip.return_value = b"clean"
        mock_consent.return_value = MagicMock()  # consent OK

        # Set /child context first
        client.post(
            "/webhook/whatsapp",
            data={"From": "+1234567890", "Body": "/child Jason", "NumMedia": "0"},
        )

        response = client.post(
            "/webhook/whatsapp",
            data={
                "From": "+1234567890",
                "Body": "snack",
                "NumMedia": "1",
                "MediaUrl0": "https://api.twilio.com/media/x",
                "MediaContentType0": "image/jpeg",
            },
        )

        assert response.status_code == 200
        assert "saved for Jason" in response.text

        photos = db.query(Photo).all()
        assert len(photos) == 1
        assert photos[0].child_id == child.id
        assert photos[0].caption == "snack"
        assert db.query(PendingPhoto).count() == 0


# ─── /child command resolution ──────────────────────────────


class TestChildCommandResolvesPending:
    """A subsequent /child command attaches outstanding pending photos."""

    @patch("backend.routers.whatsapp.get_child_for_processing")
    @patch("backend.routers.whatsapp.delete_s3_object")
    @patch("backend.routers.whatsapp.upload_photo")
    @patch("backend.routers.whatsapp.download_from_s3")
    def test_resolves_pending_to_final_photo(
        self, mock_download_s3, mock_upload, mock_delete_s3, mock_consent, setup_db
    ):
        db = setup_db
        center = db.query(Center).first()
        teacher = db.query(Teacher).first()
        child = db.query(Child).first()

        # Pre-seed a pending photo (as if a prior request had stored one)
        pending = PendingPhoto(
            id=uuid.uuid4(),
            center_id=center.id,
            teacher_id=teacher.id,
            s3_temp_key=f"pending/{center.id}/{teacher.id}/abc.jpg",
            caption="art project",
            content_type="image/jpeg",
            expires_at=datetime.now(UTC) + timedelta(minutes=30),
        )
        db.add(pending)
        db.commit()

        mock_download_s3.return_value = b"clean_bytes"
        mock_consent.return_value = MagicMock()

        response = client.post(
            "/webhook/whatsapp",
            data={"From": "+1234567890", "Body": "/child Jason", "NumMedia": "0"},
        )

        assert response.status_code == 200
        assert "1 photo(s) saved for Jason" in response.text

        photos = db.query(Photo).all()
        assert len(photos) == 1
        assert photos[0].child_id == child.id
        assert photos[0].caption == "art project"
        assert photos[0].s3_key.startswith(f"photos/{center.id}/{child.id}/")

        # Pending row + temp S3 object cleaned up
        assert db.query(PendingPhoto).count() == 0
        mock_delete_s3.assert_called_once_with(pending.s3_temp_key)

    def test_unknown_child_leaves_pending_intact(self, setup_db):
        """If /child name isn't in the roster, pending photos are NOT discarded."""
        db = setup_db
        center = db.query(Center).first()
        teacher = db.query(Teacher).first()

        pending = PendingPhoto(
            id=uuid.uuid4(),
            center_id=center.id,
            teacher_id=teacher.id,
            s3_temp_key="pending/x.jpg",
            expires_at=datetime.now(UTC) + timedelta(minutes=30),
        )
        db.add(pending)
        db.commit()

        response = client.post(
            "/webhook/whatsapp",
            data={"From": "+1234567890", "Body": "/child Nobody", "NumMedia": "0"},
        )

        assert response.status_code == 200
        assert "not found in roster" in response.text
        # Pending is intact — teacher can retry with a correct name
        assert db.query(PendingPhoto).count() == 1
        assert db.query(Photo).count() == 0

    @patch("backend.routers.whatsapp.get_child_for_processing")
    @patch("backend.routers.whatsapp.delete_s3_object")
    def test_no_consent_discards_pending(
        self, mock_delete_s3, mock_consent, setup_db
    ):
        """No consent for the named child → pending row + S3 object are dropped."""
        db = setup_db
        center = db.query(Center).first()
        teacher = db.query(Teacher).first()

        pending = PendingPhoto(
            id=uuid.uuid4(),
            center_id=center.id,
            teacher_id=teacher.id,
            s3_temp_key="pending/no-consent.jpg",
            expires_at=datetime.now(UTC) + timedelta(minutes=30),
        )
        db.add(pending)
        db.commit()

        mock_consent.return_value = None  # consent gate denies

        response = client.post(
            "/webhook/whatsapp",
            data={"From": "+1234567890", "Body": "/child Jason", "NumMedia": "0"},
        )

        assert response.status_code == 200
        assert db.query(PendingPhoto).count() == 0
        assert db.query(Photo).count() == 0
        mock_delete_s3.assert_called_once_with("pending/no-consent.jpg")


# ─── Scheduler cleanup ───────────────────────────────────────


class TestSchedulerCleanup:
    """Expired pending photos are GC'd by the scheduler job."""

    @patch("backend.services.scheduler.delete_s3_object")
    @patch("backend.services.scheduler.SessionLocal")
    @pytest.mark.asyncio
    async def test_cleanup_deletes_expired(
        self, mock_session_local, mock_delete_s3, setup_db
    ):
        from backend.services.scheduler import _cleanup_expired_pending_photos

        db = setup_db
        center = db.query(Center).first()
        teacher = db.query(Teacher).first()

        expired = PendingPhoto(
            id=uuid.uuid4(),
            center_id=center.id,
            teacher_id=teacher.id,
            s3_temp_key="pending/expired.jpg",
            expires_at=datetime.now(UTC) - timedelta(minutes=5),
        )
        fresh = PendingPhoto(
            id=uuid.uuid4(),
            center_id=center.id,
            teacher_id=teacher.id,
            s3_temp_key="pending/fresh.jpg",
            expires_at=datetime.now(UTC) + timedelta(minutes=20),
        )
        db.add_all([expired, fresh])
        db.commit()

        # Make the scheduler use our test session
        mock_session_local.return_value = db

        await _cleanup_expired_pending_photos()

        remaining = db.query(PendingPhoto).all()
        assert len(remaining) == 1
        assert remaining[0].s3_temp_key == "pending/fresh.jpg"
        mock_delete_s3.assert_called_once_with("pending/expired.jpg")
