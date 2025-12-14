"""add unique constraint for active position groups

Revision ID: unique_active_position_001
Revises: telegram_config_001
Create Date: 2025-12-14

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'unique_active_position_001'
down_revision = 'telegram_config_001'
branch_labels = None
depends_on = None


def upgrade():
    # Add partial unique index on active position groups
    # This prevents duplicate positions for the same (user, symbol, exchange, timeframe, side)
    # Only applies to non-closed/non-failed statuses
    op.execute("""
        CREATE UNIQUE INDEX uix_active_position_group
        ON position_groups (user_id, symbol, exchange, timeframe, side)
        WHERE status NOT IN ('closed', 'failed')
    """)


def downgrade():
    op.execute("DROP INDEX IF EXISTS uix_active_position_group")
