"""WhatsApp webhook router for Twilio (Issue #1)."""

import logging
from typing import Dict
from fastapi import APIRouter, Form, Response
from backend.services.transcription import transcribe_audio
from backend.services.extraction import extract_events
from backend.utils.media import download_twilio_media

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhook", tags=["whatsapp"])

# In-memory context store (replaced by PostgreSQL in Issue #4)
# Key: phone number, Value: {"child_name": str, "classroom": str, "center_id": str}
_teacher_context: Dict[str, dict] = {}

# Default center_id for development (replaced by DB lookup in Issue #4)
DEFAULT_CENTER_ID = "center_dev_001"


def _build_twiml_response(message: str) -> Response:
    """Build a TwiML XML response for Twilio."""
    twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Message>{message}</Message>
</Response>"""
    return Response(content=twiml, media_type="application/xml")


def _get_context(phone: str) -> dict:
    """Get the current teacher context for a phone number."""
    return _teacher_context.get(phone, {"center_id": DEFAULT_CENTER_ID})


def _set_context(phone: str, **kwargs) -> None:
    """Update teacher context for a phone number."""
    if phone not in _teacher_context:
        _teacher_context[phone] = {"center_id": DEFAULT_CENTER_ID}
    _teacher_context[phone].update(kwargs)


def _handle_command(phone: str, body: str) -> str | None:
    """Handle /child and /classroom commands. Returns reply text or None."""
    body_stripped = body.strip()
    body_lower = body_stripped.lower()

    if body_lower.startswith("/child"):
        child_name = body_stripped[6:].strip()
        if child_name:
            _set_context(phone, child_name=child_name)
            return f"✅ Context set to child: {child_name}. Send a voice memo or photo now."
        return "⚠️ Usage: /child [name]"

    if body_lower.startswith("/classroom"):
        classroom = body_stripped[10:].strip()
        if classroom:
            _set_context(phone, classroom=classroom)
            return f"✅ Context set to classroom: {classroom}. Send a voice memo or photo now."
        return "⚠️ Usage: /classroom [name]"

    return None


def _format_event_summary(events: list) -> str:
    """Format a confirmation message summarizing extracted events."""
    if not events:
        return "🤔 I couldn't extract any events from that memo. Could you try again?"

    # Group by child
    by_child: Dict[str, list] = {}
    for event in events:
        name = event.child_name
        if name not in by_child:
            by_child[name] = []
        by_child[name].append(event.event_type.value.lower().replace("_", " "))

    parts = []
    for child, types in by_child.items():
        type_summary = ", ".join(
            f"{types.count(t)} {t}" for t in dict.fromkeys(types)
        )
        parts.append(f"{child} ({type_summary})")

    total = len(events)
    children_str = " and ".join(parts)
    review_count = sum(1 for e in events if e.needs_review)

    msg = f"Got it! Parsed {total} event{'s' if total != 1 else ''} for {children_str}."
    if review_count:
        msg += f"\n⚠️ {review_count} event{'s' if review_count != 1 else ''} flagged for review."

    return msg


@router.post("/whatsapp")
async def whatsapp_webhook(
    From: str = Form(""),
    Body: str = Form(""),
    NumMedia: str = Form("0"),
    MediaUrl0: str = Form(None),
    MediaContentType0: str = Form(None),
    # Additional Twilio fields we want to capture for debugging
    MessageSid: str = Form(None),
    ProfileName: str = Form(None),
    SmsStatus: str = Form(None),
) -> Response:
    """Handle incoming WhatsApp messages from Twilio.

    Supports:
    - Voice messages (.ogg/.mp4) → transcribe → extract events
    - Text commands (/child, /classroom)
    - Photo messages (stored for later attachment)
    """
    phone = From
    body = Body.strip()
    num_media = int(NumMedia)

    # === VERBOSE DEBUG LOGGING ===
    logger.warning(
        f"=== INCOMING WHATSAPP ===\n"
        f"  From: {phone}\n"
        f"  ProfileName: {ProfileName}\n"
        f"  MessageSid: {MessageSid}\n"
        f"  Body: '{body}'\n"
        f"  NumMedia: {num_media}\n"
        f"  MediaUrl0: {MediaUrl0}\n"
        f"  MediaContentType0: {MediaContentType0}\n"
        f"  SmsStatus: {SmsStatus}\n"
        f"========================="
    )

    # 1. Handle text commands
    if body and not num_media:
        command_reply = _handle_command(phone, body)
        if command_reply:
            return _build_twiml_response(command_reply)

        # Plain text that isn't a command — treat as a note
        context = _get_context(phone)
        try:
            events = await extract_events(
                transcript=body,
                center_id=context.get("center_id", DEFAULT_CENTER_ID),
                child_name=context.get("child_name"),
            )
            return _build_twiml_response(_format_event_summary(events))
        except Exception as e:
            logger.error(f"Extraction from text failed: {e}")
            return _build_twiml_response(
                "❌ Sorry, I had trouble processing that message. Please try again."
            )

    # 2. Handle voice messages
    if num_media >= 1 and MediaContentType0 and (
        "audio" in MediaContentType0 or "video" in MediaContentType0
    ):
        context = _get_context(phone)
        try:
            # Download audio from Twilio
            audio_bytes, content_type = await download_twilio_media(MediaUrl0)

            # Determine file extension
            ext = "ogg" if "ogg" in content_type else "mp4"
            filename = f"voice_memo.{ext}"

            # Transcribe
            transcript = await transcribe_audio(audio_bytes, filename)
            logger.info(f"Transcript: {transcript[:100]}...")

            # Extract events
            events = await extract_events(
                transcript=transcript,
                center_id=context.get("center_id", DEFAULT_CENTER_ID),
                child_name=context.get("child_name"),
            )

            return _build_twiml_response(_format_event_summary(events))

        except Exception as e:
            logger.error(f"Voice pipeline failed: {e}")
            return _build_twiml_response(
                "❌ Sorry, I had trouble processing that voice memo. Please try again."
            )

    # 3. Handle photo messages
    if num_media >= 1 and MediaContentType0 and "image" in MediaContentType0:
        context = _get_context(phone)
        child_name = context.get("child_name", "Unknown")

        # Store photo metadata (full storage in Issue #4)
        logger.info(f"Photo received for {child_name} from {phone}")

        msg = f"📷 Photo received for {child_name}."
        if body:
            msg += f" Caption: \"{body}\""
        return _build_twiml_response(msg)

    # 4. Fallback
    return _build_twiml_response(
        "👋 Hi! Send a voice memo to log events, "
        "or use /child [name] to set context."
    )
