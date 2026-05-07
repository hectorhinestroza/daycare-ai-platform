"""add processed_messages dedup table

Revision ID: 7376cf782334
Revises: 4306abf128cb
Create Date: 2026-05-07 08:08:27.052172

Twilio retries failed webhooks. Without dedup, a single voice memo can be
processed multiple times — duplicate events, duplicate audit logs, duplicate
OpenAI calls. This table is the dedup ledger: insert ON CONFLICT DO NOTHING
returns NULL on retries.

Rows are short-lived (~7 days, cleaned by a nightly scheduler job) since
Twilio's retry window is much shorter.
"""
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op


# revision identifiers, used by Alembic.
revision: str = '7376cf782334'
down_revision: Union[str, Sequence[str], None] = '4306abf128cb'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'processed_messages',
        sa.Column('message_sid', sa.Text(), nullable=False),
        sa.Column(
            'processed_at',
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text('NOW()'),
        ),
        sa.PrimaryKeyConstraint('message_sid'),
    )
    op.create_index(
        'idx_processed_messages_processed_at',
        'processed_messages',
        ['processed_at'],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('idx_processed_messages_processed_at', table_name='processed_messages')
    op.drop_table('processed_messages')
