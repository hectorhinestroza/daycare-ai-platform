"""Scheduler — EOD narratives + pending photo cleanup.

Jobs:
1. EOD narratives: Runs every hour at :00. For each center, checks if the
   center's local time is 5 PM on a weekday — if so, generates EOD narratives.
2. Pending photo cleanup: Runs every 10 minutes. Deletes pending photos that
   have passed their 30-minute expiry (S3 object + DB row).

Registered once in main.py lifespan; shuts down cleanly on app exit.
"""

import logging
from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger

from backend.services.narrative import generate_narrative
from backend.storage.database import SessionLocal
from backend.storage.events_handlers import delete_pending_photo, get_expired_pending_photos
from backend.storage.models import Center, Child
from backend.storage.narrative_handlers import get_narrative, upsert_narrative
from backend.utils.s3 import delete_photo as delete_s3_object

logger = logging.getLogger(__name__)

_EOD_HOUR = 17  # 5 PM local center time


async def _generate_all_centers() -> None:
    """Hourly tick — generate EOD narratives for centers currently at 5 PM local."""
    db = SessionLocal()
    generated = failed = skipped = 0

    try:
        centers = db.query(Center).all()

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
                        f"Scheduler: generated narrative for {child.name} ({child.id}) "
                        f"on {target_date} — tone={result['tone']}"
                    )
                except Exception as e:
                    failed += 1
                    logger.error(
                        f"Scheduler: failed narrative for {child.name} ({child.id}): {e}",
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

    scheduler.start()
    logger.info("Scheduler started — EOD narratives (hourly) + pending photo cleanup (every 10 min)")
    return scheduler
