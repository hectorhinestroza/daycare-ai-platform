"""Scheduler — EOD narratives + pending photo cleanup.

Jobs:
1. EOD narratives: Runs every hour at :00. For each center, checks if the
   center's local time is 5 PM on a weekday — if so, generates EOD narratives.
2. Pending photo cleanup: Runs every 10 minutes. Deletes pending photos that
   have passed their 30-minute expiry (S3 object + DB row).
3. Processed-messages cleanup: Runs nightly. Deletes Twilio dedup ledger
   rows older than 7 days (Twilio's retry window is much shorter).

Registered once in main.py lifespan; shuts down cleanly on app exit.
"""

import logging
import time
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from sqlalchemy import text

from backend.services.narrative import generate_narrative
from backend.storage.database import SessionLocal
from backend.storage.events_handlers import delete_pending_photo, get_expired_pending_photos
from backend.storage.models import Center, Child
from backend.storage.narrative_handlers import get_narrative, upsert_narrative
from backend.utils.s3 import delete_photo as delete_s3_object
from backend.utils.safe_logging import safe_log

logger = logging.getLogger(__name__)

_EOD_HOUR = 17  # 5 PM local center time


async def _generate_all_centers() -> None:
    """Hourly tick — generate EOD narratives for centers currently at 5 PM local."""
    db = SessionLocal()
    generated = failed = skipped = 0

    try:
        centers = db.query(Center).all()

        # Count how many centers are currently at 5 PM local on a weekday —
        # the eligibility predicate the loop below applies. Reported up-front
        # so observability sees the tick even when no center fires.
        eligible_centers = 0
        for c in centers:
            try:
                local_now = datetime.now(ZoneInfo(c.timezone or "UTC"))
                if local_now.hour == _EOD_HOUR and local_now.weekday() < 5:
                    eligible_centers += 1
            except Exception:
                pass
        safe_log(
            logger, "info", "scheduler.eod_tick",
            total_centers=len(centers),
            eligible_centers=eligible_centers,
        )

        for center in centers:
            tz_str = center.timezone or "UTC"
            try:
                local_now = datetime.now(ZoneInfo(tz_str))
            except (ZoneInfoNotFoundError, Exception):
                logger.warning(f"Center {center.id} has invalid timezone '{tz_str}', skipping")
                continue

            # Only fire at the 5 PM hour on weekdays (Mon=0 … Fri=4)
            if local_now.hour != _EOD_HOUR or local_now.weekday() >= 5:
                continue

            target_date = local_now.date()
            logger.info(
                f"Scheduler: running EOD for center {center.id} "
                f"({tz_str}) — {target_date}"
            )

            children = (
                db.query(Child)
                .filter(Child.center_id == center.id, Child.status == "ACTIVE")
                .all()
            )

            for child in children:
                existing = get_narrative(db, center.id, child.id, target_date)

                # Never overwrite a director-authored narrative
                if existing and existing.admin_override:
                    skipped += 1
                    continue

                try:
                    result = await generate_narrative(db, center.id, child.id, target_date)
                    upsert_narrative(
                        db,
                        center_id=center.id,
                        child_id=child.id,
                        target_date=target_date,
                        **{k: result[k] for k in ("headline", "body", "tone", "photo_captions")},
                    )
                    generated += 1
                    logger.info(
                        "scheduler.narrative_generated child_id=%s date=%s tone=%s",
                        child.id, target_date, result["tone"],
                    )
                except Exception as e:
                    failed += 1
                    logger.error(
                        "scheduler.narrative_failed child_id=%s error_type=%s",
                        child.id, type(e).__name__,
                        exc_info=True,
                    )

    except Exception as e:
        logger.error(f"Scheduler: tick crashed: {e}", exc_info=True)
    finally:
        db.close()

    if generated or failed:
        logger.info(
            f"Scheduler: EOD run complete — "
            f"{generated} generated, {failed} failed, {skipped} skipped (admin override)"
        )


async def _cleanup_processed_messages() -> None:
    """Delete Twilio dedup ledger rows older than 7 days.

    Twilio retries within ~1 day; 7 days gives a comfortable safety margin
    while keeping the table small.
    """
    db = SessionLocal()
    try:
        cutoff = datetime.now(timezone.utc) - timedelta(days=7)
        result = db.execute(
            text("DELETE FROM processed_messages WHERE processed_at < :cutoff"),
            {"cutoff": cutoff},
        )
        db.commit()
        if result.rowcount:
            logger.info(f"Scheduler: cleaned up {result.rowcount} processed_messages rows")
    except Exception as e:
        logger.error(f"Scheduler: processed_messages cleanup crashed: {e}", exc_info=True)
        try:
            db.rollback()
        except Exception:
            pass
    finally:
        db.close()


async def _cleanup_expired_pending_photos() -> None:
    """Delete pending photos that have passed their 30-minute expiry."""
    db = SessionLocal()
    cleaned = 0

    try:
        expired = get_expired_pending_photos(db)
        for pending in expired:
            try:
                delete_s3_object(pending.s3_temp_key)
            except Exception as e:
                logger.warning(f"Failed to delete S3 object {pending.s3_temp_key}: {e}")
            delete_pending_photo(db, pending.id)
            cleaned += 1

        if cleaned:
            logger.info(f"Scheduler: cleaned up {cleaned} expired pending photo(s)")
    except Exception as e:
        logger.error(f"Scheduler: pending photo cleanup crashed: {e}", exc_info=True)
    finally:
        db.close()


def start_scheduler() -> AsyncIOScheduler:
    """Create, configure, and start the async APScheduler instance.

    Returns the running scheduler so the caller can shut it down on app exit.
    """
    scheduler = AsyncIOScheduler()

    # Tick every hour at :00. The job itself checks each center's local time
    # and only acts on centers currently in the 5 PM hour.
    scheduler.add_job(
        _generate_all_centers,
        CronTrigger(minute=0),
        id="eod_narrative_generation",
        name="EOD narrative generation — hourly tick, fires per center at 5 PM local",
        replace_existing=True,
        misfire_grace_time=3600,  # fire up to 1 hr late if server was restarting
    )

    # Clean up expired pending photos every 10 minutes
    scheduler.add_job(
        _cleanup_expired_pending_photos,
        IntervalTrigger(minutes=10),
        id="pending_photo_cleanup",
        name="Pending photo cleanup — 30-min TTL, checks every 10 min",
        replace_existing=True,
    )

    # Clean up old Twilio dedup ledger rows nightly at 03:00 UTC
    scheduler.add_job(
        _cleanup_processed_messages,
        CronTrigger(hour=3, minute=0),
        id="processed_messages_cleanup",
        name="Processed-messages cleanup — drops dedup rows older than 7 days",
        replace_existing=True,
    )

    scheduler.start()
    logger.info(
        "Scheduler started — EOD narratives (hourly), pending photo cleanup "
        "(every 10 min), processed-messages cleanup (nightly 03:00 UTC)"
    )
    return scheduler
