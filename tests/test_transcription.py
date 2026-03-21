"""Tests for the transcription service (Issue #2)."""

import pytest
from unittest.mock import patch, MagicMock
from backend.services.transcription import transcribe_audio


class TestTranscribeAudio:
    """Test Whisper transcription service."""

    @pytest.mark.asyncio
    @patch("backend.services.transcription.OpenAI")
    async def test_successful_transcription(self, mock_openai_class):
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client
        mock_client.audio.transcriptions.create.return_value = (
            "Jason ate mac and cheese for lunch and took a nap at noon."
        )

        result = await transcribe_audio(b"fake_audio_bytes", "test.ogg")

        assert result == "Jason ate mac and cheese for lunch and took a nap at noon."
        mock_client.audio.transcriptions.create.assert_called_once()

    @pytest.mark.asyncio
    async def test_empty_audio_raises(self):
        with pytest.raises(ValueError, match="Empty audio data"):
            await transcribe_audio(b"", "test.ogg")

    @pytest.mark.asyncio
    @patch("backend.services.transcription.OpenAI")
    async def test_empty_transcript_raises(self, mock_openai_class):
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client
        mock_client.audio.transcriptions.create.return_value = "   "

        with pytest.raises(ValueError, match="empty transcript"):
            await transcribe_audio(b"fake_audio", "test.ogg")

    @pytest.mark.asyncio
    @patch("backend.services.transcription.OpenAI")
    async def test_api_failure_propagates(self, mock_openai_class):
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client
        mock_client.audio.transcriptions.create.side_effect = Exception("API down")

        with pytest.raises(Exception, match="API down"):
            await transcribe_audio(b"fake_audio", "test.ogg")
