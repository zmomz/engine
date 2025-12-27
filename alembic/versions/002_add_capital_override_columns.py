"""Add capital override columns to dca_configurations

Revision ID: 002_add_capital_override
Revises: 001_initial_schema
Create Date: 2025-12-27

This migration adds columns to support custom capital override per pyramid:
- use_custom_capital: Boolean toggle to enable/disable capital override
- custom_capital_usd: Default capital amount in USD (default: 200.0)
- pyramid_custom_capitals: JSON dict for per-pyramid capital overrides
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '002_add_capital_override'
down_revision: Union[str, None] = '001_initial_schema'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add capital override columns to dca_configurations
    op.add_column('dca_configurations',
        sa.Column('use_custom_capital', sa.Boolean(), nullable=False, server_default='false')
    )
    op.add_column('dca_configurations',
        sa.Column('custom_capital_usd', sa.Numeric(precision=18, scale=8), nullable=False, server_default='200.0')
    )
    op.add_column('dca_configurations',
        sa.Column('pyramid_custom_capitals', sa.JSON(), nullable=False, server_default='{}')
    )


def downgrade() -> None:
    op.drop_column('dca_configurations', 'pyramid_custom_capitals')
    op.drop_column('dca_configurations', 'custom_capital_usd')
    op.drop_column('dca_configurations', 'use_custom_capital')
