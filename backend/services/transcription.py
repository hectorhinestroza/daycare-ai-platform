"""Whisper API transcription service (Issue #2)."""

import io
import logging
import time

from backend.utils.openai_client import get_openai_client
from backend.utils.safe_logging import safe_log

logger = logging.getLogger(__name__)


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

    client = get_openai_client()
    start = time.monotonic()

    try:
        audio_file = io.BytesIO(audio_bytes)
        audio_file.name = filename

        transcript = await client.audio.transcriptions.create(
            model="whisper-1",
            file=audio_file,
            response_format="text",
        )

        transcript_text = transcript.strip()

        if not transcript_text:
            raise ValueError("Whisper returned empty transcript")

        safe_log(
            logger, "info", "transcription.completed",
            duration_ms=int((time.monotonic() - start) * 1000),
            transcript_length=len(transcript_text),
            audio_bytes=len(audio_bytes),
        )
        return transcript_text

    except Exception as e:
        # Don't echo the exception message — Whisper errors are usually generic
        # but defensive scrubbing keeps prod logs PII-free even on edge cases.
        safe_log(
            logger, "error", "transcription.failed",
            duration_ms=int((time.monotonic() - start) * 1000),
            error_type=type(e).__name__,
        )
        raise
