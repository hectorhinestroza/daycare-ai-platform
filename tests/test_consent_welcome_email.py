"""Tests for the post-consent welcome email + parent-token mint.

When a parent submits the consent form, `submit_consent()` should:
  1. Activate the child (existing behavior — covered elsewhere).
  2. Mint a 1-year parent bearer token scoped to that child.
  3. Build a bootstrap URL with the configured `app_base_url`.
  4. Fire `send_parent_welcome_email` in a background thread.

The email send itself is mocked — we only care that the dispatch call
shape is right. Failures in the email path must NOT roll back the consent.
"""

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.main import app
from backend.storage.database import Base, get_db
from backend.storage.models import (
    Center,
    Child,
    ConsentToken,
    ParentContact,
    ParentalConsent,
    Teacher,
)
from backend.utils.auth_tokens import verify_token

engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture
def db():
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()

    def override_get_db():
        try:
            yield session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    yield session
    app.dependency_overrides.pop(get_db, None)
    Base.metadata.drop_all(bind=engine)
    session.close()


@pytest.fixture
def seeded(db):
    """Center + child in PENDING_CONSENT + primary parent + valid token."""
    center = Center(id=uuid.uuid4(), name="Tilly's Tots")
    db.add(center)
    db.commit()

    # The schema requires at least a teacher for FK integrity in some
    # downstream queries; not strictly needed here but harmless.
    db.add(Teacher(
        id=uuid.uuid4(), center_id=center.id, name="T", phone="+15550009999",
    ))
    db.commit()

    child = Child(
        id=uuid.uuid4(),
        center_id=center.id,
        name="Loie Sanders",
        status="PENDING_CONSENT",
    )
    db.add(child)
    db.commit()

    parent = ParentContact(
        id=uuid.uuid4(),
        center_id=center.id,
        child_id=child.id,
        name="Jane Sanders",
        email="jane@example.com",
        is_primary=True,
    )
    db.add(parent)
    db.commit()

    token = ConsentToken(
        id=uuid.uuid4(),
        center_id=center.id,
        child_id=child.id,
        parent_id=parent.id,
        token=uuid.uuid4(),
        expires_at=datetime.now(timezone.utc) + timedelta(days=7),
    )
    db.add(token)
    db.commit()

    return {"center": center, "child": child, "parent": parent, "token": token}


client = TestClient(app)


def _submit(token_uuid):
    return client.post(
        f"/api/consent/{token_uuid}",
        json={
            "consent_daily_reports": True,
            "consent_photos": True,
            "consent_audio_processing": True,
            "consent_billing_data": True,
            "digital_signature": "Jane Sanders",
        },
    )


class TestPostConsentWelcomeEmail:
    @patch("backend.routers.consent.threading.Thread")
    @patch(
        "backend.routers.consent.send_parent_welcome_email",
        new_callable=AsyncMock,
    )
    def test_welcome_email_dispatched_with_bootstrap_url(
        self, mock_send, mock_thread, seeded, db
    ):
        # Force the threaded send to run inline so we can inspect the call.
        def run_target(target=None, daemon=None):
            t = MagicMock()
            # FastAPI's TestClient is sync; the _send closure calls
            # asyncio.run which then awaits our AsyncMock — fine.
            t.start.side_effect = lambda: target()
            return t
        mock_thread.side_effect = run_target

        resp = _submit(seeded["token"].token)
        assert resp.status_code == 201

        # Welcome email was awaited with the expected kwargs
        assert mock_send.await_count == 1
        kwargs = mock_send.await_args.kwargs
        assert kwargs["to_email"] == "jane@example.com"
        assert kwargs["parent_name"] == "Jane Sanders"
        assert kwargs["child_name"] == "Loie"  # first name only
        assert kwargs["center_name"] == "Tilly's Tots"
        # The bootstrap URL must point at /app and carry a real signed token
        portal_url = kwargs["portal_url"]
        assert "/app?token=" in portal_url
        bearer = portal_url.split("token=", 1)[1]
        payload = verify_token(bearer, db)
        assert payload is not None
        assert payload.role == "parent"
        assert payload.sub == seeded["parent"].id
        assert payload.center_id == seeded["center"].id
        assert payload.child_ids == (seeded["child"].id,)
        # 1-year TTL → expiry is well over 360 days out
        days_until_expiry = (payload.expires_at - datetime.now(timezone.utc)).days
        assert 360 < days_until_expiry <= 366

    @patch("backend.routers.consent.threading.Thread")
    @patch(
        "backend.routers.consent.send_parent_welcome_email",
        new_callable=AsyncMock,
    )
    def test_consent_persists_even_if_welcome_email_throws(
        self, mock_send, mock_thread, seeded, db
    ):
        """If the email dispatch raises, the consent should still be
        recorded and the child should still flip to ACTIVE."""
        # Make the threaded send throw on .start()
        bad_thread = MagicMock()
        bad_thread.start.side_effect = RuntimeError("smtp down")
        mock_thread.return_value = bad_thread

        resp = _submit(seeded["token"].token)
        assert resp.status_code == 201
        assert resp.json()["child_status"] == "ACTIVE"

        # Consent + child status committed despite the email failure.
        db.refresh(seeded["child"])
        assert seeded["child"].status == "ACTIVE"
        assert (
            db.query(ParentalConsent)
            .filter(ParentalConsent.child_id == seeded["child"].id)
            .count() == 1
        )

    @patch("backend.routers.consent.threading.Thread")
    @patch(
        "backend.routers.consent.send_parent_welcome_email",
        new_callable=AsyncMock,
    )
    def test_skips_email_when_parent_has_no_email(
        self, mock_send, mock_thread, seeded, db
    ):
        """If the primary contact has no email, no welcome email is
        dispatched (no thread started, no AsyncMock awaited)."""
        seeded["parent"].email = None
        db.commit()

        resp = _submit(seeded["token"].token)
        assert resp.status_code == 201
        mock_thread.assert_not_called()
        mock_send.assert_not_awaited()
