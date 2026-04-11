#!/bin/bash
set -e

echo "=== Daycare AI Platform — Starting ==="

# If alembic_version table doesn't exist, the DB was bootstrapped via
# create_all() without Alembic. Stamp it at the baseline revision so
# only new migrations run.
python - <<'EOF'
from backend.storage.database import engine
from sqlalchemy import text, inspect

inspector = inspect(engine)
if 'alembic_version' not in inspector.get_table_names():
    print("No alembic_version table found — stamping baseline...")
    with engine.connect() as conn:
        conn.execute(text("CREATE TABLE IF NOT EXISTS alembic_version (version_num VARCHAR(32) NOT NULL, CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num))"))
        conn.execute(text("INSERT INTO alembic_version (version_num) VALUES ('285a346288d3') ON CONFLICT DO NOTHING"))
        conn.commit()
    print("Stamped at baseline revision 285a346288d3")
else:
    print("alembic_version table exists — skipping stamp")
EOF

echo "Running database migrations..."
alembic upgrade head

echo "Starting server on port ${PORT:-8080}..."
exec uvicorn backend.main:app --host 0.0.0.0 --port "${PORT:-8080}"
