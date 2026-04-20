"""add_embedding_to_world_entries

Revision ID: 2c9e1f4a7b22
Revises: 1b7f3c2d4e90
Create Date: 2026-04-19 12:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '2c9e1f4a7b22'
down_revision: Union[str, None] = '1b7f3c2d4e90'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {col['name'] for col in inspector.get_columns('world_entries')}
    if 'embedding' not in columns:
        op.add_column('world_entries', sa.Column('embedding', sa.Text(), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {col['name'] for col in inspector.get_columns('world_entries')}
    if 'embedding' in columns:
        op.drop_column('world_entries', 'embedding')
