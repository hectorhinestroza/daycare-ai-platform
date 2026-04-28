"""Daily EOD narrative scheduler.

Runs every hour at :00. For each center, checks if the center's local time
is 5 PM on a weekday — if so, generates EOD narratives for all active children.

This per-center approach means a center in LA gets its reports at 5 PM PT,
not 5 PM ET, without needing a separate cron job per timezone.

Rules:
- Skips children with admin-overridden narratives (never overwrite).
- Regenerates if a narrative already exists (picks up any late-day events).
- Uses each center's own timezone for both the fire-time check and the date.
- Registered once in main.py lifespan; shuts down cleanly on app exit.
"""

import logging
from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from backend.services.narrative import generate_narrative
from backend.storage.database import SessionLocal
from backend.storage.models import Center, Child
from backend.storage.narrative_handlers import get_narrative, upsert_narrative

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

    scheduler.start()
    logger.info("Narrative scheduler started — ticks hourly, generates at 5 PM per center timezone")
    return scheduler
