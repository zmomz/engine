"""Add quote_amount column to dca_orders for quote-based ordering

Revision ID: 006_add_quote_amount
Revises: 005_add_fee_columns
Create Date: 2026-01-03

This migration adds:
- dca_orders.quote_amount: USDT amount for quote-based market orders
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '006_add_quote_amount'
down_revision: Union[str, None] = '005_add_fee_columns'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add quote_amount column to dca_orders
    op.add_column('dca_orders',
        sa.Column('quote_amount', sa.Numeric(20, 10), nullable=True)
    )


def downgrade() -> None:
    # Remove quote_amount column from dca_orders
    op.drop_column('dca_orders', 'quote_amount')
