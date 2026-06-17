"""Seed a local SQLite DB for frontend dev — skips Twilio, no token needed.

Why this exists
---------------
Running `npm run dev` against a real backend normally requires a valid
bearer token in sessionStorage. The backend (`backend/utils/pilot_auth.py`)
already bypasses token verification when `ENVIRONMENT=development` AND
the request has no Authorization header — so as long as the backend runs
locally in dev mode, the frontend can hit it cold without auth setup.

This script creates a SQLite database with the minimum data needed for
the director console to render something useful (one center, two rooms,
two teachers, three kids), so the UI isn't an empty shell.

Usage
-----
    python scripts/seed_local_dev.py

Then in two terminals:

    # Terminal 1 — backend
    ENVIRONMENT=development \
    DATABASE_URL=sqlite:///./local.db \
    AUTH_TOKEN_SECRET=devsecret \
    uvicorn backend.main:app --reload --port 8000

    # Terminal 2 — frontend
    cd frontend/console
    VITE_API_URL=http://localhost:8000 npm run dev

Then visit the printed director URL.

Re-running this script is a no-op if the seed center already exists.
"""

import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

# Ensure repo root is importable so `backend.*` resolves whether the script is
# invoked as `python scripts/seed_local_dev.py` or via an absolute path.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# Force local SQLite + dev env BEFORE we import any backend modules so the
# pydantic-settings cache reads the right values.
os.environ.setdefault("DATABASE_URL", "sqlite:///./local.db")
os.environ.setdefault("ENVIRONMENT", "development")
os.environ.setdefault("AUTH_TOKEN_SECRET", "devsecret")

# These imports MUST come after the env-var setup above.
from backend.storage.database import Base, SessionLocal, engine  # noqa: E402
import backend.storage.models  # noqa: F401, E402  populate Base.metadata
from backend.storage.models import Admin, Center, Child, Room, Teacher, TeacherClassroom  # noqa: E402


SEED_CENTER_NAME = "Sunshine Dev Daycare"


def main() -> int:
    # 1. Make sure schema exists.
    Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        existing = db.query(Center).filter(Center.name == SEED_CENTER_NAME).first()
        if existing is not None:
            _print_run_steps(existing.id)
            print(f"\n(seed already present — center_id {existing.id} reused)")
            return 0

        now = datetime.now(timezone.utc)

        center_id = uuid.uuid4()
        db.add(Center(
            id=center_id,
            name=SEED_CENTER_NAME,
            timezone="America/Los_Angeles",
            created_at=now,
        ))

        db.add(Admin(
            id=uuid.uuid4(),
            center_id=center_id,
            email="dev-director@example.com",
            name="Dev Director",
            phone="+15550199",
            role="director",
            is_active=True,
            created_at=now,
        ))

        toddlers_id = uuid.uuid4()
        preschool_id = uuid.uuid4()
        db.add(Room(id=toddlers_id, center_id=center_id, name="Toddlers"))
        db.add(Room(id=preschool_id, center_id=center_id, name="Preschool"))

        emi_id = uuid.uuid4()
        db.add(Teacher(
            id=emi_id,
            center_id=center_id,
            name="Ms. Emi",
            phone="+15550100",
        ))
        db.add(TeacherClassroom(
            teacher_id=emi_id,
            room_id=toddlers_id,
            center_id=center_id,
            is_primary=True,
        ))
        db.add(TeacherClassroom(
            teacher_id=emi_id,
            room_id=preschool_id,
            center_id=center_id,
            is_primary=False,
        ))

        sara_id = uuid.uuid4()
        db.add(Teacher(
            id=sara_id,
            center_id=center_id,
            name="Ms. Sara",
            phone="+15550101",
        ))
        db.add(TeacherClassroom(
            teacher_id=sara_id,
            room_id=preschool_id,
            center_id=center_id,
            is_primary=True,
        ))

        for kid_name, room in [
            ("Carlos", toddlers_id),
            ("Annie", toddlers_id),
            ("Loie", preschool_id),
        ]:
            db.add(Child(
                id=uuid.uuid4(),
                center_id=center_id,
                name=kid_name,
                room_id=room,
                status="ACTIVE",
            ))

        db.commit()
        print(f"Seeded {engine.url}")
        _print_run_steps(center_id)
        return 0
    finally:
        db.close()


def _print_run_steps(center_id) -> None:
    print()
    print(f"  center_id = {center_id}")
    print()
    print("Next steps:")
    print("  # Terminal 1 — backend")
    print("  ENVIRONMENT=development \\")
    print("    DATABASE_URL=sqlite:///./local.db \\")
    print("    AUTH_TOKEN_SECRET=devsecret \\")
    print("    uvicorn backend.main:app --reload --port 8000")
    print()
    print("  # Terminal 2 — frontend")
    print("  cd frontend/console")
    print("  VITE_API_URL=http://localhost:8000 npm run dev")
    print()
    print(f"  # Browser")
    print(f"  http://localhost:5173/director/{center_id}")


if __name__ == "__main__":
    sys.exit(main())
