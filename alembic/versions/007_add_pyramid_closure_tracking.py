"""Add pyramid closure tracking fields for pyramid_aggregate TP

Revision ID: 007_add_pyramid_closure_tracking
Revises: 006_add_quote_amount
Create Date: 2026-01-04

This migration adds:
- pyramids.closed_at: When pyramid TP was hit
- pyramids.exit_price: Price at which pyramid was sold
- pyramids.realized_pnl_usd: PnL from this pyramid
- pyramids.total_quantity: Total qty that was in this pyramid
- Adds 'closed' value to pyramid_status_enum
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '007_add_pyramid_closure_tracking'
down_revision: Union[str, None] = '006_add_quote_amount'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add 'closed' value to pyramid_status_enum
    # PostgreSQL requires special handling for adding enum values
    op.execute("ALTER TYPE pyramid_status_enum ADD VALUE IF NOT EXISTS 'closed'")

    # Add closure tracking columns to pyramids
    op.add_column('pyramids',
        sa.Column('closed_at', sa.DateTime(), nullable=True)
    )
    op.add_column('pyramids',
        sa.Column('exit_price', sa.Numeric(20, 10), nullable=True)
    )
    op.add_column('pyramids',
        sa.Column('realized_pnl_usd', sa.Numeric(20, 10), nullable=True)
    )
    op.add_column('pyramids',
        sa.Column('total_quantity', sa.Numeric(20, 10), nullable=True)
    )


def downgrade() -> None:
    # Remove closure tracking columns from pyramids
    op.drop_column('pyramids', 'total_quantity')
    op.drop_column('pyramids', 'realized_pnl_usd')
    op.drop_column('pyramids', 'exit_price')
    op.drop_column('pyramids', 'closed_at')

    # Note: PostgreSQL does not support removing enum values easily
    # The 'closed' value will remain in the enum but won't be used
