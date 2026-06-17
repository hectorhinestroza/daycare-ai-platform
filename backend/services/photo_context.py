"""Photo-context resolver — turns a caption or follow-up voice/text reply
into a list of children the photo(s) should be attached to.

Used by the WhatsApp batch-photo flow:
  1. Teacher sends one or more photos with a caption ("Clara and Emi at lunch")
     → we resolve the caption directly.
  2. Teacher sends photos with no caption → we park them in PendingPhoto
     and prompt for a reply. The next text/voice message hits this resolver.

Returns a structured result so the webhook can fan-out (one Photo row per
child, sharing the same s3_key) or fall back to event extraction when the
message clearly isn't naming kids.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from typing import List, Optional

from sqlalchemy.orm import Session

from backend.utils.openai_client import get_openai_client
from backend.utils.openai_wrapper import call_openai_async_with_logging
from backend.utils.safe_logging import safe_log

logger = logging.getLogger(__name__)


SYSTEM_PROMPT = """You identify which children are in a daycare photo
based on a short caption or reply from a teacher.

You will receive:
  - A short message (the caption attached to one or more photos, or a
    reply the teacher sent right after uploading photos).
  - A roster of known children at this center.

Output a JSON object:
{
  "applies_to_all": bool,
  "child_names": [string]
}

Rules:
- If the message refers to the whole group ("everyone", "all kids", "the
  class", "all of them", "todos", "all the children") → applies_to_all=true
  and child_names=[].
- If the message names one or more specific children → applies_to_all=false
  and child_names = those names exactly as they appear in the message.
- If the message looks like a narrative event description rather than a
  list of names (e.g. "Clara had a great nap", "Emi fell on the playground
  and we put ice on it") → return applies_to_all=false and child_names=[].
  The caller will treat that as an event log, not as photo context.
- If the message does not identify any child and is not a group reference
  (e.g. "snack time", "playtime", "look at this"), return
  applies_to_all=false and child_names=[].
- Do not invent names. Only return names that appear in the message.
- Prefer matching against the roster spelling when the message uses a
  clearly equivalent variant (e.g. "Klara" → "Clara") only if the roster
  contains exactly one obvious match. Otherwise leave the name as written.
"""


@dataclass
class PhotoContext:
    applies_to_all: bool = False
    child_names: List[str] = field(default_factory=list)
    raw_message: str = ""

    @property
    def has_context(self) -> bool:
        return self.applies_to_all or bool(self.child_names)


async def resolve_photo_context(
    message: str,
    known_children: List[str],
    center_id: str,
    db: Session,
) -> PhotoContext:
    """Parse a caption / reply into a list of child names or applies_to_all.

    Returns a PhotoContext with `has_context=False` when the message
    neither names a child nor refers to the group — the caller should
    treat that as "need to prompt the teacher" or fall through to normal
    event extraction.
    """
    msg = (message or "").strip()
    if not msg:
        return PhotoContext(raw_message="")

    user_prompt = (
        f"Roster: {', '.join(known_children) if known_children else '(none provided)'}\n\n"
        f"Message: {msg}"
    )

    client = get_openai_client()
    start = time.monotonic()
    try:
        response = await call_openai_async_with_logging(
            client=client,
            db=db,
            center_id=center_id,
            child_id=None,
            pipeline_stage="photo_context",
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
    except Exception as e:
        safe_log(
            logger,
            "error",
            "photo_context.failed",
            duration_ms=int((time.monotonic() - start) * 1000),
            error_type=type(e).__name__,
        )
        # Fail closed: caller will treat as no-context and prompt the teacher.
        return PhotoContext(raw_message=msg)

    applies_to_all = bool(parsed.get("applies_to_all", False))
    raw_names = parsed.get("child_names") or []
    names: List[str] = []
    for n in raw_names:
        if isinstance(n, str) and n.strip():
            names.append(n.strip())

    safe_log(
        logger,
        "info",
        "photo_context.resolved",
        duration_ms=int((time.monotonic() - start) * 1000),
        applies_to_all=applies_to_all,
        name_count=len(names),
        message_length=len(msg),
    )

    return PhotoContext(
        applies_to_all=applies_to_all,
        child_names=names,
        raw_message=msg,
    )


# ─── Lightweight local heuristic ───────────────────────────────
# Cheap check for group-reference phrases, used as a fast-path before the
# LLM call (and in tests where we want to avoid mocking the model).
_ALL_KEYWORDS = (
    "everyone",
    "all kids",
    "all the kids",
    "all of them",
    "all children",
    "the whole class",
    "the class",
    "todos",
    "everybody",
)


def looks_like_group(message: Optional[str]) -> bool:
    if not message:
        return False
    low = message.lower().strip()
    return any(kw in low for kw in _ALL_KEYWORDS)
