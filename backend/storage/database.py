"""Database engine, session factory, and Base for SQLAlchemy ORM.

Usage:
    from backend.database import get_db, Base

    # In FastAPI endpoints:
    @router.post("/events")
    async def create(db: Session = Depends(get_db)):
        ...
"""

from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, declarative_base, sessionmaker

from backend.config import get_settings

settings = get_settings()

engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,    # verify connections are alive before checkout
    # Pool sized for pilot traffic: 4-5 teachers, ~10 parents polling every 10s,
    # the director, plus background narrative-refresh tasks that hold a
    # connection during ~10s GPT-4o calls. The original 5+10=15 exhausted under
    # real load on day 1 and timed out new requests at 30s. Railway Postgres
    # defaults to ~100 max_connections so 20+40=60 leaves comfortable headroom.
    pool_size=20,
    max_overflow=40,
    # Force recycle every 30 min so we don't hold onto stale TCP connections
    # if Railway Postgres or the network drops idle ones server-side.
    pool_recycle=1800,
    # Fail fast (10s) instead of stalling 30s waiting on a free connection —
    # surfaces capacity issues sooner and lets the client retry without a
    # half-minute hang.
    pool_timeout=10,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency that yields a DB session per request.

    Usage in endpoint: db: Session = Depends(get_db)
    Session auto-closes after the request completes (RAII pattern).
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
