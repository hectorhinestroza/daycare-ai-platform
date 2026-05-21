"""WhatsApp webhook router for Twilio (Issue #1 and #4)."""

import asyncio
import gc
import hashlib
import json
import logging
import time
import uuid
from datetime import UTC, datetime, timedelta
from typing import Dict, Optional

from fastapi import APIRouter, Depends, Form, Response
from sqlalchemy import text
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
    fan_out_batch_event,
    get_child_by_name,
    get_children_by_center,
    get_pending_photos_by_teacher,
    get_teacher_by_phone,
)
from backend.storage.models import PendingEvent
from backend.utils.consent_gate import get_child_for_processing
from backend.utils.media import delete_twilio_media_with_retry, download_twilio_media
from backend.utils.photo import build_pending_s3_key, build_photo_s3_key, strip_exif
from backend.utils.s3 import delete_photo as delete_s3_object
from backend.utils.s3 import download_from_s3, upload_photo
from backend.utils.safe_logging import safe_log
from backend.utils.twilio_security import verify_twilio_signature
from schemas.events import BaseEvent

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhook", tags=["whatsapp"])

# In-memory context store for /child and /classroom commands
# Key: phone number, Value: dict
_command_context: Dict[str, dict] = {}


def _phone_hash(phone: str) -> str:
    """Short stable hash of a phone number for log correlation (no PII)."""
    return hashlib.sha256((phone or "").encode()).hexdigest()[:8]


def _build_twiml_response(message: str) -> Response:
    """Build a TwiML XML response for Twilio."""
    twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Message>{message}</Message>
</Response>"""
    return Response(content=twiml, media_type="application/xml")


def _build_empty_twiml() -> Response:
    """Empty TwiML — used for retries we've already processed (no double-reply to teacher)."""
    return Response(
        content='<?xml version="1.0" encoding="UTF-8"?><Response/>',
        media_type="application/xml",
    )


def _claim_message_sid(db: Session, message_sid: str) -> bool:
    """Atomically claim a Twilio MessageSid.

    Returns True if this is the first time we've seen the SID (caller should
    process the message); False if the SID was already processed (caller should
    short-circuit with an empty TwiML).

    Commits the claim row immediately so a crash mid-processing doesn't leave
    us re-running the pipeline on the next Twilio retry.
    """
    if not message_sid:
        # Twilio always sends MessageSid, but be defensive: if missing, don't
        # block processing — just skip dedup.
        return True

    # CURRENT_TIMESTAMP is portable across Postgres and SQLite (used in tests).
    row = db.execute(
        text(
            "INSERT INTO processed_messages (message_sid, processed_at) "
            "VALUES (:sid, CURRENT_TIMESTAMP) "
            "ON CONFLICT (message_sid) DO NOTHING "
            "RETURNING message_sid"
        ),
        {"sid": message_sid},
    ).fetchone()
    db.commit()
    return row is not None


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


def _format_event_summary(events: list, auto_approved_ids: set) -> str:
    """Format a confirmation message summarizing extracted events.

    auto_approved_ids: set of event IDs (as str or UUID) that were auto-approved
    at persist time. Used to split the summary into auto-approved vs. pending review.
    """
    if not events:
        return "🤔 I couldn't extract any events from that memo. Could you try again?"

    def _label(e) -> str:
        return "All children" if getattr(e, "applies_to_all", False) else e.child_name

    def _type_str(e) -> str:
        return e.event_type.value.lower().replace("_", " ")

    auto: Dict[str, list] = {}
    pending: Dict[str, list] = {}

    for event in events:
        bucket = auto if str(event.id) in {str(i) for i in auto_approved_ids} else pending
        name = _label(event)
        bucket.setdefault(name, []).append(_type_str(event))

    def _summarise_bucket(bucket: Dict[str, list]) -> str:
        parts = []
        for child, types in bucket.items():
            type_summary = ", ".join(f"{types.count(t)} {t}" for t in dict.fromkeys(types))
            parts.append(f"{child} ({type_summary})")
        return " and ".join(parts)

    total = len(events)
    msg = f"Got it! Logged {total} event{'s' if total != 1 else ''}."

    if auto:
        msg += f"\n✅ Auto-approved: {_summarise_bucket(auto)}."
    if pending:
        msg += f"\n⏳ Sent for review: {_summarise_bucket(pending)}."

    return msg


