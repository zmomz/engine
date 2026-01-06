"""Add closing_started_at to position_groups for stuck position recovery

Revision ID: 008_add_closing_started_at
Revises: 007_add_pyramid_closure_tracking
Create Date: 2026-01-06

This migration adds:
- position_groups.closing_started_at: When position entered CLOSING status
  This field does NOT have onupdate trigger, unlike updated_at.
  Used by recovery mechanism to detect stuck CLOSING positions.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '008_add_closing_started_at'
down_revision: Union[str, None] = '007_add_pyramid_closure_tracking'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add closing_started_at column to position_groups
    op.add_column('position_groups',
        sa.Column('closing_started_at', sa.DateTime(), nullable=True)
    )


def downgrade() -> None:
    op.drop_column('position_groups', 'closing_started_at')
