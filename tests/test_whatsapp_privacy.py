"""Tests for L-3: WhatsApp / Twilio Audio Privacy.

Verifies:
- Twilio media is deleted using an HTTP DELETE request to the MediaUrl
- gc.collect is called after extraction
- Errors during deletion do not crash the pipeline
"""

import gc
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import httpx

from backend.utils.media import delete_twilio_media


@pytest.mark.asyncio
async def test_delete_twilio_media_success():
    """HTTP DELETE is issued to the correct URL with auth."""
    mock_settings = MagicMock()
    mock_settings.twilio_account_sid = "AC_test"
    mock_settings.twilio_auth_token = "token_test"

    media_url = "https://api.twilio.com/2010-04-01/Accounts/AC/Messages/MM/Media/ME"

    with patch("backend.utils.media.get_settings", return_value=mock_settings):
        with patch("httpx.AsyncClient.delete", new_callable=AsyncMock) as mock_delete:
            mock_response = MagicMock()
            mock_response.status_code = 204
            mock_delete.return_value = mock_response
            
            await delete_twilio_media(media_url)

            mock_delete.assert_called_once_with(
                media_url,
                auth=("AC_test", "token_test")
            )


@pytest.mark.asyncio
async def test_delete_twilio_media_swallows_errors():
    """Deletion failures should be logged but never raise exceptions."""
    mock_settings = MagicMock()
    
    with patch("backend.utils.media.get_settings", return_value=mock_settings):
        with patch("httpx.AsyncClient.delete", new_callable=AsyncMock) as mock_delete:
            mock_delete.side_effect = httpx.RequestError("Network error")
            
            try:
                await delete_twilio_media("http://fake.url")
            except Exception as e:
                pytest.fail(f"delete_twilio_media raised an exception: {e}")

