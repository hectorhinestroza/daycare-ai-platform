"""Provision a new center on any environment (Railway prod, staging, local).

Creates the center row, a director admin row, and mints a bootstrap director
URL — all in one shot. Safe to run against production: it never touches
existing centers.

Usage (Railway production):

    DATABASE_URL='postgresql://...' \
    AUTH_TOKEN_SECRET='...' \
    APP_BASE_URL='https://daycare-ai-platform-production.up.railway.app' \
    PYTHONPATH=. \
    python scripts/provision_center.py \
        --name "My Test Center" \
        --director-email "me@example.com" \
        --director-name "Hector" \
        --timezone "America/Los_Angeles"

Usage (local SQLite):

    DATABASE_URL=sqlite:///./local.db \
    AUTH_TOKEN_SECRET=devsecret \
    APP_BASE_URL=http://localhost:5173 \
    PYTHONPATH=. \
    python scripts/provision_center.py \
        --name "Test Center" \
        --director-email "test@example.com"

Options:
  --name              Center display name (required)
  --director-email    Director admin email (required, must be unique across DB)
  --director-name     Director display name (default: "Director")
  --timezone          IANA tz string (default: America/New_York)
  --days              Token validity in days (default: 90)
"""

import argparse
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from backend.config import get_settings
from backend.storage.database import Base, SessionLocal, engine
import backend.storage.models  # noqa: F401  populates Base.metadata
from backend.storage.models import Admin, Center
from backend.utils.auth_tokens import generate_token


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--name", required=True, help="Center display name")
    parser.add_argument(
        "--director-email", required=True, help="Director email (unique)"
    )
    parser.add_argument(
        "--director-name", default="Director", help="Director display name"
    )
    parser.add_argument(
        "--timezone", default="America/New_York", help="IANA timezone string"
    )
    parser.add_argument(
        "--days", type=int, default=90, help="Director token validity in days"
    )
    args = parser.parse_args()

    settings = get_settings()
    if not settings.auth_token_secret:
        sys.stderr.write("AUTH_TOKEN_SECRET is not set — aborting\n")
        return 1

    # For SQLite local dev, ensure schema exists.
    if "sqlite" in str(engine.url):
        Base.metadata.create_all(bind=engine)

    db = SessionLocal()
    try:
        # Guard: don't create duplicates.
        existing = db.query(Center).filter(Center.name == args.name).first()
        if existing:
            sys.stderr.write(
                f"Center '{args.name}' already exists (id={existing.id}).\n"
                "Use a different --name or run mint_first_director_token.py to issue a new URL.\n"
            )
            return 1

        email_taken = db.query(Admin).filter(Admin.email == args.director_email).first()
        if email_taken:
            sys.stderr.write(
                f"Email '{args.director_email}' is already registered as an admin.\n"
                "Use a different --director-email.\n"
            )
            return 1

        now = datetime.now(timezone.utc)
        center_id = uuid.uuid4()
        admin_id = uuid.uuid4()

        db.add(
            Center(
                id=center_id,
                name=args.name,
                timezone=args.timezone,
                created_at=now,
            )
        )
        db.add(
            Admin(
                id=admin_id,
                center_id=center_id,
                email=args.director_email,
                name=args.director_name,
                role="director",
                is_active=True,
                created_at=now,
            )
        )
        db.commit()

    finally:
        db.close()

    # Mint director bootstrap URL.
    token, payload = generate_token(
        role="director",
        sub=admin_id,
        center_id=center_id,
        expires_in_days=args.days,
    )

    base = settings.app_base_url.rstrip("/")
    url = f"{base}/app?token={token}"

    print()
    print(f"Center provisioned: {args.name}")
    print(f"  center_id  : {center_id}")
    print(f"  admin_id   : {admin_id}")
    print(f"  timezone   : {args.timezone}")
    print()
    print("Director bootstrap URL (open once to activate session):")
    print()
    print(f"  {url}")
    print()
    print(f"Expires : {payload.expires_at.isoformat()}")
    print(f"Nonce   : {payload.nonce}")
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
