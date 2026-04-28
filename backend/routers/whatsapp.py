"""WhatsApp webhook router for Twilio (Issue #1 and #4)."""

import asyncio
import gc
import json
import logging
import uuid
from datetime import UTC, datetime, timedelta
from typing import Dict, Optional

from fastapi import APIRouter, Depends, Form, Response
from sqlalchemy.orm import Session

from backend.config import get_settings
from backend.services.extraction import extract_events
from backend.services.transcription import transcribe_audio
from backend.storage.database import get_db
from backend.storage.events_handlers import (
    create_event_from_base,
    create_pending_photo,
    create_photo,
    delete_pending_photo,
    get_child_by_name,
    get_children_by_center,
    get_pending_photos_by_teacher,
    get_teacher_by_phone,
)
from backend.storage.models import PendingEvent
from backend.utils.consent_gate import get_child_for_processing
from backend.utils.media import delete_twilio_media, download_twilio_media
from backend.utils.photo import build_pending_s3_key, build_photo_s3_key, strip_exif
from backend.utils.s3 import delete_photo as delete_s3_object
from backend.utils.s3 import download_from_s3, upload_photo
from schemas.events import BaseEvent

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhook", tags=["whatsapp"])

# In-memory context store for /child and /classroom commands
# Key: phone number, Value: dict
_command_context: Dict[str, dict] = {}


def _build_twiml_response(message: str) -> Response:
    """Build a TwiML XML response for Twilio."""
    twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Message>{message}</Message>
