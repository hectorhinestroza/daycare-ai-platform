"""Utility for downloading and deleting media files from Twilio."""
import asyncio
import hashlib
import logging
from typing import Optional

import httpx

from backend.config import get_settings
from backend.utils.safe_logging import safe_log

logger = logging.getLogger(__name__)


def _hash_url(media_url: str) -> str:
    """Short stable hash of a Twilio media URL for log correlation.
    Twilio URLs contain the account SID and the message/media SIDs, which
    are sensitive — we never log the raw URL."""
    return hashlib.sha256((media_url or "").encode()).hexdigest()[:12]


async def download_twilio_media(media_url: str) -> tuple[bytes, str]:
    """Download media from a Twilio media URL.

    Returns:
        Tuple of (file_bytes, content_type)
    """
    settings = get_settings()
    async with httpx.AsyncClient() as client:
        response = await client.get(
            media_url,
            auth=(settings.twilio_account_sid, settings.twilio_auth_token),
            follow_redirects=True,
        )
        response.raise_for_status()
        content_type = response.headers.get("content-type", "application/octet-stream")
        return response.content, content_type


async def delete_twilio_media(media_url: str) -> None:
    """Delete media from Twilio servers to enforce zero-retention.

    Single attempt; errors propagate. Use delete_twilio_media_with_retry
    for the production code path — fire-and-forget without retries can
    silently leave audio in Twilio's CDN, violating the legal_PRD.
    """
    settings = get_settings()
    if not media_url.startswith("https://api.twilio.com/"):
        safe_log(
            logger, "warning", "twilio.media_deletion.invalid_url",
            url_hash=_hash_url(media_url),
        )
        return

    async with httpx.AsyncClient() as client:
        response = await client.delete(
            media_url,
            auth=(settings.twilio_account_sid, settings.twilio_auth_token),
        )
        response.raise_for_status()


async def delete_twilio_media_with_retry(
    media_url: str,
    *,
    max_attempts: int = 3,
    base_delay_s: float = 1.0,
) -> None:
    """Delete Twilio media with exponential backoff. Compliance-critical:
    if all attempts fail, we log at ERROR level so Sentry picks it up.

    Backoff: 1s, 2s, 4s between attempts (max_attempts=3 → up to 7s total).

    Errors are never re-raised; this is fire-and-forget by design (caller
    typically schedules via asyncio.create_task). The webhook response
    must not be delayed by Twilio CDN issues, but the deletion failure
    must be observable.
    """
    url_hash = _hash_url(media_url)
    last_error: Optional[BaseException] = None

    for attempt in range(1, max_attempts + 1):
        try:
            await delete_twilio_media(media_url)
            safe_log(
                logger, "info", "twilio.media_deletion.succeeded",
                url_hash=url_hash, attempt=attempt,
            )
            return
        except Exception as e:
            last_error = e
            if attempt < max_attempts:
                delay = base_delay_s * (2 ** (attempt - 1))
                await asyncio.sleep(delay)

    # All attempts exhausted.
    safe_log(
        logger, "error", "twilio.media_deletion.failed",
        url_hash=url_hash,
        attempts=max_attempts,
        error_type=type(last_error).__name__ if last_error else "unknown",
    )
