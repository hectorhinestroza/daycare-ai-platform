"""GPT-4o structured event extraction service (Issue #3).

Extracts Brightwheel-aligned events from teacher voice memos/text.
Event types: food, nap, potty, kudos, observation, health_check,
             absence, note, incident, medication
"""

import json
import logging
import time
from typing import List, Optional, Tuple
from uuid import UUID, uuid4

from pydantic import ValidationError
from sqlalchemy.orm import Session

from backend.utils.openai_client import get_openai_client
from backend.utils.openai_wrapper import call_openai_async_with_logging
from backend.utils.safe_logging import safe_log
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
- You will be provided with a list of "Known Children in this room". If ANY child name mentioned in the transcript is NOT a perfect or obvious match for a known child on the roster, you MUST include that transcript name in the "unrecognized_names" array.
- DO NOT hallucinate or guess unrecognized names into known names if they are completely different. Just extract the event with the said name, and flag it in unrecognized_names.
- Teachers will send raw voice notes, because they will be doing it in the middle of the day while taking care of children, that means that extracted events and descriptions need to be cleaned up of any negative or unprofessional language and it needs to be as parent friendly as possible. Key words that need to be paraphrased are:
  * "struggling", "struggle", "struggled", "hard time" -> "needed help with", "we recommend that you continue working on this at home", "needs to improve on", "working on"
  * "had/throwing a tantrum/fit" -> "felt overwhelmed", "could use better guidance processing his/her emotions",
  * "did not want to", "refused to" -> "was reluctant to", "needed redirection"
  * "hit {child_name} with {object}" -> "had an incident involving another kid". Never mention other kids names but still include details about the other kid, for example "One of the kids was laying down outside and Penny ran outside and tripped over Wilder's face. Wilder got a bump on his nose" Will obscure Wilder's name but still give details about what happened to him
  * "talked back to {teacher}" -> "spoke disrespectfully to teacher" or "did not respond to teacher's directions" (whatever is more accurate)
- If there is an incident that also has a response to it in the note, then package it as a single activity 

BATCH / GROUP EVENTS:
- If the teacher says "all kids", "everyone", "the whole class", "all children", or any clearly
  all-inclusive phrase, set applies_to_all=true and child_name=null for that event.
- Do NOT expand the roster yourself — the system will fan-out to individual children.
- applies_to_all=false for any event that mentions a specific child by name.

CHILD VOICE INSTRUCTION (legal requirement — do not modify):
If any child's voice is audible in this audio, treat the entire recording as 
containing children's personal information. Do not transcribe or quote direct 
speech from any child. Describe only the observable events narrated by the teacher.

For each distinct event mentioned, extract:
- event_type: one of "food", "nap", "potty", "kudos", "observation", "health_check", "absence", "note", "activity", "incident", "medication"
- child_name: the child's name exactly as mentioned in the transcript, or null if applies_to_all=true
- applies_to_all: true if the teacher used a group phrase ("all kids", "everyone", etc.), false otherwise
- event_time: ISO 8601 datetime if mentioned, otherwise null
- confidence_score: a float 0.0–1.0 indicating extraction accuracy. Set below 0.7 if the child name is unclear, event type is ambiguous, or details are vague.
- details: a brief factual description of what was stated

Return a JSON object with this shape:
{
  "unrecognized_names": ["list of child names from the transcript that are NOT in the Known Children roster"],
  "events": [...]
}

Example — teacher says "Carlos played basketball, then had a snack and took a nap":
{
  "unrecognized_names": [],
  "events": [
    {"event_type": "activity", "child_name": "Carlos", "applies_to_all": false, "event_time": null, "confidence_score": 0.9, "details": "Played basketball"},
    {"event_type": "food", "child_name": "Carlos", "applies_to_all": false, "event_time": null, "confidence_score": 0.85, "details": "Had a snack"},
    {"event_type": "nap", "child_name": "Carlos", "applies_to_all": false, "event_time": null, "confidence_score": 0.9, "details": "Took a nap"}
  ]
}

