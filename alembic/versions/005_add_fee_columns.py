"""Add fee tracking columns to dca_orders and position_groups

Revision ID: 005_add_fee_columns
Revises: 004_add_hedge_tracking
Create Date: 2026-01-01

This migration adds:
- dca_orders.fee: Trading fee for the order
- dca_orders.fee_currency: Currency of the fee (e.g., USDT)
- position_groups.total_entry_fees_usd: Cumulative entry fees in USD
- position_groups.total_exit_fees_usd: Cumulative exit fees in USD
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '005_add_fee_columns'
down_revision: Union[str, None] = '004_add_hedge_tracking'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add fee columns to dca_orders
    op.add_column('dca_orders',
        sa.Column('fee', sa.Numeric(20, 10), nullable=True, server_default='0')
    )
    op.add_column('dca_orders',
        sa.Column('fee_currency', sa.String(10), nullable=True)
    )

    # Add fee totals to position_groups
    op.add_column('position_groups',
        sa.Column('total_entry_fees_usd', sa.Numeric(20, 10), nullable=True, server_default='0')
    )
    op.add_column('position_groups',
        sa.Column('total_exit_fees_usd', sa.Numeric(20, 10), nullable=True, server_default='0')
    )


def downgrade() -> None:
    # Remove fee columns from position_groups
    op.drop_column('position_groups', 'total_exit_fees_usd')
    op.drop_column('position_groups', 'total_entry_fees_usd')

    # Remove fee columns from dca_orders
    op.drop_column('dca_orders', 'fee_currency')
    op.drop_column('dca_orders', 'fee')