async def _process_and_persist_events(
    db: Session,
    teacher: any,
    events: list,
    unrecognized_names: list,
    transcript: str,
    phone: Optional[str] = None,
    child_context: Optional[str] = None,
) -> Response:

    recognized_events = []
    unrecognized_events = []
    batch_fan_out_count = 0
    auto_approved_ids: set = set()

    for base_event in events:
        if base_event.child_name in unrecognized_names:
            unrecognized_events.append(base_event)
        else:
            recognized_events.append(base_event)

    # 1. Persist valid events immediately (consent-gated per child)
    settings = get_settings()
    blocked_count = 0
    for base_event in recognized_events:
        if getattr(base_event, "applies_to_all", False):
            # Group event — fan out to all active children in the teacher's room.
            # The fan-out function gates each child individually.
            created = fan_out_batch_event(
                db, teacher.center_id, teacher.id, base_event,
                environment=settings.environment,
            )
            batch_fan_out_count += len(created)
            auto_approved_ids.update(str(e.id) for e in created if e.status == "APPROVED")
            logger.info(
                f"Batch fan-out: {len(created)} events created for teacher {teacher.id}"
            )
        else:
            child = get_child_by_name(db, teacher.center_id, base_event.child_name)
            if child is not None:
                # Consent gate: in production, blocks events for children without
                # active parental consent and queues them in pending_consent_queue.
                gated = get_child_for_processing(
                    child_id=child.id,
                    center_id=teacher.center_id,
                    db=db,
                    environment=settings.environment,
                    pipeline_stage="event_extraction",
                    raw_event_ref=base_event.model_dump_json(),
                )
                if gated is None:
                    blocked_count += 1
                    logger.info(
                        f"consent_gate.blocked_event child_id={child.id} "
                        f"center_id={teacher.center_id}"
                    )
                    continue
            child_id = child.id if child else None
            db_event = create_event_from_base(db, base_event, teacher_id=teacher.id, child_id=child_id)
            if db_event.status == "APPROVED":
                auto_approved_ids.add(str(base_event.id))

    # 1.5 If the transcript named a child different from the /child context,
    # honor what was actually said and clear the stale context.
    context_cleared_for: Optional[str] = None
    if child_context and phone and recognized_events:
        spoken_names = {e.child_name for e in recognized_events}
        if all(n.lower() != child_context.lower() for n in spoken_names):
            _command_context.get(phone, {}).pop("child_name", None)
            context_cleared_for = ", ".join(sorted(spoken_names))

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
            msg = _format_event_summary(recognized_events, auto_approved_ids) + "\n\n" + msg

        if context_cleared_for:
            msg += f"\n\nℹ️ Cleared /child context — transcript named {context_cleared_for}."

        return _build_twiml_response(msg)

    # 3. All valid
    msg = _format_event_summary(recognized_events, auto_approved_ids)
    if context_cleared_for:
        msg += f"\n\nℹ️ Cleared /child context — transcript named {context_cleared_for}."
    return _build_twiml_response(msg)