Example — teacher says "all kids had rice and beans for lunch":
{
  "unrecognized_names": [],
  "events": [
    {"event_type": "food", "child_name": null, "applies_to_all": true, "event_time": null, "confidence_score": 0.95, "details": "Had rice and beans for lunch"}
  ]
}"""


async def extract_events(
    transcript: str,
    center_id: str,
    db: Session,
    child_name: Optional[str] = None,
    known_children: Optional[List[str]] = None,
    child_id: Optional[UUID] = None,
    teacher_name: Optional[str] = None,
) -> Tuple[List[BaseEvent], List[str]]:
    """Extract structured events from a transcript using GPT-4o.

    Args:
        transcript:     Raw transcript text from Whisper
        center_id:      Center ID for multi-tenant isolation
        db:             SQLAlchemy session — used for OpenAI audit log
        child_name:     Optional pre-set child context from /child command
        known_children: Optional list of actual registered child names for resolution
        child_id:       Optional resolved child UUID for the audit log
        teacher_name:   Optional name of the teacher who sent this voice note.
                        Two prompt effects:
                          (a) Prevent the AI from extracting the sender's own
                              name as a child event.
                          (b) When the teacher appears as the actor of an
                              event with a kid ("Emi helped Joii", "I read a
                              book with Carlos"), attribute the teacher in
                              `details` text so parents see the interaction
                              ("Got help from Emi"). The event still belongs
                              to the child.

    Returns:
        Tuple of (validated_events, unrecognized_names)
    """
    if not transcript.strip():
        raise ValueError("Empty transcript received")

    client = get_openai_client()

    user_prompt = f"Transcript: {transcript}"
    if child_name:
        user_prompt = (
            f"Default child name (use ONLY if the transcript does not name a child): {child_name}. "
            f"If the transcript explicitly names a different child, use that name instead — "
            f"do not override what the teacher actually said.\n\n{user_prompt}"
        )
    elif known_children:
        children_list = ", ".join(known_children)
        user_prompt = f"Known Children in this room: {children_list}\n\n{user_prompt}"

    # Teacher context — the sender narrates events about *children*. Two
    # behaviors we want from the model:
    #
    #   1. Never extract the teacher's own name as if it were a child event.
    #   2. When the teacher's name appears as the actor of an event (e.g.
    #      "Emi helped Joii", "I read a book with Carlos"), attribute the
    #      teacher in `details` so parents see who interacted with their kid
    #      ("Got help from Emi", "Read a book with Ms. Emi"). The event still
    #      belongs to the *child* — teacher_name only enriches details.
    if teacher_name:
        user_prompt = (
            f"This voice note was sent by teacher {teacher_name}.\n"
            f"RULES for teacher attribution:\n"
            f"  - Never extract {teacher_name} as a child — they are staff.\n"
            f"  - The teacher's first-person references ('I', 'me', 'my') refer "
            f"to {teacher_name}. Resolve them to '{teacher_name}' in `details`.\n"
            f"  - When the teacher and a child interact, the event ALWAYS "
            f"belongs to the CHILD (child_name = the child). In `details`, "
            f"include the teacher's name to capture who they interacted with. "
            f"Direction of action matters — preserve it in the details text:\n"
            f"      • Teacher → child (teacher acting on/with child):\n"
            f"          '{teacher_name} helped Joii build a tower'\n"
            f"            → child=Joii, details: 'Built a tower with help from {teacher_name}'\n"
            f"          'I read a book to Carlos'\n"
            f"            → child=Carlos, details: 'Read a book with {teacher_name}'\n"
            f"      • Child → teacher (child acting on/with teacher):\n"
            f"          'Carlos helped me organize the toys'\n"
            f"            → child=Carlos, details: 'Helped {teacher_name} organize the toys'\n"
            f"          'Joii asked me for a hug'\n"
            f"            → child=Joii, details: 'Asked {teacher_name} for a hug'\n\n"
            f"{user_prompt}"
        )

    safe_log(
        logger,
        "info",
        "extraction.started",
        transcript_length=len(transcript),
        known_children_count=len(known_children) if known_children else 0,
    )
    start = time.monotonic()

    try:
        response = await call_openai_async_with_logging(
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
        # Do NOT log raw_content — it contains child names extracted from the
        # transcript (full PII). Logging shape only.
        parsed = json.loads(raw_content)

        # Handle all possible GPT-4o response formats:
        # 1. {"events": [...]}  — array wrapped in object
        # 2. [...]             — direct array
        # 3. {"event_type": ...} — single event as bare dict
        unrecognized_names: List[str] = []
        if isinstance(parsed, dict) and "events" in parsed:
            raw_events = parsed["events"]
            unrecognized_names = parsed.get("unrecognized_names", [])
        elif isinstance(parsed, list):
            raw_events = parsed
        elif isinstance(parsed, dict) and "event_type" in parsed:
            raw_events = [parsed]
        else:
            # Don't log `parsed` — it contains child-named events.
            safe_log(
                logger,
                "warning",
                "extraction.unexpected_response_shape",
                parsed_type=type(parsed).__name__,
            )
            raw_events = []

        response_shape = (
            "object_with_events"
            if isinstance(parsed, dict) and "events" in parsed
            else (
                "list"
                if isinstance(parsed, list)
                else (
                    "single_event"
                    if isinstance(parsed, dict) and "event_type" in parsed
                    else "unknown"
                )
            )
        )

        # Validate each event against Pydantic schema
        validated_events: List[BaseEvent] = []
        for raw_event in raw_events:
            try:
                applies_to_all = bool(raw_event.get("applies_to_all", False))
                event_type = EventType(raw_event["event_type"])
                confidence = float(raw_event.get("confidence_score", 0.5))

                # Determine review tier based on confidence + event type
                is_always_review = event_type in ALWAYS_REVIEW_TYPES
                is_low_confidence = confidence < CONFIDENCE_THRESHOLD
                needs_director = is_always_review or is_low_confidence
                review_tier = "director" if needs_director else "teacher"

                # Resolve child_name: null when applies_to_all, else use transcript name
                resolved_child_name = (
                    None
                    if applies_to_all
                    else raw_event.get("child_name") or child_name or "Unknown"
                )

                event = BaseEvent(
                    id=uuid4(),
                    center_id=center_id,
                    child_name=resolved_child_name or "ALL",
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
                    applies_to_all=applies_to_all,
                )
                validated_events.append(event)
            except (ValidationError, KeyError, ValueError) as e:
                # Don't log `raw_event` — it contains the child name and details.
                safe_log(
                    logger,
                    "warning",
                    "extraction.event_dropped",
                    error_type=type(e).__name__,
                )
                continue

        safe_log(
            logger,
            "info",
            "extraction.completed",
            duration_ms=int((time.monotonic() - start) * 1000),
            response_shape=response_shape,
            raw_event_count=len(raw_events),
            validated_event_count=len(validated_events),
            unrecognized_name_count=len(unrecognized_names),
        )
        return validated_events, unrecognized_names

    except json.JSONDecodeError:
        # JSONDecodeError messages can include a snippet of the offending JSON,
        # which contains child names — log type only, not the message.
        safe_log(
            logger,
            "error",
            "extraction.invalid_json",
            duration_ms=int((time.monotonic() - start) * 1000),
        )
        raise ValueError("LLM returned invalid JSON") from None
    except Exception as e:
        # exc_info=True is fine: the traceback structure is captured by Sentry's
        # before_send scrubber (frame vars are redacted). Avoid `{e}` in the
        # format string since OpenAI errors can echo prompt content.
        safe_log(
            logger,
            "error",
            "extraction.failed",
            duration_ms=int((time.monotonic() - start) * 1000),
            error_type=type(e).__name__,
        )
        logger.error("extraction.failed traceback", exc_info=True)
        raise
