"""add children_with_active_consent view

Revision ID: c2f8d35a9e4b
Revises: a7c4e9b1d2f3
Create Date: 2026-04-28 11:00:00.000000

The consent gate (backend/utils/consent_gate.py) queries this view as the
single source of truth for "which children may enter the AI pipeline."
A child appears here only if there's an active, non-withdrawn parental
consent row with all four required scopes granted.

Postgres-only: SQLite test environments use Base.metadata.create_all()
and never run this migration, so the view is not created there. The
consent gate has a dev/test bypass that hits the children table directly.
"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'c2f8d35a9e4b'
down_revision: Union[str, Sequence[str], None] = 'a7c4e9b1d2f3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


VIEW_SQL = """
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


def upgrade() -> None:
    # CREATE OR REPLACE is idempotent — safe to re-run.
    op.execute(VIEW_SQL)


def downgrade() -> None:
    op.execute("DROP VIEW IF EXISTS children_with_active_consent")
