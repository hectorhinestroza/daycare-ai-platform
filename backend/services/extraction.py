"""GPT-4o structured event extraction service (Issue #3)."""

import json
import logging
from uuid import uuid4
from typing import List, Optional
from openai import OpenAI
from pydantic import ValidationError
from backend.config import get_settings
from schemas.events import BaseEvent, EventType, EventStatus

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are an event extraction system for a daycare center.
Extract only what is explicitly stated in the transcript. Do not infer or add detail.

For each distinct event mentioned, extract:
- event_type: one of MEAL, NAP, DIAPER, ACTIVITY, NOTE_TO_PARENT, PICKUP, DROP_OFF, INCIDENT_MINOR, INCIDENT_MAJOR, BILLING_LATE_PICKUP, BILLING_EXTRA_HOURS, BILLING_DROP_IN
- child_name: the child's name as mentioned
- event_time: ISO 8601 datetime if mentioned, otherwise null
- needs_review: set to true if the information is ambiguous, unclear, or you are uncertain about any field
- details: a brief description of what was stated

Return a JSON array of event objects. If no events can be extracted, return an empty array.

Example output:
[
  {
    "event_type": "MEAL",
    "child_name": "Jason",
    "event_time": null,
    "needs_review": false,
    "details": "Ate most of his mac and cheese at lunch, asked for more apple slices"
  }
]"""


async def extract_events(
    transcript: str,
    center_id: str,
    child_name: Optional[str] = None,
) -> List[BaseEvent]:
    """Extract structured events from a transcript using GPT-4o.

    Args:
        transcript: Raw transcript text from Whisper
        center_id: Center ID for multi-tenant isolation
        child_name: Optional pre-set child context from /child command

    Returns:
        List of validated BaseEvent objects

    Raises:
        ValueError: If extraction or validation fails
    """
    if not transcript.strip():
        raise ValueError("Empty transcript received")

    settings = get_settings()
    client = OpenAI(api_key=settings.openai_api_key)

    user_prompt = f"Transcript: {transcript}"
    if child_name:
        user_prompt = f"Context: Events are about child named {child_name}.\n\n{user_prompt}"

    logger.info(f"Extracting events from transcript ({len(transcript)} chars)")

    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            temperature=0,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
        )

        raw_content = response.choices[0].message.content
        parsed = json.loads(raw_content)

        # Handle both {"events": [...]} and direct array
        if isinstance(parsed, dict) and "events" in parsed:
            raw_events = parsed["events"]
        elif isinstance(parsed, list):
            raw_events = parsed
        else:
            raise ValueError(f"Unexpected response structure: {type(parsed)}")

        # Validate each event against Pydantic schema
        validated_events: List[BaseEvent] = []
        for raw_event in raw_events:
            try:
                event = BaseEvent(
                    id=uuid4(),
                    center_id=center_id,
                    child_name=raw_event.get("child_name", child_name or "Unknown"),
                    event_type=EventType(raw_event["event_type"]),
                    event_time=raw_event.get("event_time"),
                    needs_review=raw_event.get("needs_review", True),
                    status=EventStatus.PENDING,
                    raw_transcript=transcript,
                    photo_ids=[],
                )
                validated_events.append(event)
            except (ValidationError, KeyError, ValueError) as e:
                logger.warning(f"Skipping malformed event: {e} — raw: {raw_event}")
                continue

        logger.info(
            f"Extracted {len(validated_events)} valid events "
            f"from {len(raw_events)} raw events"
        )
        return validated_events

    except json.JSONDecodeError as e:
        logger.error(f"GPT-4o returned invalid JSON: {e}")
        raise ValueError(f"LLM returned invalid JSON: {e}")
    except Exception as e:
        logger.error(f"Event extraction failed: {e}")
        raise