</Response>"""
    return Response(content=twiml, media_type="application/xml")


def _get_command_context(phone: str) -> dict:
    """Get the current command context for a phone number."""
    return _command_context.get(phone, {})


def _set_command_context(phone: str, **kwargs) -> None:
    """Update command context for a phone number."""
    if phone not in _command_context:
        _command_context[phone] = {}
    _command_context[phone].update(kwargs)


def _handle_command(phone: str, body: str) -> Optional[str]:
    """Handle /child and /classroom commands. Returns reply text or None."""
    body_stripped = body.strip()
    body_lower = body_stripped.lower()

    if body_lower.startswith("/child"):
        child_name = body_stripped[6:].strip()
        if child_name:
            _set_command_context(phone, child_name=child_name)
            return f"✅ Context set to child: {child_name}. Send a voice memo or photo now."
        return "⚠️ Usage: /child [name]"

    if body_lower.startswith("/classroom"):
        classroom = body_stripped[10:].strip()
        if classroom:
            _set_command_context(phone, classroom=classroom)
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
        by_child[name].append(
            event.event_type.value.lower().replace("_", " ")
        )

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


async def _process_and_persist_events(
    db: Session,
    teacher: any,
    events: list,
    unrecognized_names: list,
    transcript: str,
) -> Response:

    recognized_events = []
    unrecognized_events = []

    for base_event in events:
        if base_event.child_name in unrecognized_names:
            unrecognized_events.append(base_event)
        else:
            recognized_events.append(base_event)

    # 1. Persist valid events immediately
    for base_event in recognized_events:
        child = get_child_by_name(
            db, teacher.center_id, base_event.child_name
        )
        child_id = child.id if child else None
        create_event_from_base(
            db, base_event, teacher_id=teacher.id, child_id=child_id
        )

    # 2. Persist unrecognized to pending table
    if unrecognized_events:
        for base_event in unrecognized_events:
            fb = PendingEvent(
                center_id=teacher.center_id,
                teacher_phone=teacher.phone,
                unrecognized_name=base_event.child_name,
                original_transcript=transcript,
                pending_event_data=json.loads(base_event.model_dump_json()),
            )
            db.add(fb)
        db.commit()

        names_str = ", ".join(unrecognized_names)
        msg = f"⚠️ I couldn't match '{names_str}' to your roster. Reply with their enrolled name, or type 'ignore'."

        if recognized_events:
            msg = _format_event_summary(recognized_events) + "\n\n" + msg

        return _build_twiml_response(msg)

    # 3. All valid
    return _build_twiml_response(_format_event_summary(recognized_events))


@router.post("/whatsapp")
async def whatsapp_webhook(
    From: str = Form(""),
    Body: str = Form(""),
    NumMedia: str = Form("0"),
    MediaUrl0: str = Form(None),
    MediaContentType0: str = Form(None),
    MessageSid: str = Form(None),
    ProfileName: str = Form(None),
    SmsStatus: str = Form(None),
    db: Session = Depends(get_db),
) -> Response:
    """Handle incoming WhatsApp messages from Twilio.

    Supports:
    - Voice messages (.ogg/.mp4) → transcribe → extract events → save to DB
    - Text commands (/child, /classroom)
    - Photo messages (stored for later attachment)
    """
    # Twilio sends From as "whatsapp:+1XXXXXXXXXX" — normalize to E.164
    phone = From.replace("whatsapp:", "").strip()
    body = Body.strip()
    num_media = int(NumMedia)

    logger.warning(
        f"=== INCOMING WHATSAPP ===\n  From: {phone}\n  Body: '{body}'\n  NumMedia: {num_media}"
    )

    # 1. Handle commands first (no DB lookup needed for parsing)
    command_reply = None
    is_child_command = False
    if body and not num_media:
        command_reply = _handle_command(phone, body)
        # /child with a valid name — don't return yet, need DB for pending photos
        is_child_command = (
            command_reply is not None
            and command_reply.startswith("✅")
            and body.strip().lower().startswith("/child")
        )
        if command_reply and not is_child_command:
            return _build_twiml_response(command_reply)

    # 2. Look up Teacher from DB
    teacher = get_teacher_by_phone(db, phone)
    if not teacher:
        logger.warning(f"Unregistered phone number hit webhook: {phone}")
        if command_reply:
            # Still return command reply for unregistered users
            return _build_twiml_response(command_reply)
        return _build_twiml_response(
            "❌ This phone number is not registered as a teacher account."
        )

    center_id = str(teacher.center_id)
    cmd_context = _get_command_context(phone)
    child_context = cmd_context.get("child_name")

    # 2.1 If /child command was just set, resolve any pending photos
    if is_child_command and child_context:
        reply = command_reply
        pending = get_pending_photos_by_teacher(db, teacher.id)
        if pending:
            child = get_child_by_name(db, teacher.center_id, child_context)
            if child:
                settings = get_settings()
                processed = 0
                for p in pending:
                    try:
                        child_record = get_child_for_processing(
                            child_id=child.id,
                            center_id=teacher.center_id,
                            db=db,
                            environment=settings.environment,
                            pipeline_stage="photo_upload",
                        )
                        if child_record is None:
                            logger.warning(
                                f"No consent for child {child.id} — discarding pending photo {p.id}"
                            )
                            delete_s3_object(p.s3_temp_key)
                            delete_pending_photo(db, p.id)
                            continue

                        clean_bytes = download_from_s3(p.s3_temp_key)
                        final_key = build_photo_s3_key(teacher.center_id, child.id)
                        upload_photo(clean_bytes, final_key)
                        create_photo(
                            db,
                            center_id=teacher.center_id,
                            child_id=child.id,
                            s3_key=final_key,
                            caption=p.caption,
                            content_type=p.content_type,
                        )
                        delete_s3_object(p.s3_temp_key)
                        delete_pending_photo(db, p.id)
                        processed += 1
                    except Exception as e:
                        logger.error(f"Failed to resolve pending photo {p.id}: {e}", exc_info=True)

                if processed:
                    reply += f"\n📷 {processed} photo(s) saved for {child_context}."
            else:
                reply += f"\n⚠️ {len(pending)} photo(s) pending — '{child_context}' not found in roster."
        return _build_twiml_response(reply)

    # 2.5 Check Fallback Loop
    if body and not num_media:

        pending_pendings = (
            db.query(PendingEvent).filter_by(teacher_phone=phone).all()
        )
        if pending_pendings:
            if body.lower() == "ignore":
                for fb in pending_pendings:
                    db.delete(fb)
                db.commit()
                return _build_twiml_response(
                    "✅ Ignored. Those events have been discarded."
                )
            else:
                new_name = body.strip()
                child = get_child_by_name(db, teacher.center_id, new_name)
                child_id = child.id if child else None

                events_created = 0
                for fb in pending_pendings:
                    raw_event = fb.pending_event_data
                    raw_event["child_name"] = new_name
                    raw_event["id"] = str(uuid.uuid4())

                    try:
                        base_event = BaseEvent(**raw_event)
                        create_event_from_base(
                            db,
                            base_event,
                            teacher_id=teacher.id,
                            child_id=child_id,
                        )
                        events_created += 1
                        db.delete(fb)
                    except Exception as e:
                        logger.error(
                            f"Failed to restore pending event: {e}"
                        )

                db.commit()
                if not child_id:
                    return _build_twiml_response(
                        f"⚠️ Logged {events_created} event(s) for '{new_name}', but it still doesn't exactly match your roster. Director review required."
                    )
                return _build_twiml_response(
                    f"✅ Got it! Logged {events_created} event(s) for {new_name}."
                )

    # 3. Handle Voice Messages
    if (
        num_media >= 1
        and MediaContentType0
        and ("audio" in MediaContentType0 or "video" in MediaContentType0)
    ):
        try:
            # Download & Transcribe
            audio_bytes, content_type = await download_twilio_media(
                MediaUrl0
            )
            ext = "ogg" if "ogg" in content_type else "mp4"
            transcript = await transcribe_audio(
                audio_bytes, f"voice_memo.{ext}"
            )

            # Zero retention for audio — immediately delete from Twilio and clear memory

            # Fire and forget Twilio deletion
            asyncio.create_task(delete_twilio_media(MediaUrl0))
            del audio_bytes
            gc.collect()

            # 1. Fetch known children for context
            center_children = get_children_by_center(db, teacher.center_id)
            known_names = [c.name for c in center_children]

            # 2. Extract
            events, unrecognized_names = await extract_events(
                transcript=transcript,
                center_id=center_id,
                child_name=child_context,
                known_children=known_names,
                db=db,
            )

            # 3. Route to Database
            return await _process_and_persist_events(
                db=db,
                teacher=teacher,
                events=events,
                unrecognized_names=unrecognized_names,
                transcript=transcript,
            )

        except Exception as e:
            logger.error(f"Voice pipeline failed: {e}", exc_info=True)
            return _build_twiml_response(
                "❌ Sorry, I had trouble processing that voice memo. Please try again."
            )

    # 4. Handle Text as a Note
    if body and not num_media:
        try:
            # Extract
            center_children = get_children_by_center(db, teacher.center_id)
            known_names = [c.name for c in center_children]

            events, unrecognized_names = await extract_events(
                transcript=body,
                center_id=center_id,
                child_name=child_context,
                known_children=known_names,
                db=db,
            )

            return await _process_and_persist_events(
                db=db,
                teacher=teacher,
                events=events,
                unrecognized_names=unrecognized_names,
                transcript=body,
            )
        except Exception as e:
            logger.error(f"Extraction from text failed: {e}", exc_info=True)
            return _build_twiml_response(
                "❌ Sorry, I had trouble processing that message. Please try again."
            )

    # 5. Handle Photos
    if (
        num_media >= 1
        and MediaContentType0
        and "image" in MediaContentType0
    ):
        try:
            # Download from Twilio immediately
            photo_bytes, content_type = await download_twilio_media(MediaUrl0)

            # Zero retention — delete from Twilio (fire-and-forget, matches audio pattern)
            asyncio.create_task(delete_twilio_media(MediaUrl0))

            # Strip EXIF immediately — no raw metadata in S3, even temporarily
            clean_bytes = strip_exif(photo_bytes)
            del photo_bytes
            gc.collect()

            caption = body if body else None
            settings = get_settings()

            if child_context:
                # Happy path: child context is set → full pipeline
                child = get_child_by_name(db, teacher.center_id, child_context)
                if not child:
                    return _build_twiml_response(
                        f"❌ Child '{child_context}' not found in roster. Photo not saved."
                    )

                child_record = get_child_for_processing(
                    child_id=child.id,
                    center_id=teacher.center_id,
                    db=db,
                    environment=settings.environment,
                    pipeline_stage="photo_upload",
                )
                if child_record is None:
                    return _build_twiml_response(
                        f"❌ No parental consent for {child_context}. Photo not saved."
                    )

                s3_key = build_photo_s3_key(teacher.center_id, child.id)
                upload_photo(clean_bytes, s3_key)
                create_photo(
                    db,
                    center_id=teacher.center_id,
                    child_id=child.id,
                    s3_key=s3_key,
                    caption=caption,
                    content_type="image/jpeg",
                )
                logger.info(f"Photo saved for {child_context} (child_id={child.id})")
                msg = f"📷 Photo saved for {child_context}."
                if caption:
                    msg += f' Caption: "{caption}"'
                return _build_twiml_response(msg)
            else:
                # No child context → store as pending, prompt teacher
                s3_temp_key = build_pending_s3_key(teacher.center_id, teacher.id)
                upload_photo(clean_bytes, s3_temp_key)
                expires_at = datetime.now(UTC) + timedelta(minutes=30)
                create_pending_photo(
                    db,
                    center_id=teacher.center_id,
                    teacher_id=teacher.id,
                    s3_temp_key=s3_temp_key,
                    caption=caption,
                    content_type="image/jpeg",
                    expires_at=expires_at,
                )
                logger.info(f"Photo stored as pending for teacher {teacher.id}")
                return _build_twiml_response(
                    "📷 Photo received! Please assign it to a child with /child [name]"
                )

        except Exception as e:
            logger.error(f"Photo processing failed: {e}", exc_info=True)
            return _build_twiml_response(
                "❌ Sorry, I had trouble processing that photo. Please try again."
            )

    # 6. Fallback
    return _build_twiml_response(
        "👋 Hi! Send a voice memo to log events, or use /child [name] to set context."
    )
