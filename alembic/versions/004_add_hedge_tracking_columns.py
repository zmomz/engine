"""Add hedge tracking columns to position_groups

Revision ID: 004_add_hedge_tracking
Revises: 003_add_rejection_reason
Create Date: 2025-12-28

This migration adds:
- total_hedged_qty: Cumulative quantity closed to offset losers
- total_hedged_value_usd: Cumulative USD value of hedge closes
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '004_add_hedge_tracking'
down_revision: Union[str, None] = '003_add_rejection_reason'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add hedge tracking columns to position_groups
    op.add_column('position_groups',
        sa.Column('total_hedged_qty', sa.Numeric(20, 10), nullable=True, server_default='0')
    )
    op.add_column('position_groups',
        sa.Column('total_hedged_value_usd', sa.Numeric(20, 10), nullable=True, server_default='0')
    )


def downgrade() -> None:
    # Remove hedge tracking columns
    op.drop_column('position_groups', 'total_hedged_value_usd')
    op.drop_column('position_groups', 'total_hedged_qty')
