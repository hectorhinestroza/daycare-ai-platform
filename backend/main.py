import logging
from contextlib import asynccontextmanager
from typing import Dict

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# Configure structured logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)

# Load .env before anything else
load_dotenv()

from backend.middleware import (
    GlobalExceptionMiddleware,
    RequestIDMiddleware,
    RequestTimingMiddleware,
)
from backend.routers.activity import router as activity_router
from backend.routers.events import router as events_router
from backend.routers.onboarding import router as onboarding_router
from backend.routers.whatsapp import router as whatsapp_router
from backend.storage.database import Base, engine


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Create DB tables on startup (dev mode). Alembic handles prod migrations."""
    import backend.storage.models  # noqa: F401 — register all models with Base

    Base.metadata.create_all(bind=engine)
    logger.info("Database tables created / verified")
    yield
    logger.info("Shutting down")


app = FastAPI(
    title="Daycare AI Platform API",
    lifespan=lifespan,
)

# Middleware (order matters — outermost first)
app.add_middleware(GlobalExceptionMiddleware)
app.add_middleware(RequestTimingMiddleware)
app.add_middleware(RequestIDMiddleware)

# CORS — allow React dev server and mobile device testing
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for dev testing
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(activity_router)
app.include_router(events_router)
app.include_router(onboarding_router)
app.include_router(whatsapp_router)


@app.get("/")
async def root() -> Dict[str, str]:
    return {"status": "ok", "message": "Daycare AI Platform API is running"}


@app.get("/health")
async def health() -> Dict[str, str]:
    return {"status": "healthy"}
