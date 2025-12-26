"""add_close_action_fields_to_risk_actions

Revision ID: add_close_action_fields_001
Revises: add_performance_indexes_001
Create Date: 2025-12-18

Adds new columns to risk_actions table to track close action details:
- exit_price, entry_price, pnl_percent, realized_pnl_usd
- quantity_closed, duration_seconds
- New action types: MANUAL_CLOSE, ENGINE_CLOSE, TP_HIT
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'add_close_action_fields_001'
down_revision: Union[str, None] = 'add_performance_indexes_001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add new columns for close action tracking
    op.add_column('risk_actions', sa.Column('exit_price', sa.Numeric(20, 10), nullable=True))
    op.add_column('risk_actions', sa.Column('entry_price', sa.Numeric(20, 10), nullable=True))
    op.add_column('risk_actions', sa.Column('pnl_percent', sa.Numeric(10, 4), nullable=True))
    op.add_column('risk_actions', sa.Column('realized_pnl_usd', sa.Numeric(20, 10), nullable=True))
    op.add_column('risk_actions', sa.Column('quantity_closed', sa.Numeric(20, 10), nullable=True))
    op.add_column('risk_actions', sa.Column('duration_seconds', sa.Numeric(20, 2), nullable=True))

    # Add index for querying close actions by type
    op.create_index(
        'ix_risk_actions_action_type',
        'risk_actions',
        ['action_type'],
        unique=False
    )

    # Add index for querying by group_id and timestamp (for history)
    op.create_index(
        'ix_risk_actions_group_timestamp',
        'risk_actions',
        ['group_id', 'timestamp'],
        unique=False
    )


def downgrade() -> None:
    # Drop indexes
    op.drop_index('ix_risk_actions_group_timestamp', table_name='risk_actions')
    op.drop_index('ix_risk_actions_action_type', table_name='risk_actions')

    # Drop columns
    op.drop_column('risk_actions', 'duration_seconds')
    op.drop_column('risk_actions', 'quantity_closed')
    op.drop_column('risk_actions', 'realized_pnl_usd')
    op.drop_column('risk_actions', 'pnl_percent')
    op.drop_column('risk_actions', 'entry_price')
    op.drop_column('risk_actions', 'exit_price')
