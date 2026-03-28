"""Tests for the WhatsApp webhook endpoint (Issue #1)."""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, AsyncMock
from backend.main import app
from schemas.events import BaseEvent, EventType, EventStatus
from uuid import uuid4

client = TestClient(app)


class TestCommandHandling:
    """Test /child and /classroom text commands."""

    def test_child_command_sets_context(self):
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

    def test_child_command_empty_name(self):
        response = client.post(
            "/webhook/whatsapp",
            data={"From": "+1234567890", "Body": "/child ", "NumMedia": "0"},
        )
        assert response.status_code == 200
        assert "Usage" in response.text

    def test_fallback_message(self):
        response = client.post(
            "/webhook/whatsapp",
            data={"From": "+1234567890", "Body": "", "NumMedia": "0"},
        )
        assert response.status_code == 200
        assert "voice memo" in response.text


class TestVoicePipeline:
    """Test voice memo → transcription → extraction pipeline."""

    @patch("backend.routers.whatsapp.extract_events", new_callable=AsyncMock)
    @patch("backend.routers.whatsapp.transcribe_audio", new_callable=AsyncMock)
    @patch("backend.routers.whatsapp.download_twilio_media", new_callable=AsyncMock)
    def test_voice_memo_pipeline(self, mock_download, mock_transcribe, mock_extract):
        mock_download.return_value = (b"fake_audio_data", "audio/ogg")
        mock_transcribe.return_value = "Jason ate mac and cheese for lunch"
        mock_extract.return_value = [
            BaseEvent(
                id=uuid4(),
                center_id="center_dev_001",
                child_name="Jason",
                event_type=EventType.MEAL,
                confidence_score=0.95,
                review_tier="teacher",
                needs_director_review=False,
                needs_review=False,
                status=EventStatus.PENDING,
                raw_transcript="Jason ate mac and cheese for lunch",
            )
        ]

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

        mock_download.assert_called_once()
        mock_transcribe.assert_called_once()
        mock_extract.assert_called_once()

    @patch("backend.routers.whatsapp.extract_events", new_callable=AsyncMock)
    @patch("backend.routers.whatsapp.transcribe_audio", new_callable=AsyncMock)
    @patch("backend.routers.whatsapp.download_twilio_media", new_callable=AsyncMock)
    def test_voice_memo_with_needs_review(self, mock_download, mock_transcribe, mock_extract):
        mock_download.return_value = (b"fake_audio", "audio/ogg")
        mock_transcribe.return_value = "Someone had a nap"
        mock_extract.return_value = [
            BaseEvent(
                id=uuid4(),
                center_id="center_dev_001",
                child_name="Unknown",
                event_type=EventType.NAP,
                confidence_score=0.3,
                review_tier="director",
                needs_director_review=True,
                needs_review=True,
                status=EventStatus.PENDING,
                raw_transcript="Someone had a nap",
            )
        ]

        response = client.post(
            "/webhook/whatsapp",
            data={
                "From": "+1111111111",
                "Body": "",
                "NumMedia": "1",
                "MediaUrl0": "https://api.twilio.com/media/test2",
                "MediaContentType0": "audio/ogg",
            },
        )
        assert response.status_code == 200
        assert "flagged for review" in response.text

    @patch("backend.routers.whatsapp.download_twilio_media", new_callable=AsyncMock)
    def test_voice_memo_pipeline_failure(self, mock_download):
        mock_download.side_effect = Exception("Download failed")

        response = client.post(
            "/webhook/whatsapp",
            data={
                "From": "+1234567890",
                "Body": "",
                "NumMedia": "1",
                "MediaUrl0": "https://api.twilio.com/media/fail",
                "MediaContentType0": "audio/ogg",
            },
        )
        assert response.status_code == 200
        assert "trouble processing" in response.text


class TestPhotoHandling:
    """Test photo reception."""

    def test_photo_received(self):
        response = client.post(
            "/webhook/whatsapp",
            data={
                "From": "+1234567890",
                "Body": "Art time!",
                "NumMedia": "1",
                "MediaUrl0": "https://api.twilio.com/media/photo1",
                "MediaContentType0": "image/jpeg",
            },
        )
        assert response.status_code == 200
        assert "Photo received" in response.text
        assert "Art time!" in response.text


class TestTextExtraction:
    """Test plain text message extraction."""

    @patch("backend.routers.whatsapp.extract_events", new_callable=AsyncMock)
    def test_text_extraction(self, mock_extract):
        mock_extract.return_value = [
            BaseEvent(
                id=uuid4(),
                center_id="center_dev_001",
                child_name="Emma",
                event_type=EventType.DIAPER,
                confidence_score=0.9,
                review_tier="teacher",
                needs_director_review=False,
                needs_review=False,
                status=EventStatus.PENDING,
                raw_transcript="Emma had a diaper change at 2pm",
            )
        ]

        response = client.post(
            "/webhook/whatsapp",
            data={
                "From": "+1234567890",
                "Body": "Emma had a diaper change at 2pm",
                "NumMedia": "0",
            },
        )
        assert response.status_code == 200
        assert "Parsed 1 event" in response.text