@router.post("/whatsapp", dependencies=[Depends(verify_twilio_signature)])
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
    webhook_start = time.monotonic()

    # Twilio sends From as "whatsapp:+1XXXXXXXXXX" — normalize to E.164
    phone = From.replace("whatsapp:", "").strip()
    body = Body.strip()
    num_media = int(NumMedia)
    has_audio = bool(MediaContentType0 and ("audio" in MediaContentType0 or "video" in MediaContentType0))
    has_image = bool(MediaContentType0 and "image" in MediaContentType0)

    # Dedup Twilio retries before doing any work.
    if not _claim_message_sid(db, MessageSid):
        safe_log(logger, "info", "webhook.duplicate_message", message_sid=MessageSid)
        return _build_empty_twiml()

    safe_log(
        logger, "info", "webhook.received",
        message_sid=MessageSid,
        body_length=len(body),
        num_media=num_media,
        has_audio=has_audio,
        has_image=has_image,
        phone_hash=_phone_hash(phone),
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
        safe_log(logger, "warning", "webhook.teacher_unknown", phone_hash=_phone_hash(phone))
        if command_reply:
            # Still return command reply for unregistered users
            return _build_twiml_response(command_reply)
        return _build_twiml_response(
            "❌ This phone number is not registered as a teacher account."
        )

    safe_log(
        logger, "info", "webhook.teacher_resolved",
        teacher_id=str(teacher.id), center_id=str(teacher.center_id),
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
                                "consent_gate.blocked_pending_photo child_id=%s pending_photo_id=%s",
                                child.id, p.id,
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
                        logger.error(
                            "photo.pending_resolve_failed pending_photo_id=%s error_type=%s",
                            p.id, type(e).__name__, exc_info=True,
                        )

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
                            "pending_event.restore_failed pending_event_id=%s error_type=%s",
                            fb.id, type(e).__name__,
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
        # Kill switch — skip the AI pipeline entirely. Still delete the audio
        # from Twilio (zero-retention compliance is independent of extraction).
        settings = get_settings()
        if settings.extraction_disabled:
            asyncio.create_task(delete_twilio_media_with_retry(MediaUrl0))
            safe_log(logger, "warning", "extraction.disabled", message_sid=MessageSid)
            return _build_twiml_response(
                "📩 Recording received — pending review. (AI extraction is currently paused; "
                "your director will follow up.)"
            )

        try:
            # Fetch known children up front — used as a Whisper transcription
            # hint AND as roster context for the GPT-4o extractor. Whisper
            # biases its output toward terms in the prompt, which materially
            # improves spelling for unusual names like "Clara", "Loie", "Emi".
            center_children = get_children_by_center(db, teacher.center_id)
            known_names = [c.name for c in center_children if c.name]
            whisper_prompt = (
                f"Children at this daycare: {', '.join(known_names)}."
                if known_names else None
            )

            # Download & Transcribe
            audio_bytes, content_type = await download_twilio_media(
                MediaUrl0
            )
            ext = "ogg" if "ogg" in content_type else "mp4"
            transcript = await transcribe_audio(
                audio_bytes, f"voice_memo.{ext}",
                prompt=whisper_prompt,
            )

            # Zero retention for audio — immediately delete from Twilio and clear memory

            # Fire and forget Twilio deletion
            asyncio.create_task(delete_twilio_media_with_retry(MediaUrl0))
            del audio_bytes
            gc.collect()

            # 2. Extract
            events, unrecognized_names = await extract_events(
                transcript=transcript,
                center_id=center_id,
                child_name=child_context,
                known_children=known_names,
                teacher_name=teacher.name,
                db=db,
            )

            # 3. Route to Database
            return await _process_and_persist_events(
                db=db,
                teacher=teacher,
                events=events,
                unrecognized_names=unrecognized_names,
                transcript=transcript,
                phone=phone,
                child_context=child_context,
            )

        except Exception as e:
            logger.error(
                "voice_pipeline.failed error_type=%s",
                type(e).__name__, exc_info=True,
            )
            return _build_twiml_response(
                "❌ Sorry, I had trouble processing that voice memo. Please try again."
            )

    # 4. Handle Text as a Note
    if body and not num_media:
        if get_settings().extraction_disabled:
            safe_log(logger, "warning", "extraction.disabled", message_sid=MessageSid)
            return _build_twiml_response(
                "📩 Note received — pending review. (AI extraction is currently paused.)"
            )
        try:
            # Extract
            center_children = get_children_by_center(db, teacher.center_id)
            known_names = [c.name for c in center_children]

            events, unrecognized_names = await extract_events(
                transcript=body,
                center_id=center_id,
                child_name=child_context,
                known_children=known_names,
                teacher_name=teacher.name,
                db=db,
            )

            return await _process_and_persist_events(
                db=db,
                teacher=teacher,
                events=events,
                unrecognized_names=unrecognized_names,
                transcript=body,
                phone=phone,
                child_context=child_context,
            )
        except Exception as e:
            logger.error(
                "text_extraction.failed error_type=%s",
                type(e).__name__, exc_info=True,
            )
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
            asyncio.create_task(delete_twilio_media_with_retry(MediaUrl0))

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
                logger.info("photo.saved child_id=%s", child.id)
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
            logger.error(
                "photo_pipeline.failed error_type=%s",
                type(e).__name__, exc_info=True,
            )
            return _build_twiml_response(
                "❌ Sorry, I had trouble processing that photo. Please try again."
            )

    # 6. Fallback
    return _build_twiml_response(
        "👋 Hi! Send a voice memo to log events, or use /child [name] to set context."
    )
