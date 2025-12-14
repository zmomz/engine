"""remove replacement_count from position_groups

Revision ID: remove_replacement_count_001
Revises: unique_active_position_001
Create Date: 2025-12-14

This migration removes the unused replacement_count column from position_groups.
The replacement_count is tracked on QueuedSignal instead, which is the correct
location for tracking how many times a queued signal was replaced.

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'remove_replacement_count_001'
down_revision = 'unique_active_position_001'
branch_labels = None
depends_on = None


def upgrade():
    # Drop the unused replacement_count column
    op.drop_column('position_groups', 'replacement_count')


def downgrade():
    # Re-add the column if rolling back
    op.add_column(
        'position_groups',
        sa.Column('replacement_count', sa.Integer(), nullable=True, server_default='0')
    )
