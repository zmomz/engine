"""add_performance_indexes

Revision ID: a1b2c3d4e5f6
Revises: remove_replacement_count_from_position_groups
Create Date: 2025-12-14

Performance optimization indexes for:
- position_groups: user_id, status, exchange queries
- dca_orders: group_id, status, user lookups via group
- queued_signals: user_id, status queries
"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'add_performance_indexes_001'
down_revision: Union[str, None] = 'remove_replacement_count_001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Position Groups indexes
    # Index for fetching active positions by user (common query in risk engine and dashboard)
    op.create_index(
        'ix_position_groups_user_status',
        'position_groups',
        ['user_id', 'status'],
        unique=False
    )

    # Index for fetching positions by exchange (used in order fill monitor)
    op.create_index(
        'ix_position_groups_exchange',
        'position_groups',
        ['exchange'],
        unique=False
    )

    # Index for risk timer expiry checks
    op.create_index(
        'ix_position_groups_risk_timer',
        'position_groups',
        ['risk_timer_expires'],
        unique=False,
        postgresql_where="risk_timer_expires IS NOT NULL"
    )

    # DCA Orders indexes
    # Index for fetching open orders by group (common in order fill monitor)
    op.create_index(
        'ix_dca_orders_group_status',
        'dca_orders',
        ['group_id', 'status'],
        unique=False
    )

    # Index for fetching orders by exchange_order_id (exchange lookups)
    op.create_index(
        'ix_dca_orders_exchange_order_id',
        'dca_orders',
        ['exchange_order_id'],
        unique=False,
        postgresql_where="exchange_order_id IS NOT NULL"
    )

    # Index for TP order tracking
    op.create_index(
        'ix_dca_orders_tp_order_id',
        'dca_orders',
        ['tp_order_id'],
        unique=False,
        postgresql_where="tp_order_id IS NOT NULL"
    )

    # Queued Signals indexes
    op.create_index(
        'ix_queued_signals_user_status',
        'queued_signals',
        ['user_id', 'status'],
        unique=False
    )

    op.create_index(
        'ix_queued_signals_priority_score',
        'queued_signals',
        ['priority_score'],
        unique=False
    )


def downgrade() -> None:
    # Drop queued signals indexes
    op.drop_index('ix_queued_signals_priority_score', table_name='queued_signals')
    op.drop_index('ix_queued_signals_user_status', table_name='queued_signals')

    # Drop DCA Orders indexes
    op.drop_index('ix_dca_orders_tp_order_id', table_name='dca_orders')
    op.drop_index('ix_dca_orders_exchange_order_id', table_name='dca_orders')
    op.drop_index('ix_dca_orders_group_status', table_name='dca_orders')

    # Drop Position Groups indexes
    op.drop_index('ix_position_groups_risk_timer', table_name='position_groups')
    op.drop_index('ix_position_groups_exchange', table_name='position_groups')
    op.drop_index('ix_position_groups_user_status', table_name='position_groups')
