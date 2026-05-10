"""Tests for delete_twilio_media_with_retry (pilot §3.4)."""

import json
import logging
from unittest.mock import AsyncMock, patch

import pytest

from backend.utils.media import (
    _hash_url,
    delete_twilio_media_with_retry,
)


URL = "https://api.twilio.com/2010-04-01/Accounts/AC1/Messages/MM1/Media/ME1"


@pytest.mark.asyncio
async def test_succeeds_on_first_attempt(caplog):
    with patch(
        "backend.utils.media.delete_twilio_media", new_callable=AsyncMock
    ) as mock_delete:
        mock_delete.return_value = None

        with caplog.at_level(logging.INFO, logger="backend.utils.media"):
            await delete_twilio_media_with_retry(URL, base_delay_s=0)

    assert mock_delete.call_count == 1
    success_logs = [
        json.loads(r.message) for r in caplog.records
        if "twilio.media_deletion.succeeded" in r.message
    ]
    assert len(success_logs) == 1
    assert success_logs[0]["attempt"] == 1
    assert success_logs[0]["url_hash"] == _hash_url(URL)


@pytest.mark.asyncio
async def test_succeeds_on_third_attempt(caplog):
    with patch(
        "backend.utils.media.delete_twilio_media", new_callable=AsyncMock
    ) as mock_delete:
        mock_delete.side_effect = [
            ConnectionError("blip 1"),
            ConnectionError("blip 2"),
            None,  # success
        ]

        with caplog.at_level(logging.INFO, logger="backend.utils.media"):
            await delete_twilio_media_with_retry(URL, base_delay_s=0)

    assert mock_delete.call_count == 3
    success_logs = [
        json.loads(r.message) for r in caplog.records
        if "twilio.media_deletion.succeeded" in r.message
    ]
    assert len(success_logs) == 1
    assert success_logs[0]["attempt"] == 3


@pytest.mark.asyncio
async def test_all_attempts_fail_logs_error(caplog):
    """All 3 attempts fail → ERROR-level structured log, no exception raised."""
    with patch(
        "backend.utils.media.delete_twilio_media", new_callable=AsyncMock
    ) as mock_delete:
        mock_delete.side_effect = ConnectionError("network down")

        with caplog.at_level(logging.ERROR, logger="backend.utils.media"):
            # Must not raise — fire-and-forget contract.
            await delete_twilio_media_with_retry(URL, base_delay_s=0)

    assert mock_delete.call_count == 3
    error_logs = [
        json.loads(r.message) for r in caplog.records
        if "twilio.media_deletion.failed" in r.message
    ]
    assert len(error_logs) == 1
    assert error_logs[0]["attempts"] == 3
    assert error_logs[0]["error_type"] == "ConnectionError"
    assert error_logs[0]["url_hash"] == _hash_url(URL)


@pytest.mark.asyncio
async def test_url_hash_never_logs_raw_url(caplog):
    """Twilio media URLs contain the account SID and message SID — must not appear in logs."""
    with patch(
        "backend.utils.media.delete_twilio_media", new_callable=AsyncMock
    ) as mock_delete:
        mock_delete.side_effect = ConnectionError("boom")

        with caplog.at_level(logging.INFO, logger="backend.utils.media"):
            await delete_twilio_media_with_retry(URL, base_delay_s=0)

    serialized = "\n".join(r.message for r in caplog.records)
    assert "AC1" not in serialized
    assert "MM1" not in serialized
    assert "ME1" not in serialized
    assert _hash_url(URL) in serialized


@pytest.mark.asyncio
async def test_max_attempts_is_configurable(caplog):
    with patch(
        "backend.utils.media.delete_twilio_media", new_callable=AsyncMock
    ) as mock_delete:
        mock_delete.side_effect = ConnectionError("boom")

        with caplog.at_level(logging.ERROR, logger="backend.utils.media"):
            await delete_twilio_media_with_retry(URL, max_attempts=5, base_delay_s=0)

    assert mock_delete.call_count == 5
