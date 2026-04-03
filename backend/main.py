import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from typing import Dict
from dotenv import load_dotenv

# Configure structured logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)

# Load .env before anything else
load_dotenv()

from backend.routers.whatsapp import router as whatsapp_router
from backend.storage.database import engine, Base
from backend.middleware import (
    RequestIDMiddleware,
    RequestTimingMiddleware,
    GlobalExceptionMiddleware,
)


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

# Routers
app.include_router(whatsapp_router)


@app.get("/")
async def root() -> Dict[str, str]:
    return {"status": "ok", "message": "Daycare AI Platform API is running"}


@app.get("/health")
async def health() -> Dict[str, str]:
    return {"status": "healthy"}
