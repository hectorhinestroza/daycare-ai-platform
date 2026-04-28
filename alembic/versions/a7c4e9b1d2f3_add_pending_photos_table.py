"""add_pending_photos_table

Revision ID: a7c4e9b1d2f3
Revises: 9b8cef9677be
Create Date: 2026-04-28 10:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy.engine.reflection import Inspector

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'a7c4e9b1d2f3'
down_revision: Union[str, Sequence[str], None] = '9b8cef9677be'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    inspector = Inspector.from_engine(conn)
    tables = inspector.get_table_names()

    if 'pending_photos' not in tables:
        op.create_table(
            'pending_photos',
            sa.Column('id', sa.UUID(), nullable=False),
            sa.Column('center_id', sa.UUID(), nullable=False),
            sa.Column('teacher_id', sa.UUID(), nullable=False),
            sa.Column('s3_temp_key', sa.String(length=500), nullable=False),
            sa.Column('caption', sa.Text(), nullable=True),
            sa.Column('content_type', sa.String(length=50), nullable=True),
            sa.Column('created_at', postgresql.TIMESTAMP(timezone=True), nullable=True),
            sa.Column('expires_at', postgresql.TIMESTAMP(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(['center_id'], ['centers.id'], name=op.f('pending_photos_center_id_fkey')),
            sa.ForeignKeyConstraint(['teacher_id'], ['teachers.id'], name=op.f('pending_photos_teacher_id_fkey')),
            sa.PrimaryKeyConstraint('id', name=op.f('pending_photos_pkey')),
        )
        existing_indexes: set[str] = set()
    else:
        existing_indexes = {ix['name'] for ix in inspector.get_indexes('pending_photos')}

    if 'ix_pending_photos_teacher_id' not in existing_indexes:
        op.create_index('ix_pending_photos_teacher_id', 'pending_photos', ['teacher_id'])

    if 'ix_pending_photos_expires_at' not in existing_indexes:
        op.create_index('ix_pending_photos_expires_at', 'pending_photos', ['expires_at'])


def downgrade() -> None:
    conn = op.get_bind()
    inspector = Inspector.from_engine(conn)
    tables = inspector.get_table_names()

    if 'pending_photos' in tables:
        existing_indexes = {ix['name'] for ix in inspector.get_indexes('pending_photos')}
        if 'ix_pending_photos_expires_at' in existing_indexes:
            op.drop_index('ix_pending_photos_expires_at', table_name='pending_photos')
        if 'ix_pending_photos_teacher_id' in existing_indexes:
            op.drop_index('ix_pending_photos_teacher_id', table_name='pending_photos')
        op.drop_table('pending_photos')
