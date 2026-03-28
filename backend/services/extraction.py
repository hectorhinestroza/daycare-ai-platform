"""GPT-4o structured event extraction service (Issue #3).

Extracts Brightwheel-aligned events from teacher voice memos/text.
Event types: food, nap, potty, kudos, observation, health_check,
             absence, note, incident, medication
"""

import json
import logging
from uuid import uuid4
from typing import List, Optional
from openai import OpenAI
from pydantic import ValidationError
from backend.config import get_settings
from schemas.events import (
    BaseEvent, EventType, EventStatus,
    ALWAYS_REVIEW_TYPES,
)

logger = logging.getLogger(__name__)

# Confidence threshold — below this, event goes to director
CONFIDENCE_THRESHOLD = 0.7

SYSTEM_PROMPT = """You are an event extraction system for a daycare center.
Extract only what is explicitly stated in the transcript. Do not infer or add detail.

For each distinct event mentioned, extract:
- event_type: one of "food", "nap", "potty", "kudos", "observation", "health_check", "absence", "note", "incident", "medication"
- child_name: the child's name as mentioned
- event_time: ISO 8601 datetime if mentioned, otherwise null
- confidence_score: a float 0.0–1.0 indicating how confident you are in the extraction accuracy. Set below 0.7 if the child name is unclear, the event type is ambiguous, or details are vague.
- details: a brief description of what was stated

You MUST return a JSON object with an "events" key containing an array of all extracted events.
If no events can be extracted, return {"events": []}.

Example output:
{"events": [
  {
    "event_type": "food",
    "child_name": "Jason",
    "event_time": null,
    "confidence_score": 0.95,
    "details": "Ate most of his mac and cheese at lunch, asked for more apple slices"
  },
  {
    "event_type": "nap",
    "child_name": "Jason",
    "event_time": "2024-01-15T12:00:00",
    "confidence_score": 0.9,
    "details": "Napped from noon to 1:15pm"
  },
  {
    "event_type": "incident",
    "child_name": "Emma",
    "event_time": null,
    "confidence_score": 0.85,
    "details": "Fell on the playground and scraped her left knee"
  }
]}"""


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

        # Handle all possible GPT-4o response formats:
        # 1. {"events": [...]}  — array wrapped in object
        # 2. [...]             — direct array
        # 3. {"event_type": ...} — single event as bare dict
        if isinstance(parsed, dict) and "events" in parsed:
            raw_events = parsed["events"]
        elif isinstance(parsed, list):
            raw_events = parsed
        elif isinstance(parsed, dict) and "event_type" in parsed:
            raw_events = [parsed]
        else:
            logger.warning(f"Unexpected response structure: {parsed}")
            raw_events = []

        # Validate each event against Pydantic schema
        validated_events: List[BaseEvent] = []
        for raw_event in raw_events:
            try:
                event_type = EventType(raw_event["event_type"])
                confidence = float(raw_event.get("confidence_score", 0.5))

                # Determine review tier based on confidence + event type
                is_always_review = event_type in ALWAYS_REVIEW_TYPES
                is_low_confidence = confidence < CONFIDENCE_THRESHOLD
                needs_director = is_always_review or is_low_confidence
                review_tier = "director" if needs_director else "teacher"

                event = BaseEvent(
                    id=uuid4(),
                    center_id=center_id,
                    child_name=raw_event.get("child_name", child_name or "Unknown"),
                    event_type=event_type,
                    event_time=raw_event.get("event_time"),
                    details=raw_event.get("details"),
                    confidence_score=confidence,
                    review_tier=review_tier,
                    needs_director_review=needs_director,
                    needs_review=needs_director,
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
