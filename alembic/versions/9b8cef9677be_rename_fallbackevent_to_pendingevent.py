"""Rename FallbackEvent to PendingEvent

Revision ID: 9b8cef9677be
Revises: 40d8d0f0767a
Create Date: 2026-04-23 19:55:51.412306

"""
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy.engine.reflection import Inspector

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '9b8cef9677be'
down_revision: Union[str, Sequence[str], None] = '40d8d0f0767a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = Inspector.from_engine(conn)
    tables = inspector.get_table_names()

    if 'fallback_events' in tables:
        op.drop_table('fallback_events')

    if 'pending_events' not in tables:
        op.create_table('pending_events',
        sa.Column('id', sa.UUID(), autoincrement=False, nullable=False),
        sa.Column('center_id', sa.UUID(), autoincrement=False, nullable=False),
        sa.Column('teacher_phone', sa.VARCHAR(length=30), autoincrement=False, nullable=False),
        sa.Column('unrecognized_name', sa.VARCHAR(length=255), autoincrement=False, nullable=False),
        sa.Column('original_transcript', sa.TEXT(), autoincrement=False, nullable=False),
        sa.Column('pending_event_data', postgresql.JSONB(astext_type=sa.Text()), autoincrement=False, nullable=False),
        sa.Column('created_at', postgresql.TIMESTAMP(timezone=True), autoincrement=False, nullable=True),
        sa.ForeignKeyConstraint(['center_id'], ['centers.id'], name=op.f('pending_events_center_id_fkey')),
        sa.PrimaryKeyConstraint('id', name=op.f('pending_events_pkey'))
        )


def downgrade() -> None:
    conn = op.get_bind()
    inspector = Inspector.from_engine(conn)
    tables = inspector.get_table_names()

    if 'pending_events' in tables:
        op.drop_table('pending_events')

    if 'fallback_events' not in tables:
        op.create_table('fallback_events',
        sa.Column('id', sa.UUID(), autoincrement=False, nullable=False),
        sa.Column('center_id', sa.UUID(), autoincrement=False, nullable=False),
        sa.Column('teacher_phone', sa.VARCHAR(length=30), autoincrement=False, nullable=False),
        sa.Column('unrecognized_name', sa.VARCHAR(length=255), autoincrement=False, nullable=False),
        sa.Column('original_transcript', sa.TEXT(), autoincrement=False, nullable=False),
        sa.Column('pending_event_data', postgresql.JSONB(astext_type=sa.Text()), autoincrement=False, nullable=False),
        sa.Column('created_at', postgresql.TIMESTAMP(timezone=True), autoincrement=False, nullable=True),
        sa.ForeignKeyConstraint(['center_id'], ['centers.id'], name=op.f('fallback_events_center_id_fkey')),
        sa.PrimaryKeyConstraint('id', name=op.f('fallback_events_pkey'))
        )
