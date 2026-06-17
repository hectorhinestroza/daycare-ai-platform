"""Tests for the batch-photo flow + AI-driven photo context.

Covers:
  - Photo with caption → resolver → single child fan-out
  - Photo with caption naming multiple children → fan-out to all
  - Photo with "everyone" caption → fan-out to room roster
  - Multiple photos in one Twilio webhook (NumMedia > 1)
  - No caption → all stored as PendingPhoto, teacher prompted
  - Follow-up text reply names kids → pending photos applied
  - Follow-up text says "everyone" → fan out to room roster
  - Follow-up text describing an event → falls through to event extraction

Multi-kid model: one S3 object per photo, one Photo row per (photo × child).
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
from backend.routers import whatsapp as whatsapp_router
from backend.routers.whatsapp import _command_context
from backend.services.photo_context import PhotoContext

# TestClient serializes requests, so the coalesce sleep can't help us
# (sibling webhooks won't actually run during it). Disable to keep tests fast.
whatsapp_router.PHOTO_BATCH_COALESCE_S = 0
from backend.storage.database import Base, get_db
from backend.storage.models import (
    Center,
    Child,
    PendingPhoto,
    Photo,
    Room,
    Teacher,
    TeacherClassroom,
)

engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(autouse=True)
def setup_db():
    """Center + teacher in one room + three children (Clara, Emi, Lola)."""
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()

    def override_get_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db

    center = Center(id=uuid.uuid4(), name="Tilly's Tots")
    db.add(center)
    db.commit()

    room = Room(id=uuid.uuid4(), center_id=center.id, name="Toddlers")
    db.add(room)
    db.commit()

    teacher = Teacher(
        id=uuid.uuid4(),
        center_id=center.id,
        name="Ms. Hector",
        phone="+15550001111",
    )
    db.add(teacher)
    db.commit()
    db.add(
        TeacherClassroom(
            teacher_id=teacher.id,
            room_id=room.id,
            center_id=center.id,
            is_primary=True,
        )
    )
    db.commit()

    for nm in ("Clara", "Emi", "Lola"):
        db.add(
            Child(
                id=uuid.uuid4(),
                center_id=center.id,
                name=nm,
                room_id=room.id,
                status="ACTIVE",
            )
        )
    db.commit()

    yield db

    app.dependency_overrides.pop(get_db, None)
    Base.metadata.drop_all(bind=engine)
    _command_context.clear()
    db.close()


client = TestClient(app)


def _ctx(applies_to_all=False, child_names=None):
    return PhotoContext(
        applies_to_all=applies_to_all,
        child_names=child_names or [],
        raw_message="",
    )


# ─── Caption-driven resolution ─────────────────────────────────


class TestCaptionResolution:
    @patch("backend.routers.whatsapp.resolve_photo_context", new_callable=AsyncMock)
    @patch("backend.routers.whatsapp.get_child_for_processing")
    @patch("backend.routers.whatsapp.upload_photo")
    @patch("backend.routers.whatsapp.strip_exif")
    @patch("backend.routers.whatsapp.delete_twilio_media_with_retry", new_callable=AsyncMock)
    @patch("backend.routers.whatsapp.download_twilio_media", new_callable=AsyncMock)
    def test_single_named_child_in_caption(
        self,
        mock_download,
        mock_delete_twilio,
        mock_strip,
        mock_upload,
        mock_consent,
        mock_resolver,
        setup_db,
    ):
        db = setup_db
        clara = db.query(Child).filter(Child.name == "Clara").first()

        mock_download.return_value = (b"raw", "image/jpeg")
        mock_strip.return_value = b"clean"
        mock_consent.return_value = MagicMock()
        mock_resolver.return_value = _ctx(child_names=["Clara"])

        resp = client.post(
            "/webhook/whatsapp",
            data={
                "From": "+15550001111",
                "Body": "Clara at lunch",
                "NumMedia": "1",
                "MediaUrl0": "https://api.twilio.com/x.jpg",
                "MediaContentType0": "image/jpeg",
            },
        )
        assert resp.status_code == 200
        assert "Saved 1 photo(s) for Clara" in resp.text

        photos = db.query(Photo).all()
        assert len(photos) == 1
        assert photos[0].child_id == clara.id
        assert photos[0].caption == "Clara at lunch"
        assert db.query(PendingPhoto).count() == 0

    @patch("backend.routers.whatsapp.resolve_photo_context", new_callable=AsyncMock)
    @patch("backend.routers.whatsapp.get_child_for_processing")
    @patch("backend.routers.whatsapp.upload_photo")
    @patch("backend.routers.whatsapp.strip_exif")
    @patch("backend.routers.whatsapp.delete_twilio_media_with_retry", new_callable=AsyncMock)
    @patch("backend.routers.whatsapp.download_twilio_media", new_callable=AsyncMock)
    def test_two_named_children_share_one_s3_object(
        self,
        mock_download,
        mock_delete_twilio,
        mock_strip,
        mock_upload,
        mock_consent,
        mock_resolver,
        setup_db,
    ):
        db = setup_db
        mock_download.return_value = (b"raw", "image/jpeg")
        mock_strip.return_value = b"clean"
        mock_consent.return_value = MagicMock()
        mock_resolver.return_value = _ctx(child_names=["Clara", "Emi"])

        resp = client.post(
            "/webhook/whatsapp",
            data={
                "From": "+15550001111",
                "Body": "Clara and Emi reading",
                "NumMedia": "1",
                "MediaUrl0": "https://api.twilio.com/x.jpg",
                "MediaContentType0": "image/jpeg",
            },
        )
        assert resp.status_code == 200
        assert "Saved 1 photo(s) for Clara, Emi" in resp.text

        photos = db.query(Photo).all()
        # One S3 object, two Photo rows (one per child) — same s3_key
        assert len(photos) == 2
        assert len({p.s3_key for p in photos}) == 1
        names = sorted(
            db.query(Child.name).filter(Child.id.in_([p.child_id for p in photos])).all()
        )
        assert [n[0] for n in names] == ["Clara", "Emi"]

    @patch("backend.routers.whatsapp.resolve_photo_context", new_callable=AsyncMock)
    @patch("backend.routers.whatsapp.get_child_for_processing")
    @patch("backend.routers.whatsapp.upload_photo")
    @patch("backend.routers.whatsapp.strip_exif")
    @patch("backend.routers.whatsapp.delete_twilio_media_with_retry", new_callable=AsyncMock)
    @patch("backend.routers.whatsapp.download_twilio_media", new_callable=AsyncMock)
    def test_everyone_caption_fans_out_to_room(
        self,
        mock_download,
        mock_delete_twilio,
        mock_strip,
        mock_upload,
        mock_consent,
        mock_resolver,
        setup_db,
    ):
        db = setup_db
        mock_download.return_value = (b"raw", "image/jpeg")
        mock_strip.return_value = b"clean"
        mock_consent.return_value = MagicMock()
        mock_resolver.return_value = _ctx(applies_to_all=True)

        resp = client.post(
            "/webhook/whatsapp",
            data={
                "From": "+15550001111",
                "Body": "everyone at the playground",
                "NumMedia": "1",
                "MediaUrl0": "https://api.twilio.com/x.jpg",
                "MediaContentType0": "image/jpeg",
            },
        )
        assert resp.status_code == 200
        assert "Saved 1 photo(s) for everyone" in resp.text

        # 3 active kids in the teacher's room → 3 rows
        assert db.query(Photo).count() == 3
        assert db.query(PendingPhoto).count() == 0


# ─── Batch upload (multiple photos in one webhook) ─────────────


class TestMultiMediaWebhook:
    @patch("backend.routers.whatsapp.resolve_photo_context", new_callable=AsyncMock)
    @patch("backend.routers.whatsapp.get_child_for_processing")
    @patch("backend.routers.whatsapp.upload_photo")
    @patch("backend.routers.whatsapp.strip_exif")
    @patch("backend.routers.whatsapp.delete_twilio_media_with_retry", new_callable=AsyncMock)
    @patch("backend.routers.whatsapp.download_twilio_media", new_callable=AsyncMock)
    def test_three_photos_one_child(
        self,
        mock_download,
        mock_delete_twilio,
        mock_strip,
        mock_upload,
        mock_consent,
        mock_resolver,
        setup_db,
    ):
        db = setup_db
        mock_download.return_value = (b"raw", "image/jpeg")
        mock_strip.return_value = b"clean"
        mock_consent.return_value = MagicMock()
        mock_resolver.return_value = _ctx(child_names=["Lola"])

        resp = client.post(
            "/webhook/whatsapp",
            data={
                "From": "+15550001111",
                "Body": "Lola at the sand table",
                "NumMedia": "3",
                "MediaUrl0": "https://api.twilio.com/a.jpg",
                "MediaUrl1": "https://api.twilio.com/b.jpg",
                "MediaUrl2": "https://api.twilio.com/c.jpg",
                "MediaContentType0": "image/jpeg",
                "MediaContentType1": "image/jpeg",
                "MediaContentType2": "image/jpeg",
            },
        )
        assert resp.status_code == 200
        assert "Saved 3 photo(s) for Lola" in resp.text

        photos = db.query(Photo).all()
        assert len(photos) == 3
        # Each photo gets a fresh s3_key
        assert len({p.s3_key for p in photos}) == 3
        lola = db.query(Child).filter(Child.name == "Lola").first()
        assert all(p.child_id == lola.id for p in photos)

    @patch("backend.routers.whatsapp.upload_photo")
    @patch("backend.routers.whatsapp.strip_exif")
    @patch("backend.routers.whatsapp.delete_twilio_media_with_retry", new_callable=AsyncMock)
    @patch("backend.routers.whatsapp.download_twilio_media", new_callable=AsyncMock)
    def test_new_batch_count_ignores_stale_pending(
        self, mock_download, mock_delete_twilio, mock_strip, mock_upload, setup_db
    ):
        """If the teacher abandoned an earlier batch (rows lingering in
        PendingPhoto until the 30-min TTL), a fresh upload should only
        report the count of THIS batch — not 'Got 4' when they sent 2.
        """
        db = setup_db
        center = db.query(Center).first()
        teacher = db.query(Teacher).first()

        # Two stale pending photos from a previous, unresolved batch.
        for s3 in ("pending/stale1.jpg", "pending/stale2.jpg"):
            db.add(
                PendingPhoto(
                    id=uuid.uuid4(),
                    center_id=center.id,
                    teacher_id=teacher.id,
                    s3_temp_key=s3,
                    content_type="image/jpeg",
                    expires_at=datetime.now(UTC) + timedelta(minutes=25),
                )
            )
        db.commit()

        mock_download.return_value = (b"raw", "image/jpeg")
        mock_strip.return_value = b"clean"

        # Teacher now uploads 2 fresh photos.
        resp = client.post(
            "/webhook/whatsapp",
            data={
                "From": "+15550001111",
                "Body": "",
                "NumMedia": "2",
                "MediaUrl0": "https://api.twilio.com/a.jpg",
                "MediaUrl1": "https://api.twilio.com/b.jpg",
                "MediaContentType0": "image/jpeg",
                "MediaContentType1": "image/jpeg",
            },
        )
        assert resp.status_code == 200
        # Count is THIS batch only (2), not stale + new (4).
        assert "Got 2 photo" in resp.text
        # All 4 rows physically exist; only the 2 fresh ones are reported.
        assert db.query(PendingPhoto).count() == 4

    @patch("backend.routers.whatsapp.resolve_photo_context", new_callable=AsyncMock)
    @patch("backend.routers.whatsapp.get_child_for_processing")
    @patch("backend.routers.whatsapp.delete_s3_object")
    @patch("backend.routers.whatsapp.upload_photo")
    @patch("backend.routers.whatsapp.strip_exif")
    @patch("backend.routers.whatsapp.delete_twilio_media_with_retry", new_callable=AsyncMock)
    @patch("backend.routers.whatsapp.download_twilio_media", new_callable=AsyncMock)
    @patch("backend.routers.whatsapp.download_from_s3")
    def test_reply_only_assigns_current_batch_not_stale(
        self,
        mock_download_s3,
        mock_download_twilio,
        mock_delete_twilio,
        mock_strip,
        mock_upload,
        mock_delete_s3,
        mock_consent,
        mock_resolver,
        setup_db,
    ):
        """Stale pending photos from a previous abandoned batch must not get
        captioned with the new batch's reply."""
        db = setup_db
        center = db.query(Center).first()
        teacher = db.query(Teacher).first()

        # Stale pending photo, well before the new batch starts.
        stale = PendingPhoto(
            id=uuid.uuid4(),
            center_id=center.id,
            teacher_id=teacher.id,
            s3_temp_key="pending/stale.jpg",
            content_type="image/jpeg",
            expires_at=datetime.now(UTC) + timedelta(minutes=25),
        )
        db.add(stale)
        db.commit()
        # Force created_at to be older than the upcoming batch.
        stale.created_at = datetime.now(UTC) - timedelta(minutes=10)
        db.commit()

        mock_download_twilio.return_value = (b"raw", "image/jpeg")
        mock_strip.return_value = b"clean"
        mock_download_s3.return_value = b"clean"
        mock_consent.return_value = MagicMock()
        mock_resolver.return_value = _ctx(child_names=["Clara"])

        # New batch: 1 fresh photo.
        client.post(
            "/webhook/whatsapp",
            data={
                "From": "+15550001111",
                "Body": "",
                "NumMedia": "1",
                "MediaUrl0": "https://api.twilio.com/x.jpg",
                "MediaContentType0": "image/jpeg",
            },
        )

        # Teacher replies. Only the fresh photo should be assigned to Clara —
        # the stale one stays pending (will be GC'd by the 30-min TTL job).
        resp = client.post(
            "/webhook/whatsapp",
            data={
                "From": "+15550001111",
                "Body": "Clara at the table",
                "NumMedia": "0",
            },
        )
        assert resp.status_code == 200
        assert "Saved 1 photo(s) for Clara" in resp.text
        # 1 final Photo row, stale pending row preserved.
        assert db.query(Photo).count() == 1
        assert db.query(PendingPhoto).count() == 1
        assert db.query(PendingPhoto).first().s3_temp_key == "pending/stale.jpg"

    @patch("backend.routers.whatsapp.upload_photo")
    @patch("backend.routers.whatsapp.strip_exif")
    @patch("backend.routers.whatsapp.delete_twilio_media_with_retry", new_callable=AsyncMock)
    @patch("backend.routers.whatsapp.download_twilio_media", new_callable=AsyncMock)
    def test_consecutive_bare_photos_only_prompt_once(
        self, mock_download, mock_delete_twilio, mock_strip, mock_upload, setup_db
    ):
        """A WhatsApp gallery batch arrives as N separate webhooks. The first
        should prompt the teacher; the rest should be silent (empty TwiML)
        so the teacher isn't spammed with N copies of the same prompt.
        """
        db = setup_db
        mock_download.return_value = (b"raw", "image/jpeg")
        mock_strip.return_value = b"clean"

        def post_one(idx, sid):
            return client.post(
                "/webhook/whatsapp",
                data={
                    "From": "+15550001111",
                    "Body": "",
                    "NumMedia": "1",
                    "MediaUrl0": f"https://api.twilio.com/p{idx}.jpg",
                    "MediaContentType0": "image/jpeg",
                    "MessageSid": sid,
                },
            )

        first = post_one(0, "SM1")
        second = post_one(1, "SM2")
        third = post_one(2, "SM3")

        assert "Got 1 photo" in first.text
        # 2nd + 3rd photos: bot stays silent — empty TwiML <Response/>
        for r in (second, third):
            assert r.status_code == 200
            assert "Got" not in r.text
            assert r.text.strip().endswith("<Response/>")

        # All 3 photos are queued; one prompt sent.
        assert db.query(PendingPhoto).count() == 3

    @patch("backend.routers.whatsapp.upload_photo")
    @patch("backend.routers.whatsapp.strip_exif")
    @patch("backend.routers.whatsapp.delete_twilio_media_with_retry", new_callable=AsyncMock)
    @patch("backend.routers.whatsapp.download_twilio_media", new_callable=AsyncMock)
    def test_two_photos_no_caption_park_as_pending(
        self,
        mock_download,
        mock_delete_twilio,
        mock_strip,
        mock_upload,
        setup_db,
    ):
        db = setup_db
        mock_download.return_value = (b"raw", "image/jpeg")
        mock_strip.return_value = b"clean"

        resp = client.post(
            "/webhook/whatsapp",
            data={
                "From": "+15550001111",
                "Body": "",
                "NumMedia": "2",
                "MediaUrl0": "https://api.twilio.com/a.jpg",
                "MediaUrl1": "https://api.twilio.com/b.jpg",
                "MediaContentType0": "image/jpeg",
                "MediaContentType1": "image/jpeg",
            },
        )
        assert resp.status_code == 200
        assert "Got 2 photo(s)" in resp.text
        # Prompt asks for both the names AND the description
        text_lower = resp.text.lower()
        assert "who" in text_lower
        assert "happening" in text_lower or "what's" in text_lower
        assert db.query(PendingPhoto).count() == 2
        assert db.query(Photo).count() == 0


