
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

# Initialize Sentry as early as possible. Empty DSN → init is a no-op.
import sentry_sdk  # noqa: E402

from backend.config import get_settings  # noqa: E402
from backend.utils.safe_logging import pii_scrubber  # noqa: E402

_sentry_settings = get_settings()
if _sentry_settings.sentry_dsn:
    sentry_sdk.init(
        dsn=_sentry_settings.sentry_dsn,
        environment=_sentry_settings.environment,
        traces_sample_rate=_sentry_settings.sentry_traces_sample_rate,
        send_default_pii=False,
        before_send=pii_scrubber,
    )
    logger.info("Sentry initialized")
else:
    logger.info("Sentry DSN not set — SDK init skipped (no-op)")

from backend.middleware import (  # noqa: E402
    GlobalExceptionMiddleware,
    RequestIDMiddleware,
    RequestTimingMiddleware,
)
from backend.routers.activity import router as activity_router  # noqa: E402
from backend.routers.consent import router as consent_router  # noqa: E402
from backend.routers.events import router as events_router  # noqa: E402
from backend.routers.narratives import router as narratives_router  # noqa: E402
from backend.routers.onboarding import router as onboarding_router  # noqa: E402
from backend.routers.photos import router as photos_router  # noqa: E402
from backend.routers.whatsapp import router as whatsapp_router  # noqa: E402
from backend.services.scheduler import start_scheduler  # noqa: E402
from backend.startup.legal_checks import get_legal_status_fields  # noqa: E402
from backend.storage.database import Base, engine  # noqa: E402


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
