"""Add rejection_reason column and REJECTED status to queued_signals

Revision ID: 003_add_rejection_reason
Revises: 002_add_capital_override
Create Date: 2025-12-28

This migration adds:
- rejection_reason: Column to store why a signal was rejected by risk validation
- Updates queue_status_enum to include 'rejected' status
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '003_add_rejection_reason'
down_revision: Union[str, None] = '002_add_capital_override'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add rejection_reason column to queued_signals
    op.add_column('queued_signals',
        sa.Column('rejection_reason', sa.String(), nullable=True)
    )

    # Add 'rejected' value to queue_status_enum
    # PostgreSQL requires ALTER TYPE to add a new value
    op.execute("ALTER TYPE queue_status_enum ADD VALUE IF NOT EXISTS 'rejected'")


def downgrade() -> None:
    # Remove rejection_reason column
    op.drop_column('queued_signals', 'rejection_reason')

    # Note: PostgreSQL doesn't support removing enum values easily
    # The 'rejected' value will remain in the enum but won't be used
