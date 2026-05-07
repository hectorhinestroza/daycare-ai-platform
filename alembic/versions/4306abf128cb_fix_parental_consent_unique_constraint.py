"""fix parental consent unique constraint

Revision ID: 4306abf128cb
Revises: c2f8d35a9e4b
Create Date: 2026-05-07 07:52:48.802124

The original UniqueConstraint("child_id", "is_active") allows only one row
per (child_id, is_active) combination. After one withdrawal-then-regrant
cycle a second withdrawal violates the constraint because two rows would
share (child_id, is_active=False).

Replace it with a partial unique index that only enforces uniqueness on
active consents. Withdrawn rows pile up freely as immutable history.

Idempotent: tolerates fresh DBs (no constraint to drop) and re-runs.
"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = '4306abf128cb'
down_revision: Union[str, Sequence[str], None] = 'c2f8d35a9e4b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute(
        "ALTER TABLE parental_consent "
        "DROP CONSTRAINT IF EXISTS unique_active_consent"
    )
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS unique_active_consent_per_child "
        "ON parental_consent (child_id) "
        "WHERE is_active = TRUE"
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.execute(
        "DROP INDEX IF EXISTS unique_active_consent_per_child"
    )
    # Re-add the original (broken) constraint so the schema matches the
    # previous revision exactly. Note: this will fail if more than one
    # withdrawn consent exists per child.
    op.execute(
        "ALTER TABLE parental_consent "
        "ADD CONSTRAINT unique_active_consent UNIQUE (child_id, is_active)"
    )
