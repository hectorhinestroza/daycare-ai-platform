"""baseline — existing schema created via create_all()

Revision ID: 285a346288d3
Revises:
Create Date: 2026-04-11

This is a no-op baseline migration. The schema was originally bootstrapped
via SQLAlchemy create_all() before Alembic was set up. This revision
represents that state so subsequent migrations can build on top of it.
"""

revision = "285a346288d3"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass  # Schema already exists via create_all()


def downgrade() -> None:
    pass
