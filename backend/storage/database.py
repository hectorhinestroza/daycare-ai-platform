"""Database engine, session factory, and Base for SQLAlchemy ORM.

Usage:
    from backend.database import get_db, Base

    # In FastAPI endpoints:
    @router.post("/events")
    async def create(db: Session = Depends(get_db)):
        ...
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base, Session
from typing import Generator
from backend.config import get_settings

settings = get_settings()

engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,      # verify connections are alive before using
    pool_size=5,              # max 5 persistent connections
    max_overflow=10,          # up to 10 overflow connections under load
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
