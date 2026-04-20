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


async def delete_twilio_media(media_url: str) -> None:
    """Delete media from Twilio servers to enforce privacy.

    Errors are swallowed and logged, as deletion failures should not
    crash the main webhook pipeline.
    """
    import logging
    logger = logging.getLogger(__name__)
    
    settings = get_settings()
    # It must be a valid Twilio API URL to delete it via their media endpoint.
    # The URL from the webhook is something like:
    # https://api.twilio.com/2010-04-01/Accounts/{AC}/Messages/{MM}/Media/{ME}
    if not media_url.startswith("https://api.twilio.com/"):
        logger.warning(f"Cannot delete non-Twilio media URL: {media_url}")
        return

    try:
        async with httpx.AsyncClient() as client:
            response = await client.delete(
                media_url,
                auth=(settings.twilio_account_sid, settings.twilio_auth_token),
            )
            response.raise_for_status()
            logger.info(f"Successfully deleted Twilio media: {media_url}")
    except Exception as e:
        logger.error(f"Failed to delete Twilio media at {media_url}: {e}")
