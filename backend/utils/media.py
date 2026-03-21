"""Utility for downloading media files from Twilio."""

import httpx
from backend.config import get_settings


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
