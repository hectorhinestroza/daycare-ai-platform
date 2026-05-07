"""add revoked_token_nonces table

Revision ID: dc6f1749d968
Revises: 7376cf782334
Create Date: 2026-05-07 09:22:33.619488

Per-subject token revocation list. Each row marks one nonce of one
subject (parent_contact_id, teacher_id, or admin_id) as invalid.

When a director "revokes a parent's bookmark URL," we insert
(parent_contact_id, current_nonce) here. The next time that token is
verified the lookup hits a row and the gate rejects it.

Composite primary key keeps lookups O(1) and prevents duplicate rows.
"""
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'dc6f1749d968'
down_revision: Union[str, Sequence[str], None] = '7376cf782334'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'revoked_token_nonces',
        sa.Column('sub_id', sa.Text(), nullable=False),
        sa.Column('nonce', sa.Text(), nullable=False),
        sa.Column(
            'revoked_at',
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text('CURRENT_TIMESTAMP'),
        ),
        sa.PrimaryKeyConstraint('sub_id', 'nonce'),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('revoked_token_nonces')
