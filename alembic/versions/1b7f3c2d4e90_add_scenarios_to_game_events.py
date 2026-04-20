"""add_scenarios_to_game_events

Revision ID: 1b7f3c2d4e90
Revises: 8e7187bad9d7
Create Date: 2026-04-18 23:40:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '1b7f3c2d4e90'
down_revision: Union[str, None] = '8e7187bad9d7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {col['name'] for col in inspector.get_columns('game_events')}
    if 'scenarios' not in columns:
        op.add_column('game_events', sa.Column('scenarios', sa.JSON(), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {col['name'] for col in inspector.get_columns('game_events')}
    if 'scenarios' in columns:
        op.drop_column('game_events', 'scenarios')
