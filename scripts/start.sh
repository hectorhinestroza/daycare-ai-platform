#!/bin/bash
set -e

echo "=== Daycare AI Platform — Starting ==="

# Bootstrap branch:
#   - Empty DB (no alembic_version AND no tables): create the current ORM
#     schema, create the Postgres-only consent view, then stamp at HEAD so
#     no migrations try to alter freshly-created tables.
#   - Schema-only DB (no alembic_version but tables exist): the schema was
#     built via create_all() from the current ORM, so it already matches
#     HEAD. Stamp at HEAD — not baseline — so we don't replay migrations
#     that try to ADD columns/tables create_all() already produced.
#     (Stamping at baseline was the prior bug: every alter-table migration
#     blew up on "column already exists" on the next deploy.)
#   - Already migrated: skip stamping; `alembic upgrade head` applies new
#     migrations or no-ops.
python - <<'EOF'
from backend.storage.database import Base, engine
# Importing models registers every ORM class onto Base.metadata. Without
# this side-effect import, create_all() sees an empty metadata and creates
# nothing — which is how a prior boot crashed on "relation 'children'
# does not exist" when creating the consent view.
import backend.storage.models  # noqa: F401
from sqlalchemy import inspect, text

from alembic import command
from alembic.config import Config

# The consent view is Postgres-specific and lives outside the ORM. The
# alembic migration c2f8d35a9e4b creates it; on a fresh DB we stamp past
# that migration, so we must materialize the view ourselves here.
CONSENT_VIEW_SQL = """
CREATE OR REPLACE VIEW children_with_active_consent AS
SELECT c.*
FROM children c
JOIN parental_consent pc
  ON pc.child_id = c.id
 AND pc.center_id = c.center_id
WHERE pc.is_active = TRUE
  AND pc.withdrawn_at IS NULL
  AND pc.consent_daily_reports = TRUE
  AND pc.consent_photos = TRUE
  AND pc.consent_audio_processing = TRUE
  AND pc.consent_billing_data = TRUE
"""

inspector = inspect(engine)
tables = set(inspector.get_table_names())
cfg = Config("alembic.ini")

if "alembic_version" not in tables:
    if not tables:
        print("Fresh DB detected — creating tables via Base.metadata.create_all()...")
        Base.metadata.create_all(bind=engine)
        # Only attempt the view on Postgres. SQLite tests don't reach this
        # script anyway, but be safe.
        if engine.dialect.name == "postgresql":
            print("Creating children_with_active_consent view...")
            with engine.begin() as conn:
                conn.execute(text(CONSENT_VIEW_SQL))
        print("Stamping alembic_version at HEAD (no migrations to replay)...")
        command.stamp(cfg, "head")
    else:
        print(f"Found {len(tables)} tables but no alembic_version — stamping at HEAD (schema was built via create_all)...")
        # Also create the consent view if it's missing — the migration that
        # creates it won't run because we're about to stamp past it.
        if engine.dialect.name == "postgresql":
            existing_views = {r[0] for r in engine.connect().execute(
                text("SELECT table_name FROM information_schema.views WHERE table_schema = current_schema()")
            ).fetchall()}
            if "children_with_active_consent" not in existing_views:
                print("Creating missing children_with_active_consent view...")
                with engine.begin() as conn:
                    conn.execute(text(CONSENT_VIEW_SQL))
        command.stamp(cfg, "head")
else:
    print("alembic_version table exists — skipping stamp")
EOF

echo "Running database migrations..."
alembic upgrade head

echo "Starting server on port ${PORT:-8080}..."
exec uvicorn backend.main:app --host 0.0.0.0 --port "${PORT:-8080}"
