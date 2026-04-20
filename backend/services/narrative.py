"""EOD narrative generation service (Issue #10).

Synthesizes approved daily events into a warm parent-facing summary using GPT-4o.

Edge cases handled:
  - No events at all → "no updates recorded" neutral narrative
  - Absence event present → acknowledge absence warmly
  - Incidents / medication → tone = "needs-attention"
  - Only 1–2 events → brief but complete narrative
"""

import json
import logging
import uuid
from datetime import date as date_type
from typing import List, Optional

from openai import AsyncOpenAI
from sqlalchemy import cast, Date, func, or_
from sqlalchemy.orm import Session

from backend.config import get_settings
from backend.storage.models import Child, Event, Photo
from backend.utils.openai_wrapper import call_openai_async_with_logging

logger = logging.getLogger(__name__)

# ─── Prompt ───────────────────────────────────────────────────

SYSTEM_PROMPT = """\
You are a warm, professional preschool communication specialist. \
You write End-of-Day (EOD) summaries for parents — personal, reassuring, and specific.

Rules:
- Address the parent directly (e.g. "Today was a great day for Sofia!").
- Be specific: mention actual activities, foods, nap times if available.
- Keep the body between 80 and 200 words.
- If there are no events, write a brief kind note that no updates were logged for the day.
- If the child was marked absent, acknowledge the absence warmly.
- Set tone to "needs-attention" only when there is an incident or medication event.
- Set tone to "upbeat" when the day had several positive activities.
- Otherwise set tone to "neutral".

Return valid JSON only — no markdown, no extra keys:
{
  "headline": "<one engaging sentence>",
  "body": "<80-200 word narrative>",
  "tone": "upbeat" | "neutral" | "needs-attention"
}"""


def _build_events_block(events: List[Event]) -> str:
    """Format events into a readable block for the prompt."""
    if not events:
        return "No events were recorded today."

    lines = []
    for e in events:
        time_str = e.event_time.strftime("%I:%M %p") if e.event_time else "time unspecified"
        detail = e.details or "(no details)"
        lines.append(f"- [{e.event_type}] at {time_str}: {detail}")
    return "\n".join(lines)


def _infer_tone(events: List[Event]) -> str:
    """Deterministic tone fallback if GPT returns something unexpected."""
    types = {e.event_type for e in events}
    if "incident" in types or "medication" in types:
        return "needs-attention"
    if len(events) >= 3:
        return "upbeat"
    return "neutral"


# ─── Main service function ────────────────────────────────────


async def generate_narrative(
    db: Session,
    center_id: uuid.UUID,
    child_id: uuid.UUID,
    target_date: date_type,
) -> dict:
    """Generate an EOD narrative for a child on a given date.

    Returns a dict with keys: headline, body, tone, photo_captions.
    Does NOT persist — caller is responsible for saving via upsert_narrative().
    """
    child = db.query(Child).filter(
        Child.id == child_id,
        Child.center_id == center_id,
    ).first()

    if not child:
        raise ValueError(f"Child {child_id} not found in center {center_id}")

    # ── 1. Fetch approved events for this child on target_date ──
    events: List[Event] = (
        db.query(Event)
        .filter(
            Event.center_id == center_id,
            Event.status == "APPROVED",
            or_(
                Event.child_id == child_id,
                func.lower(Event.child_name) == func.lower(child.name),
            ),
            cast(func.coalesce(Event.event_time, Event.created_at), Date) == target_date,
        )
        .order_by(Event.event_time.asc().nullslast(), Event.created_at.asc())
        .all()
    )

    # ── 2. Collect photo captions from linked photos ─────────
    photo_captions: dict = {}
    for event in events:
        for photo in event.photos:
            if photo.caption:
                photo_captions[str(photo.id)] = photo.caption

    # ── 3. Handle absence edge case (no GPT call needed) ────
    has_absence = any(e.event_type == "absence" for e in events)
    first_name = child.name.split()[0]

    if not events:
        return {
            "headline": f"No updates recorded for {first_name} today.",
            "body": (
                f"We don't have any logged updates for {first_name} today. "
                "This may mean your child was absent, or updates weren't recorded. "
                "Please reach out to the center if you have any questions."
            ),
            "tone": "neutral",
            "photo_captions": {},
        }

    if has_absence and len(events) == 1:
        return {
            "headline": f"{first_name} was absent today.",
            "body": (
                f"We missed {first_name} today! "
                "We hope everything is well and look forward to seeing them back soon."
            ),
            "tone": "neutral",
            "photo_captions": {},
        }

    # ── 4. Call GPT-4o ────────────────────────────────────────
    settings = get_settings()
    client = AsyncOpenAI(api_key=settings.openai_api_key)

    events_block = _build_events_block(events)
    user_prompt = (
        f"Child: {child.name}\n"
        f"Date: {target_date.strftime('%A, %B %d, %Y')}\n"
        f"Events:\n{events_block}"
    )

    logger.info(
        f"Generating EOD narrative for {child.name} ({child_id}) on {target_date} "
        f"— {len(events)} events"
    )

    try:
        response = await call_openai_async_with_logging(
            client=client,
            db=db,
            center_id=center_id,
            child_id=child_id,
            pipeline_stage="narrative",
            model="gpt-4o",
            temperature=0,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
        )

        raw = response.choices[0].message.content
        parsed = json.loads(raw)

        headline = parsed.get("headline", f"Here's {first_name}'s day!")
        body = parsed.get("body", "")
        tone = parsed.get("tone", _infer_tone(events))

        # Validate tone value
        if tone not in ("upbeat", "neutral", "needs-attention"):
            tone = _infer_tone(events)

        return {
            "headline": headline,
            "body": body,
            "tone": tone,
            "photo_captions": photo_captions,
        }

    except json.JSONDecodeError as e:
        logger.error(f"GPT-4o returned invalid JSON for narrative: {e}")
        raise ValueError("Narrative generation returned invalid JSON") from e
    except Exception as e:
        logger.error(f"Narrative generation failed: {type(e).__name__}: {e}", exc_info=True)
        raise
