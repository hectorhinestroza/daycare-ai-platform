"""Whisper API transcription service (Issue #2)."""

import io
import logging

from openai import OpenAI

from backend.config import get_settings

logger = logging.getLogger(__name__)


def get_openai_client() -> OpenAI:
    settings = get_settings()
    return OpenAI(api_key=settings.openai_api_key)


async def transcribe_audio(audio_bytes: bytes, filename: str = "audio.ogg") -> str:
    """Transcribe audio bytes using OpenAI Whisper API.

    Args:
        audio_bytes: Raw audio file bytes (.ogg or .mp4)
        filename: Original filename with extension for format detection

    Returns:
        Transcript string

    Raises:
        ValueError: If audio is empty or transcription fails
    """
    if not audio_bytes:
        raise ValueError("Empty audio data received")

    settings = get_settings()
    client = OpenAI(api_key=settings.openai_api_key)

    logger.info(f"Transcribing audio: {filename} ({len(audio_bytes)} bytes)")

    try:
        audio_file = io.BytesIO(audio_bytes)
        audio_file.name = filename

        transcript = client.audio.transcriptions.create(
            model="whisper-1",
            file=audio_file,
            response_format="text",
        )

        transcript_text = transcript.strip()

        if not transcript_text:
            raise ValueError("Whisper returned empty transcript")

        logger.info(
            f"Transcription complete: {len(transcript_text)} chars"
        )
        return transcript_text

    except Exception as e:
        logger.error(f"Transcription failed: {e}")
        raise
