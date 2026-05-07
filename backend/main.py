
import logging
from contextlib import asynccontextmanager
from typing import Dict

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import backend.storage.models  # noqa: F401 — register all models with Base

# Configure structured logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)

# Load .env before anything else
load_dotenv()

# TODO(pilot): Sentry init is currently inline here as a stub.
#   Once a real DSN is provisioned, revisit this:
#     - Move to a dedicated backend/observability/sentry.py module
#     - Tune traces_sample_rate (currently 0.0 — no perf data)
#     - Verify pii_scrubber works against real events (raise inside extraction
#       with a transcript and confirm "[redacted]" in the Sentry UI)
#     - Add release tagging (git_sha) once /health exposes it (Phase 4)
import sentry_sdk

from backend.config import get_settings
from backend.utils.safe_logging import pii_scrubber

_sentry_settings = get_settings()
if _sentry_settings.sentry_dsn:
    try:
        sentry_sdk.init(
            dsn=_sentry_settings.sentry_dsn.strip(),
            environment=_sentry_settings.environment,
            traces_sample_rate=_sentry_settings.sentry_traces_sample_rate,
            send_default_pii=False,
            before_send=pii_scrubber,
        )
        logger.info("Sentry initialized")
    except Exception as e:
        # Malformed DSN must not crash the app. Warn loudly so it gets fixed.
        logger.error(f"Sentry init failed ({type(e).__name__}: {e}) — continuing without Sentry")
else:
    logger.info("Sentry DSN not set — SDK init skipped (no-op)")

from backend.middleware import (
    GlobalExceptionMiddleware,
    RequestIDMiddleware,
    RequestTimingMiddleware,
)
from backend.routers.activity import router as activity_router
from backend.routers.consent import router as consent_router
from backend.routers.events import router as events_router
from backend.routers.narratives import router as narratives_router
from backend.routers.onboarding import router as onboarding_router
from backend.routers.photos import router as photos_router
from backend.routers.whatsapp import router as whatsapp_router
from backend.services.scheduler import start_scheduler
from backend.startup.legal_checks import get_legal_status_fields
from backend.storage.database import Base, engine


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Create DB tables on startup (dev mode). Alembic handles prod migrations."""

    Base.metadata.create_all(bind=engine)
    logger.info("Database tables created / verified")

    scheduler = start_scheduler()
    yield
    scheduler.shutdown(wait=False)
    logger.info("Shutting down")


app = FastAPI(
    title="Daycare AI Platform API",
    lifespan=lifespan,
)

# Middleware (order matters — outermost first)
app.add_middleware(GlobalExceptionMiddleware)
app.add_middleware(RequestTimingMiddleware)
app.add_middleware(RequestIDMiddleware)

# CORS — allow all origins (credentials=False required for wildcard origin)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(activity_router)
app.include_router(consent_router)
app.include_router(events_router)
app.include_router(narratives_router)
app.include_router(onboarding_router)
app.include_router(photos_router)
app.include_router(whatsapp_router)


@app.get("/")
async def root() -> Dict[str, str]:
    return {"status": "ok", "message": "Daycare AI Platform API is running"}


@app.get("/health")
async def health() -> Dict:
    """Health check — includes passive legal DPA status for observability.

    Legal fields show False if env vars missing — a reminder, not a wall.
    DPAs are a one-time founder action documented in README_LEGAL.md.
    """
    return {
        "status": "healthy",
        "legal": get_legal_status_fields(),
    }
