"""Tests for the GPT-4o extraction service (Issue #3).

Tests cover the Brightwheel-aligned event types: food, nap, potty,
kudos, observation, health_check, absence, note, incident, medication.
"""

import json
from unittest.mock import MagicMock, patch

import pytest

from backend.services.extraction import extract_events
from schemas.events import EventType


class TestExtractEvents:
    """Test GPT-4o structured event extraction."""

    @pytest.mark.asyncio
    @patch("backend.services.extraction.OpenAI")
    async def test_single_food_event(self, mock_openai_class):
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client

        mock_response = MagicMock()
        mock_response.choices[0].message.content = json.dumps(
            {
                "events": [
                    {
                        "event_type": "food",
                        "child_name": "Jason",
                        "event_time": None,
                        "confidence_score": 0.95,
                        "details": "Ate mac and cheese for lunch",
                    }
                ]
            }
        )
        mock_client.chat.completions.create.return_value = mock_response

        events = await extract_events(
            transcript="Jason ate mac and cheese for lunch",
            center_id="center_001",
            db=MagicMock(),
        )

        assert len(events) == 1
        assert events[0].child_name == "Jason"
        assert events[0].event_type == EventType.FOOD
        assert events[0].center_id == "center_001"
        assert events[0].confidence_score == 0.95
        assert events[0].review_tier == "teacher"
        assert events[0].needs_director_review is False
        assert events[0].needs_review is False

    @pytest.mark.asyncio
    @patch("backend.services.extraction.OpenAI")
    async def test_multiple_events_extraction(self, mock_openai_class):
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client

        mock_response = MagicMock()
        mock_response.choices[0].message.content = json.dumps(
            {
                "events": [
                    {"event_type": "food", "child_name": "Jason", "confidence_score": 0.9},
                    {"event_type": "nap", "child_name": "Jason", "confidence_score": 0.85},
                    {"event_type": "kudos", "child_name": "Emma", "confidence_score": 0.8},
                ]
            }
        )
        mock_client.chat.completions.create.return_value = mock_response

        events = await extract_events("Jason had lunch, napped. Emma shared toys.", "c1", db=MagicMock())

        assert len(events) == 3
        assert events[0].event_type == EventType.FOOD
        assert events[1].event_type == EventType.NAP
        assert events[2].event_type == EventType.KUDOS
        # All high confidence → teacher tier
        assert all(e.review_tier == "teacher" for e in events)

    @pytest.mark.asyncio
    @patch("backend.services.extraction.OpenAI")
    async def test_low_confidence_goes_to_director(self, mock_openai_class):
        """Low confidence events go to director queue."""
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client

        mock_response = MagicMock()
        mock_response.choices[0].message.content = json.dumps(
            {
                "events": [
                    {"event_type": "nap", "child_name": "Someone", "confidence_score": 0.3},
                ]
            }
        )
        mock_client.chat.completions.create.return_value = mock_response

        events = await extract_events("someone took a nap", "c1", db=MagicMock())

        assert len(events) == 1
        assert events[0].confidence_score == 0.3
        assert events[0].review_tier == "director"
        assert events[0].needs_director_review is True
        assert events[0].needs_review is True

    @pytest.mark.asyncio
    @patch("backend.services.extraction.OpenAI")
    async def test_incident_always_director(self, mock_openai_class):
        """Incidents ALWAYS go to director regardless of confidence."""
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client

        mock_response = MagicMock()
        mock_response.choices[0].message.content = json.dumps(
            {
                "events": [
                    {"event_type": "incident", "child_name": "Jason", "confidence_score": 0.99},
                ]
            }
        )
        mock_client.chat.completions.create.return_value = mock_response

        events = await extract_events("Jason fell and scraped his knee", "c1", db=MagicMock())

        assert len(events) == 1
        assert events[0].event_type == EventType.INCIDENT
        assert events[0].confidence_score == 0.99
        assert events[0].review_tier == "director"  # incident → always director
        assert events[0].needs_director_review is True

    @pytest.mark.asyncio
    @patch("backend.services.extraction.OpenAI")
    async def test_medication_always_director(self, mock_openai_class):
        """Medication ALWAYS goes to director regardless of confidence."""
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client

        mock_response = MagicMock()
        mock_response.choices[0].message.content = json.dumps(
            {
                "events": [
                    {"event_type": "medication", "child_name": "Emma", "confidence_score": 0.95},
                ]
            }
        )
        mock_client.chat.completions.create.return_value = mock_response

        events = await extract_events("Gave Emma her allergy medicine at 2pm", "c1", db=MagicMock())

        assert len(events) == 1
        assert events[0].event_type == EventType.MEDICATION
        assert events[0].review_tier == "director"  # medication → always director
        assert events[0].needs_director_review is True

    @pytest.mark.asyncio
    @patch("backend.services.extraction.OpenAI")
    async def test_potty_event(self, mock_openai_class):
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client

        mock_response = MagicMock()
        mock_response.choices[0].message.content = json.dumps(
            {
                "events": [
                    {"event_type": "potty", "child_name": "Sarah", "confidence_score": 0.9},
                ]
            }
        )
        mock_client.chat.completions.create.return_value = mock_response

        events = await extract_events("Successful potty for Sarah", "c1", db=MagicMock())

        assert len(events) == 1
        assert events[0].event_type == EventType.POTTY
        assert events[0].review_tier == "teacher"  # low risk

    @pytest.mark.asyncio
    @patch("backend.services.extraction.OpenAI")
    async def test_health_check_event(self, mock_openai_class):
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client

        mock_response = MagicMock()
        mock_response.choices[0].message.content = json.dumps(
            {
                "events": [
                    {
                        "event_type": "health_check",
                        "child_name": "Emma",
                        "confidence_score": 0.85,
                        "details": "Temp of 99.2",
                    },
                ]
            }
        )
        mock_client.chat.completions.create.return_value = mock_response

        events = await extract_events("Emma had a temp of 99.2", "c1", db=MagicMock())

        assert len(events) == 1
        assert events[0].event_type == EventType.HEALTH_CHECK
        assert events[0].review_tier == "teacher"

    @pytest.mark.asyncio
    @patch("backend.services.extraction.OpenAI")
    async def test_temperature_zero(self, mock_openai_class):
        """Verify temperature=0 is always used (deterministic)."""
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client

        mock_response = MagicMock()
        mock_response.choices[0].message.content = json.dumps({"events": []})
        mock_client.chat.completions.create.return_value = mock_response

        await extract_events("test", "c1", db=MagicMock())

        call_kwargs = mock_client.chat.completions.create.call_args
        assert call_kwargs.kwargs["temperature"] == 0

    @pytest.mark.asyncio
    @patch("backend.services.extraction.OpenAI")
    async def test_child_name_context(self, mock_openai_class):
        """Verify child_name context is passed to GPT-4o."""
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client

        mock_response = MagicMock()
        mock_response.choices[0].message.content = json.dumps(
            {"events": [{"event_type": "food", "child_name": "Jason", "confidence_score": 0.9}]}
        )
        mock_client.chat.completions.create.return_value = mock_response

        await extract_events("had lunch", "c1", db=MagicMock(), child_name="Jason")

        call_kwargs = mock_client.chat.completions.create.call_args
        user_msg = call_kwargs.kwargs["messages"][1]["content"]
        assert "Jason" in user_msg

    @pytest.mark.asyncio
    async def test_empty_transcript_raises(self):
        with pytest.raises(ValueError, match="Empty transcript"):
            await extract_events("", "c1", db=MagicMock())

    @pytest.mark.asyncio
    @patch("backend.services.extraction.OpenAI")
    async def test_malformed_event_skipped(self, mock_openai_class):
        """Malformed events are skipped, valid ones still returned."""
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client

        mock_response = MagicMock()
        mock_response.choices[0].message.content = json.dumps(
            {
                "events": [
                    {"event_type": "INVALID_TYPE", "child_name": "Test"},
                    {"event_type": "food", "child_name": "Jason", "confidence_score": 0.85},
                ]
            }
        )
        mock_client.chat.completions.create.return_value = mock_response

        events = await extract_events("test transcript", "c1", db=MagicMock())

        assert len(events) == 1
        assert events[0].child_name == "Jason"

    @pytest.mark.asyncio
    @patch("backend.services.extraction.OpenAI")
    async def test_default_confidence_when_missing(self, mock_openai_class):
        """When GPT-4o omits confidence_score, default to 0.5 (director queue)."""
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client

        mock_response = MagicMock()
        mock_response.choices[0].message.content = json.dumps(
            {
                "events": [
                    {"event_type": "food", "child_name": "Jason"},  # no confidence_score
                ]
            }
        )
        mock_client.chat.completions.create.return_value = mock_response

        events = await extract_events("Jason ate lunch", "c1", db=MagicMock())

        assert len(events) == 1
        assert events[0].confidence_score == 0.5
        assert events[0].review_tier == "director"  # 0.5 < 0.7 threshold
