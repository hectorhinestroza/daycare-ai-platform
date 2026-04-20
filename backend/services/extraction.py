"""GPT-4o structured event extraction service (Issue #3).

Extracts Brightwheel-aligned events from teacher voice memos/text.
Event types: food, nap, potty, kudos, observation, health_check,
             absence, note, incident, medication
"""

import json
import logging
from typing import List, Optional
from uuid import UUID, uuid4

from openai import OpenAI
from pydantic import ValidationError
from sqlalchemy.orm import Session

from backend.config import get_settings
from backend.utils.openai_wrapper import call_openai_with_logging
from schemas.events import (
    ALWAYS_REVIEW_TYPES,
    BaseEvent,
    EventStatus,
    EventType,
)

logger = logging.getLogger(__name__)

# Confidence threshold — below this, event goes to director
CONFIDENCE_THRESHOLD = 0.7

SYSTEM_PROMPT = """You are an event extraction system for a daycare center.
Teachers send voice memos and text messages describing what children did during the day.
Your job is to extract EVERY event mentioned in the transcript.

CRITICAL RULES:
- ALWAYS extract events. If the transcript mentions any child activity, food, nap, potty, incident, etc., you MUST extract it.
- ANY name mentioned is a valid child name. Do not skip events because a name seems unusual.
- Do not add events that were not mentioned. Stick to what was said.
- If a name is unclear or ambiguous, still extract the event but set confidence_score below 0.7.
- NEVER return an empty events array if the transcript describes activities.

CHILD VOICE INSTRUCTION (legal requirement — do not modify):
If any child's voice is audible in this audio, treat the entire recording as 
containing children's personal information. Do not transcribe or quote direct 
speech from any child. Describe only the observable events narrated by the teacher.

For each distinct event mentioned, extract:
- event_type: one of "food", "nap", "potty", "kudos", "observation", "health_check", "absence", "note", "activity", "incident", "medication"
- child_name: the child's name exactly as mentioned in the transcript
- event_time: ISO 8601 datetime if mentioned, otherwise null
- confidence_score: a float 0.0–1.0 indicating extraction accuracy. Set below 0.7 if the child name is unclear, event type is ambiguous, or details are vague.
- details: a brief factual description of what was stated

Return a JSON object: {"events": [...]}

Example — teacher says "Carlos played basketball, then had a snack and took a nap":
{"events": [
  {"event_type": "activity", "child_name": "Carlos", "event_time": null, "confidence_score": 0.9, "details": "Played basketball"},
  {"event_type": "food", "child_name": "Carlos", "event_time": null, "confidence_score": 0.85, "details": "Had a snack"},
  {"event_type": "nap", "child_name": "Carlos", "event_time": null, "confidence_score": 0.9, "details": "Took a nap"}
]}"""


async def extract_events(
    transcript: str,
    center_id: str,
    db: Session,
    child_name: Optional[str] = None,
    known_children: Optional[List[str]] = None,
    child_id: Optional[UUID] = None,
) -> List[BaseEvent]:
    """Extract structured events from a transcript using GPT-4o.

    Args:
        transcript:     Raw transcript text from Whisper
        center_id:      Center ID for multi-tenant isolation
        db:             SQLAlchemy session — used for OpenAI audit log (L-5)
        child_name:     Optional pre-set child context from /child command
        known_children: Optional list of actual registered child names for resolution
        child_id:       Optional resolved child UUID for the audit log

    Returns:
        List of validated BaseEvent objects
    """
    if not transcript.strip():
        raise ValueError("Empty transcript received")

    settings = get_settings()
    client = OpenAI(api_key=settings.openai_api_key)

    user_prompt = f"Transcript: {transcript}"
    if child_name:
        user_prompt = f"Context: Events are about child named {child_name}.\n\n{user_prompt}"
    elif known_children:
        children_list = ", ".join(known_children)
        user_prompt = f"Known Children in this room: {children_list}\n\n{user_prompt}"

    logger.info(f"Extracting events from transcript ({len(transcript)} chars)")

    try:
        response = call_openai_with_logging(
            client=client,
            db=db,
            center_id=center_id,
            child_id=child_id,
            pipeline_stage="extraction",
            model="gpt-4o",
            temperature=0,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
        )

        raw_content = response.choices[0].message.content
        logger.debug(f"GPT-4o raw response: {raw_content}")
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
                logger.warning(f"Dropped malformed event: {type(e).__name__}: {e} — raw: {raw_event}")
                continue

        logger.info(f"Extracted {len(validated_events)} valid events from {len(raw_events)} raw events")
        return validated_events

    except json.JSONDecodeError as e:
        logger.error(f"GPT-4o returned invalid JSON: {e}")
        raise ValueError(f"LLM returned invalid JSON: {e}") from e
    except Exception as e:
        logger.error(f"Event extraction failed: {type(e).__name__}: {e}", exc_info=True)
        raise e
