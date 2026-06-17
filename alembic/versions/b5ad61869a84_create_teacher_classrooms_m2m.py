"""create_teacher_classrooms_m2m

Revision ID: b5ad61869a84
Revises: dc6f1749d968
Create Date: 2026-06-17 09:05:12.142487

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b5ad61869a84'
down_revision: Union[str, Sequence[str], None] = 'dc6f1749d968'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create teacher_classrooms table
    op.create_table(
        'teacher_classrooms',
        sa.Column('teacher_id', sa.UUID(), nullable=False),
        sa.Column('room_id', sa.UUID(), nullable=False),
        sa.Column('center_id', sa.UUID(), nullable=False),
        sa.Column('is_primary', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['center_id'], ['centers.id'], ),
        sa.ForeignKeyConstraint(['room_id'], ['rooms.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['teacher_id'], ['teachers.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('teacher_id', 'room_id')
    )

    # 2. Backfill data from teachers.room_id
    connection = op.get_bind()
    teachers_table = sa.table(
        'teachers',
        sa.column('id', sa.UUID()),
        sa.column('center_id', sa.UUID()),
        sa.column('room_id', sa.UUID())
    )
    
    results = connection.execute(
        sa.select(
            teachers_table.c.id,
            teachers_table.c.center_id,
            teachers_table.c.room_id
        ).where(teachers_table.c.room_id.is_not(None))
    ).fetchall()

    teacher_classrooms_table = sa.table(
        'teacher_classrooms',
        sa.column('teacher_id', sa.UUID()),
        sa.column('room_id', sa.UUID()),
        sa.column('center_id', sa.UUID()),
        sa.column('is_primary', sa.Boolean()),
        sa.column('created_at', sa.DateTime())
    )

    import datetime
    for row in results:
        teacher_id, center_id, room_id = row[0], row[1], row[2]
        connection.execute(
            teacher_classrooms_table.insert().values(
                teacher_id=teacher_id,
                room_id=room_id,
                center_id=center_id,
                is_primary=True,
                created_at=datetime.datetime.now(datetime.timezone.utc)
            )
        )

    # 3. Drop constraint and room_id column using batch mode
    with op.batch_alter_table('teachers', schema=None) as batch_op:
        batch_op.drop_column('room_id')


def downgrade() -> None:
    # 1. Add room_id column back to teachers
    with op.batch_alter_table('teachers', schema=None) as batch_op:
        batch_op.add_column(sa.Column('room_id', sa.UUID(), nullable=True))
        batch_op.create_foreign_key('fk_teachers_room_id', 'rooms', ['room_id'], ['id'])

    # 2. Backfill from teacher_classrooms back to teachers where is_primary = True
    connection = op.get_bind()
    teacher_classrooms_table = sa.table(
        'teacher_classrooms',
        sa.column('teacher_id', sa.UUID()),
        sa.column('room_id', sa.UUID()),
        sa.column('is_primary', sa.Boolean())
    )
    results = connection.execute(
        sa.select(
            teacher_classrooms_table.c.teacher_id,
            teacher_classrooms_table.c.room_id
        ).where(teacher_classrooms_table.c.is_primary == True)
    ).fetchall()

    teachers_table = sa.table(
        'teachers',
        sa.column('id', sa.UUID()),
        sa.column('room_id', sa.UUID())
    )

    for row in results:
        teacher_id, room_id = row[0], row[1]
        connection.execute(
            teachers_table.update()
            .where(teachers_table.c.id == teacher_id)
            .values(room_id=room_id)
        )

    # 3. Drop teacher_classrooms table
    op.drop_table('teacher_classrooms')
