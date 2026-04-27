"""Tests for the WhatsApp webhook endpoint (Issue #1 and #4).

Uses a TestClient with a mocked DB dependency to test teacher lookups and event persistence.
"""

import uuid
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.main import app
from backend.storage.database import Base, get_db
from backend.storage.models import Center, Event, Teacher
from schemas.events import BaseEvent, EventStatus, EventType

# In-memory DB for router testing
engine = create_engine(
    "sqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(autouse=True)
def setup_db():
    """Create fresh schema for each test and seed a teacher."""
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()

    # Override get_db to use this test session
    def override_get_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db

    # Seed data
    center = Center(id=uuid.uuid4(), name="Test Center")
    db.add(center)
    db.commit()

    teacher = Teacher(id=uuid.uuid4(), center_id=center.id, name="Test Teacher", phone="+1234567890")
    db.add(teacher)
    db.commit()

    yield db

    app.dependency_overrides.pop(get_db, None)
    Base.metadata.drop_all(bind=engine)
    db.close()


client = TestClient(app)


class TestCommandHandling:
    """Test /child and /classroom text commands."""

    def test_child_command_sets_context(self):
        # Commands don't require DB lookup right now, but we send a registered phone
        response = client.post(
            "/webhook/whatsapp",
            data={"From": "+1234567890", "Body": "/child Jason", "NumMedia": "0"},
        )
        assert response.status_code == 200
        assert "Context set to child: Jason" in response.text

    def test_classroom_command_sets_context(self):
        response = client.post(
            "/webhook/whatsapp",
            data={"From": "+1234567890", "Body": "/classroom Butterflies", "NumMedia": "0"},
        )
        assert response.status_code == 200
        assert "Context set to classroom: Butterflies" in response.text

    def test_unregistered_number_rejected(self):
        """Unregistered numbers are immediately rejected."""
        response = client.post(
            "/webhook/whatsapp",
            data={"From": "+9999999999", "Body": "Hello", "NumMedia": "0"},
        )
        assert response.status_code == 200
        assert "not registered" in response.text


class TestVoicePipeline:
    """Test voice memo → transcription → extraction → DB storage."""

    @patch("backend.routers.whatsapp.extract_events", new_callable=AsyncMock)
    @patch("backend.routers.whatsapp.transcribe_audio", new_callable=AsyncMock)
    @patch("backend.routers.whatsapp.download_twilio_media", new_callable=AsyncMock)
    def test_voice_memo_pipeline(self, mock_download, mock_transcribe, mock_extract, setup_db):
        db = setup_db
        center = db.query(Center).first()
        teacher = db.query(Teacher).first()

        mock_download.return_value = (b"fake_audio_data", "audio/ogg")
        mock_transcribe.return_value = "Jason ate mac and cheese for lunch"
        mock_extract.return_value = (
            [
                BaseEvent(
                    id=uuid.uuid4(),
                    center_id=str(center.id),
                    child_name="Jason",
                    event_type=EventType.FOOD,
                    confidence_score=0.95,
                    review_tier="teacher",
                    needs_director_review=False,
                    needs_review=False,
                    status=EventStatus.PENDING,
                    raw_transcript="Jason ate mac and cheese for lunch",
                )
            ],
            [],
        )

        response = client.post(
            "/webhook/whatsapp",
            data={
                "From": "+1234567890",
                "Body": "",
                "NumMedia": "1",
                "MediaUrl0": "https://api.twilio.com/media/test",
                "MediaContentType0": "audio/ogg",
            },
        )
        assert response.status_code == 200
        assert "Parsed 1 event" in response.text
        assert "Jason" in response.text

        # Verify it was saved to the DB
        saved_events = db.query(Event).all()
        assert len(saved_events) == 1
        assert saved_events[0].child_name == "Jason"
        assert saved_events[0].teacher_id == teacher.id

    @patch("backend.routers.whatsapp.extract_events", new_callable=AsyncMock)
    def test_text_extraction(self, mock_extract, setup_db):
        db = setup_db
        center = db.query(Center).first()

        mock_extract.return_value = (
            [
                BaseEvent(
                    id=uuid.uuid4(),
                    center_id=str(center.id),
                    child_name="Emma",
                    event_type=EventType.POTTY,
                    confidence_score=0.9,
                    review_tier="teacher",
                    needs_director_review=False,
                    needs_review=False,
                    status=EventStatus.PENDING,
                    raw_transcript="Successful potty for Emma",
                )
            ],
            [],
        )

        response = client.post(
            "/webhook/whatsapp",
            data={
                "From": "+1234567890",
                "Body": "Successful potty for Emma",
                "NumMedia": "0",
            },
        )
        assert response.status_code == 200
        assert "Parsed 1 event" in response.text

        # Verify DB save
        saved_events = db.query(Event).all()
        assert len(saved_events) == 1
        assert saved_events[0].event_type == "potty"
