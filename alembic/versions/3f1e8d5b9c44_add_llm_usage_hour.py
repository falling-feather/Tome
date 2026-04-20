"""add_llm_usage_hour

Revision ID: 3f1e8d5b9c44
Revises: 2c9e1f4a7b22
Create Date: 2026-04-22 12:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '3f1e8d5b9c44'
down_revision: Union[str, None] = '2c9e1f4a7b22'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if 'llm_usage_hour' in inspector.get_table_names():
        return
    op.create_table(
        'llm_usage_hour',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('hour_bucket', sa.DateTime(), nullable=False),
        sa.Column('model', sa.String(length=128), nullable=False),
        sa.Column('requests', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('input_tokens', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('output_tokens', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('cost_usd', sa.Float(), nullable=True, server_default='0'),
    )
    op.create_index('ix_llm_usage_hour_hour_bucket', 'llm_usage_hour', ['hour_bucket'])
    op.create_index('ix_llm_usage_hour_model', 'llm_usage_hour', ['model'])
    op.create_index(
        'ix_llm_usage_hour_bucket_model',
        'llm_usage_hour',
        ['hour_bucket', 'model'],
        unique=True,
    )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if 'llm_usage_hour' not in inspector.get_table_names():
        return
    op.drop_index('ix_llm_usage_hour_bucket_model', table_name='llm_usage_hour')
    op.drop_index('ix_llm_usage_hour_model', table_name='llm_usage_hour')
    op.drop_index('ix_llm_usage_hour_hour_bucket', table_name='llm_usage_hour')
    op.drop_table('llm_usage_hour')