# ─── Follow-up reply resolves pending photos ───────────────────


class TestFollowupReply:
    @patch("backend.routers.whatsapp.resolve_photo_context", new_callable=AsyncMock)
    @patch("backend.routers.whatsapp.get_child_for_processing")
    @patch("backend.routers.whatsapp.delete_s3_object")
    @patch("backend.routers.whatsapp.upload_photo")
    @patch("backend.routers.whatsapp.download_from_s3")
    def test_text_reply_with_names_applies_pending(
        self,
        mock_download_s3,
        mock_upload,
        mock_delete_s3,
        mock_consent,
        mock_resolver,
        setup_db,
    ):
        db = setup_db
        center = db.query(Center).first()
        teacher = db.query(Teacher).first()

        # Two photos pending from a previous Twilio webhook
        for s3 in ("pending/a.jpg", "pending/b.jpg"):
            db.add(
                PendingPhoto(
                    id=uuid.uuid4(),
                    center_id=center.id,
                    teacher_id=teacher.id,
                    s3_temp_key=s3,
                    content_type="image/jpeg",
                    expires_at=datetime.now(UTC) + timedelta(minutes=30),
                )
            )
        db.commit()

        mock_download_s3.return_value = b"clean"
        mock_consent.return_value = MagicMock()
        mock_resolver.return_value = _ctx(child_names=["Clara", "Emi"])

        resp = client.post(
            "/webhook/whatsapp",
            data={
                "From": "+15550001111",
                "Body": "Clara and Emi",
                "NumMedia": "0",
            },
        )
        assert resp.status_code == 200
        assert "Saved 2 photo(s) for Clara, Emi" in resp.text

        # 2 photos × 2 children = 4 Photo rows
        assert db.query(Photo).count() == 4
        assert db.query(PendingPhoto).count() == 0
        # Each S3 temp key got deleted
        assert mock_delete_s3.call_count == 2

    @patch("backend.routers.whatsapp.resolve_photo_context", new_callable=AsyncMock)
    @patch("backend.routers.whatsapp.get_child_for_processing")
    @patch("backend.routers.whatsapp.delete_s3_object")
    @patch("backend.routers.whatsapp.upload_photo")
    @patch("backend.routers.whatsapp.download_from_s3")
    def test_everyone_reply_fans_out_to_room(
        self,
        mock_download_s3,
        mock_upload,
        mock_delete_s3,
        mock_consent,
        mock_resolver,
        setup_db,
    ):
        db = setup_db
        center = db.query(Center).first()
        teacher = db.query(Teacher).first()

        db.add(
            PendingPhoto(
                id=uuid.uuid4(),
                center_id=center.id,
                teacher_id=teacher.id,
                s3_temp_key="pending/only.jpg",
                content_type="image/jpeg",
                expires_at=datetime.now(UTC) + timedelta(minutes=30),
            )
        )
        db.commit()

        mock_download_s3.return_value = b"clean"
        mock_consent.return_value = MagicMock()
        mock_resolver.return_value = _ctx(applies_to_all=True)

        resp = client.post(
            "/webhook/whatsapp",
            data={
                "From": "+15550001111",
                "Body": "everyone",
                "NumMedia": "0",
            },
        )
        assert resp.status_code == 200
        assert "Saved 1 photo(s) for everyone" in resp.text
        # 1 photo × 3 children in the room
        assert db.query(Photo).count() == 3
        assert db.query(PendingPhoto).count() == 0

    @patch("backend.routers.whatsapp.resolve_photo_context", new_callable=AsyncMock)
    @patch("backend.routers.whatsapp.get_child_for_processing")
    @patch("backend.routers.whatsapp.delete_s3_object")
    @patch("backend.routers.whatsapp.upload_photo")
    @patch("backend.routers.whatsapp.download_from_s3")
    def test_followup_description_becomes_caption(
        self,
        mock_download_s3,
        mock_upload,
        mock_delete_s3,
        mock_consent,
        mock_resolver,
        setup_db,
    ):
        """The teacher's reply (which both names the kids AND describes the
        activity) should be saved as the photo caption when the pending
        photo had no caption of its own.
        """
        db = setup_db
        center = db.query(Center).first()
        teacher = db.query(Teacher).first()

        db.add(
            PendingPhoto(
                id=uuid.uuid4(),
                center_id=center.id,
                teacher_id=teacher.id,
                s3_temp_key="pending/x.jpg",
                caption=None,  # bare photo upload — caption comes from reply
                content_type="image/jpeg",
                expires_at=datetime.now(UTC) + timedelta(minutes=30),
            )
        )
        db.commit()

        mock_download_s3.return_value = b"clean"
        mock_consent.return_value = MagicMock()
        mock_resolver.return_value = _ctx(child_names=["Clara"])

        description = "Clara painting a rainbow at the art table"
        resp = client.post(
            "/webhook/whatsapp",
            data={
                "From": "+15550001111",
                "Body": description,
                "NumMedia": "0",
            },
        )
        assert resp.status_code == 200
        photos = db.query(Photo).all()
        assert len(photos) == 1
        assert photos[0].caption == description

    @patch("backend.routers.whatsapp.resolve_photo_context", new_callable=AsyncMock)
    @patch("backend.routers.whatsapp.get_child_for_processing")
    @patch("backend.routers.whatsapp.delete_s3_object")
    @patch("backend.routers.whatsapp.upload_photo")
    @patch("backend.routers.whatsapp.download_from_s3")
    def test_everyone_works_for_pending_consent_kids_in_pilot(
        self,
        mock_download_s3,
        mock_upload,
        mock_delete_s3,
        mock_consent,
        mock_resolver,
        setup_db,
    ):
        """Phase 1 pilot: children typically sit in PENDING_CONSENT until the
        parent flow is enabled. 'everyone' should still fan out to them — we
        only exclude UNENROLLED.
        """
        db = setup_db
        center = db.query(Center).first()
        teacher = db.query(Teacher).first()

        # Force every child into PENDING_CONSENT (the realistic pilot state).
        for c in db.query(Child).all():
            c.status = "PENDING_CONSENT"
        db.commit()

        db.add(
            PendingPhoto(
                id=uuid.uuid4(),
                center_id=center.id,
                teacher_id=teacher.id,
                s3_temp_key="pending/x.jpg",
                content_type="image/jpeg",
                expires_at=datetime.now(UTC) + timedelta(minutes=30),
            )
        )
        db.commit()

        mock_download_s3.return_value = b"clean"
        mock_consent.return_value = MagicMock()
        mock_resolver.return_value = _ctx(applies_to_all=True)

        resp = client.post(
            "/webhook/whatsapp",
            data={
                "From": "+15550001111",
                "Body": "everyone is playing cards",
                "NumMedia": "0",
            },
        )
        assert resp.status_code == 200
        assert "Saved 1 photo(s) for everyone" in resp.text
        # 3 kids in the room → 3 Photo rows
        assert db.query(Photo).count() == 3

    @patch("backend.routers.whatsapp.extract_events", new_callable=AsyncMock)
    @patch("backend.routers.whatsapp.resolve_photo_context", new_callable=AsyncMock)
    def test_event_narrative_falls_through_to_extraction(
        self, mock_resolver, mock_extract, setup_db
    ):
        """When the teacher replies with what looks like an event log, the
        photo-context resolver returns no context and the message routes
        to normal event extraction — pending photos are left alone."""
        db = setup_db
        center = db.query(Center).first()
        teacher = db.query(Teacher).first()

        db.add(
            PendingPhoto(
                id=uuid.uuid4(),
                center_id=center.id,
                teacher_id=teacher.id,
                s3_temp_key="pending/x.jpg",
                content_type="image/jpeg",
                expires_at=datetime.now(UTC) + timedelta(minutes=30),
            )
        )
        db.commit()

        # Resolver returns no context — caller falls through.
        mock_resolver.return_value = _ctx()
        # Extractor returns no events (we only care it was *called*).
        mock_extract.return_value = ([], [])

        resp = client.post(
            "/webhook/whatsapp",
            data={
                "From": "+15550001111",
                "Body": "Clara had a great nap and then ate her snack",
                "NumMedia": "0",
            },
        )
        assert resp.status_code == 200
        mock_extract.assert_called_once()
        # Pending photo untouched
        assert db.query(PendingPhoto).count() == 1
        assert db.query(Photo).count() == 0
