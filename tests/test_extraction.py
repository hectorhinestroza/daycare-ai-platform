"""Tests for the GPT-4o extraction service (Issue #3)."""

import json
import pytest
from unittest.mock import patch, MagicMock
from backend.services.extraction import extract_events
from schemas.events import EventType


class TestExtractEvents:
    """Test GPT-4o structured event extraction."""

    @pytest.mark.asyncio
    @patch("backend.services.extraction.OpenAI")
    async def test_single_event_extraction(self, mock_openai_class):
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client

        mock_response = MagicMock()
        mock_response.choices[0].message.content = json.dumps({
            "events": [
                {
                    "event_type": "MEAL",
                    "child_name": "Jason",
                    "event_time": None,
                    "needs_review": False,
                    "details": "Ate mac and cheese for lunch",
                }
            ]
        })
        mock_client.chat.completions.create.return_value = mock_response

        events = await extract_events(
            transcript="Jason ate mac and cheese for lunch",
            center_id="center_001",
        )

        assert len(events) == 1
        assert events[0].child_name == "Jason"
        assert events[0].event_type == EventType.MEAL
        assert events[0].center_id == "center_001"
        assert events[0].needs_review is False

    @pytest.mark.asyncio
    @patch("backend.services.extraction.OpenAI")
    async def test_multiple_events_extraction(self, mock_openai_class):
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client

        mock_response = MagicMock()
        mock_response.choices[0].message.content = json.dumps({
            "events": [
                {"event_type": "MEAL", "child_name": "Jason", "needs_review": False},
                {"event_type": "NAP", "child_name": "Jason", "needs_review": False},
                {"event_type": "ACTIVITY", "child_name": "Emma", "needs_review": False},
            ]
        })
        mock_client.chat.completions.create.return_value = mock_response

        events = await extract_events("Jason had lunch, napped. Emma did art.", "c1")

        assert len(events) == 3
        assert events[0].event_type == EventType.MEAL
        assert events[1].event_type == EventType.NAP
        assert events[2].child_name == "Emma"

    @pytest.mark.asyncio
    @patch("backend.services.extraction.OpenAI")
    async def test_ambiguous_event_needs_review(self, mock_openai_class):
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client

        mock_response = MagicMock()
        mock_response.choices[0].message.content = json.dumps({
            "events": [
                {"event_type": "NAP", "child_name": "Someone", "needs_review": True},
            ]
        })
        mock_client.chat.completions.create.return_value = mock_response

        events = await extract_events("someone took a nap", "c1")

        assert len(events) == 1
        assert events[0].needs_review is True

    @pytest.mark.asyncio
    @patch("backend.services.extraction.OpenAI")
    async def test_temperature_zero(self, mock_openai_class):
        """Verify temperature=0 is always used (deterministic)."""
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client

        mock_response = MagicMock()
        mock_response.choices[0].message.content = json.dumps({"events": []})
        mock_client.chat.completions.create.return_value = mock_response

        await extract_events("test", "c1")

        call_kwargs = mock_client.chat.completions.create.call_args
        assert call_kwargs.kwargs["temperature"] == 0

    @pytest.mark.asyncio
    @patch("backend.services.extraction.OpenAI")
    async def test_child_name_context(self, mock_openai_class):
        """Verify child_name context is passed to GPT-4o."""
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client

        mock_response = MagicMock()
        mock_response.choices[0].message.content = json.dumps({
            "events": [{"event_type": "MEAL", "child_name": "Jason", "needs_review": False}]
        })
        mock_client.chat.completions.create.return_value = mock_response

        await extract_events("had lunch", "c1", child_name="Jason")

        call_kwargs = mock_client.chat.completions.create.call_args
        user_msg = call_kwargs.kwargs["messages"][1]["content"]
        assert "Jason" in user_msg

    @pytest.mark.asyncio
    async def test_empty_transcript_raises(self):
        with pytest.raises(ValueError, match="Empty transcript"):
            await extract_events("", "c1")

    @pytest.mark.asyncio
    @patch("backend.services.extraction.OpenAI")
    async def test_malformed_event_skipped(self, mock_openai_class):
        """Malformed events are skipped, valid ones still returned."""
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client

        mock_response = MagicMock()
        mock_response.choices[0].message.content = json.dumps({
            "events": [
                {"event_type": "INVALID_TYPE", "child_name": "Test"},
                {"event_type": "MEAL", "child_name": "Jason", "needs_review": False},
            ]
        })
        mock_client.chat.completions.create.return_value = mock_response

        events = await extract_events("test transcript", "c1")

        assert len(events) == 1
        assert events[0].child_name == "Jason"
