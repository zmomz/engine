"""Initial consolidated schema

Revision ID: 001_initial_schema
Revises:
Create Date: 2025-12-26

This migration creates the complete database schema from scratch.
It consolidates all previous migrations into a single initial migration.

Tables:
- users
- dca_configurations
- position_groups
- queued_signals
- pyramids
- risk_actions
- dca_orders
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from app.db.types import GUID


# revision identifiers, used by Alembic.
revision: str = '001_initial_schema'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ===========================================
    # ENUM TYPES
    # ===========================================

    # Create all enum types first
    position_side_enum = postgresql.ENUM('long', 'short', name='position_side_enum', create_type=False)
    signal_side_enum = postgresql.ENUM('long', 'short', name='signal_side_enum', create_type=False)
    order_side_enum = postgresql.ENUM('buy', 'sell', name='order_side_enum', create_type=False)

    group_status_enum = postgresql.ENUM(
        'waiting', 'live', 'partially_filled', 'active', 'closing', 'closed', 'failed',
        name='group_status_enum', create_type=False
    )

    queue_status_enum = postgresql.ENUM('queued', 'promoted', 'cancelled', name='queue_status_enum', create_type=False)

    pyramid_status_enum = postgresql.ENUM('pending', 'submitted', 'filled', 'cancelled', name='pyramid_status_enum', create_type=False)

    order_status_enum = postgresql.ENUM(
        'pending', 'trigger_pending', 'open', 'partially_filled', 'filled', 'cancelled', 'failed',
        name='order_status_enum', create_type=False
    )

    order_type_enum = postgresql.ENUM('limit', 'market', name='order_type_enum', create_type=False)

    entry_order_type_enum = postgresql.ENUM('limit', 'market', name='entry_order_type_enum', create_type=False)

    tp_mode_enum = postgresql.ENUM('per_leg', 'aggregate', 'hybrid', name='tp_mode_enum', create_type=False)

    take_profit_mode_enum = postgresql.ENUM(
        'per_leg', 'aggregate', 'hybrid', 'pyramid_aggregate',
        name='take_profit_mode_enum', create_type=False
    )

    risk_action_type_enum = postgresql.ENUM(
        'offset_loss', 'manual_block', 'manual_skip', 'manual_close', 'engine_close', 'tp_hit',
        name='riskactiontype', create_type=False
    )

    # Create enum types in database (using DO block for IF NOT EXISTS support)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE position_side_enum AS ENUM ('long', 'short');
        EXCEPTION WHEN duplicate_object THEN NULL; END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE signal_side_enum AS ENUM ('long', 'short');
        EXCEPTION WHEN duplicate_object THEN NULL; END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE order_side_enum AS ENUM ('buy', 'sell');
        EXCEPTION WHEN duplicate_object THEN NULL; END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE group_status_enum AS ENUM ('waiting', 'live', 'partially_filled', 'active', 'closing', 'closed', 'failed');
        EXCEPTION WHEN duplicate_object THEN NULL; END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE queue_status_enum AS ENUM ('queued', 'promoted', 'cancelled');
        EXCEPTION WHEN duplicate_object THEN NULL; END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE pyramid_status_enum AS ENUM ('pending', 'submitted', 'filled', 'cancelled');
        EXCEPTION WHEN duplicate_object THEN NULL; END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE order_status_enum AS ENUM ('pending', 'trigger_pending', 'open', 'partially_filled', 'filled', 'cancelled', 'failed');
        EXCEPTION WHEN duplicate_object THEN NULL; END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE order_type_enum AS ENUM ('limit', 'market');
        EXCEPTION WHEN duplicate_object THEN NULL; END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE entry_order_type_enum AS ENUM ('limit', 'market');
        EXCEPTION WHEN duplicate_object THEN NULL; END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE tp_mode_enum AS ENUM ('per_leg', 'aggregate', 'hybrid');
        EXCEPTION WHEN duplicate_object THEN NULL; END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE take_profit_mode_enum AS ENUM ('per_leg', 'aggregate', 'hybrid', 'pyramid_aggregate');
        EXCEPTION WHEN duplicate_object THEN NULL; END $$;
    """)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE riskactiontype AS ENUM ('offset_loss', 'manual_block', 'manual_skip', 'manual_close', 'engine_close', 'tp_hit');
        EXCEPTION WHEN duplicate_object THEN NULL; END $$;
    """)

    # ===========================================
    # TABLE: users
    # ===========================================
    op.create_table('users',
        sa.Column('id', GUID(), nullable=False),
        sa.Column('username', sa.String(), nullable=False),
        sa.Column('email', sa.String(), nullable=False),
        sa.Column('hashed_password', sa.String(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=True, default=True),
        sa.Column('is_superuser', sa.Boolean(), nullable=True, default=False),
        sa.Column('exchange', sa.String(), nullable=False, server_default='binance'),
        sa.Column('webhook_secret', sa.String(), nullable=False),
        sa.Column('encrypted_api_keys', sa.JSON(), nullable=True),
        sa.Column('risk_config', sa.JSON(), nullable=False),
        sa.Column('telegram_config', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_users_email', 'users', ['email'], unique=True)
    op.create_index('ix_users_username', 'users', ['username'], unique=True)

    # ===========================================
    # TABLE: dca_configurations
    # ===========================================
    op.create_table('dca_configurations',
        sa.Column('id', GUID(), nullable=False),
        sa.Column('user_id', GUID(), nullable=False),
        sa.Column('pair', sa.String(), nullable=False),
        sa.Column('timeframe', sa.Integer(), nullable=False),
        sa.Column('exchange', sa.String(), nullable=False),
        sa.Column('entry_order_type', sa.Enum('limit', 'market', name='entry_order_type_enum', create_type=False), nullable=False),
        sa.Column('dca_levels', sa.JSON(), nullable=False),
        sa.Column('pyramid_specific_levels', sa.JSON(), nullable=False),
        sa.Column('tp_mode', sa.Enum('per_leg', 'aggregate', 'hybrid', 'pyramid_aggregate', name='take_profit_mode_enum', create_type=False), nullable=False),
        sa.Column('tp_settings', sa.JSON(), nullable=False),
        sa.Column('max_pyramids', sa.Integer(), nullable=False, server_default='5'),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'pair', 'timeframe', 'exchange', name='uix_user_pair_timeframe_exchange')
    )

    # ===========================================
    # TABLE: position_groups
    # ===========================================
    op.create_table('position_groups',
        sa.Column('id', GUID(), nullable=False),
        sa.Column('user_id', GUID(), nullable=False),
        sa.Column('exchange', sa.String(), nullable=False),
        sa.Column('symbol', sa.String(), nullable=False),
        sa.Column('timeframe', sa.Integer(), nullable=False),
        sa.Column('side', sa.Enum('long', 'short', name='position_side_enum', create_type=False), nullable=False),
        sa.Column('status', sa.Enum('waiting', 'live', 'partially_filled', 'active', 'closing', 'closed', 'failed', name='group_status_enum', create_type=False), nullable=False),
        sa.Column('pyramid_count', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('max_pyramids', sa.Integer(), nullable=True, server_default='5'),
        sa.Column('total_dca_legs', sa.Integer(), nullable=False),
        sa.Column('filled_dca_legs', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('base_entry_price', sa.Numeric(precision=20, scale=10), nullable=False),
        sa.Column('weighted_avg_entry', sa.Numeric(precision=20, scale=10), nullable=False),
        sa.Column('total_invested_usd', sa.Numeric(precision=20, scale=10), nullable=True, server_default='0'),
        sa.Column('total_filled_quantity', sa.Numeric(precision=20, scale=10), nullable=True, server_default='0'),
        sa.Column('unrealized_pnl_usd', sa.Numeric(precision=20, scale=10), nullable=True, server_default='0'),
        sa.Column('unrealized_pnl_percent', sa.Numeric(precision=10, scale=4), nullable=True, server_default='0'),
        sa.Column('realized_pnl_usd', sa.Numeric(precision=20, scale=10), nullable=True, server_default='0'),
        sa.Column('tp_mode', sa.Enum('per_leg', 'aggregate', 'hybrid', name='tp_mode_enum', create_type=False), nullable=False),
        sa.Column('tp_aggregate_percent', sa.Numeric(precision=10, scale=4), nullable=True),
        sa.Column('risk_timer_start', sa.DateTime(), nullable=True),
        sa.Column('risk_timer_expires', sa.DateTime(), nullable=True),
        sa.Column('risk_eligible', sa.Boolean(), nullable=True, server_default='false'),
        sa.Column('risk_blocked', sa.Boolean(), nullable=True, server_default='false'),
        sa.Column('risk_skip_once', sa.Boolean(), nullable=True, server_default='false'),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('closed_at', sa.DateTime(), nullable=True),
        sa.Column('telegram_message_id', sa.BigInteger(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id')
    )

    # Partial unique index for active positions
    op.execute("""
        CREATE UNIQUE INDEX uix_active_position_group
        ON position_groups (user_id, symbol, exchange, timeframe, side)
        WHERE status NOT IN ('closed', 'failed')
    """)

    # Performance indexes
    op.create_index('ix_position_groups_user_status', 'position_groups', ['user_id', 'status'])
    op.create_index('ix_position_groups_exchange', 'position_groups', ['exchange'])
    op.execute("""
        CREATE INDEX ix_position_groups_risk_timer
        ON position_groups (risk_timer_expires)
        WHERE risk_timer_expires IS NOT NULL
    """)

    # ===========================================
    # TABLE: queued_signals
    # ===========================================
    op.create_table('queued_signals',
        sa.Column('id', GUID(), nullable=False),
        sa.Column('user_id', GUID(), nullable=False),
        sa.Column('exchange', sa.String(), nullable=False),
        sa.Column('symbol', sa.String(), nullable=False),
        sa.Column('timeframe', sa.Integer(), nullable=False),
        sa.Column('side', sa.Enum('long', 'short', name='signal_side_enum', create_type=False), nullable=False),
        sa.Column('entry_price', sa.Numeric(precision=20, scale=10), nullable=False),
        sa.Column('signal_payload', sa.JSON(), nullable=False),
        sa.Column('queued_at', sa.DateTime(), nullable=True),
        sa.Column('replacement_count', sa.Integer(), nullable=True, server_default='0'),
        sa.Column('priority_score', sa.Numeric(precision=20, scale=4), nullable=True, server_default='0'),
        sa.Column('priority_explanation', sa.String(), nullable=True),
        sa.Column('is_pyramid_continuation', sa.Boolean(), nullable=True, server_default='false'),
        sa.Column('current_loss_percent', sa.Numeric(precision=10, scale=4), nullable=True),
        sa.Column('status', sa.Enum('queued', 'promoted', 'cancelled', name='queue_status_enum', create_type=False), nullable=False),
        sa.Column('promoted_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id')
    )

    # Performance indexes
    op.create_index('ix_queued_signals_user_status', 'queued_signals', ['user_id', 'status'])
    op.create_index('ix_queued_signals_priority_score', 'queued_signals', ['priority_score'])

    # ===========================================
    # TABLE: pyramids
    # ===========================================
    op.create_table('pyramids',
        sa.Column('id', GUID(), nullable=False),
        sa.Column('group_id', GUID(), nullable=False),
        sa.Column('pyramid_index', sa.Integer(), nullable=False),
        sa.Column('entry_price', sa.Numeric(precision=20, scale=10), nullable=False),
        sa.Column('entry_timestamp', sa.DateTime(), nullable=False),
        sa.Column('signal_id', sa.String(), nullable=True),
        sa.Column('status', sa.Enum('pending', 'submitted', 'filled', 'cancelled', name='pyramid_status_enum', create_type=False), nullable=False),
        sa.Column('dca_config', sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(['group_id'], ['position_groups.id']),
        sa.PrimaryKeyConstraint('id')
    )

    # ===========================================
    # TABLE: risk_actions
    # ===========================================
    op.create_table('risk_actions',
        sa.Column('id', GUID(), nullable=False),
        sa.Column('group_id', GUID(), nullable=False),
        sa.Column('action_type', sa.Enum('offset_loss', 'manual_block', 'manual_skip', 'manual_close', 'engine_close', 'tp_hit', name='riskactiontype', create_type=False), nullable=False),
        sa.Column('timestamp', sa.DateTime(), nullable=True),
        sa.Column('loser_group_id', GUID(), nullable=True),
        sa.Column('loser_pnl_usd', sa.Numeric(precision=20, scale=10), nullable=True),
        sa.Column('winner_details', sa.JSON(), nullable=True),
        sa.Column('exit_price', sa.Numeric(precision=20, scale=10), nullable=True),
        sa.Column('entry_price', sa.Numeric(precision=20, scale=10), nullable=True),
        sa.Column('pnl_percent', sa.Numeric(precision=10, scale=4), nullable=True),
        sa.Column('realized_pnl_usd', sa.Numeric(precision=20, scale=10), nullable=True),
        sa.Column('quantity_closed', sa.Numeric(precision=20, scale=10), nullable=True),
        sa.Column('duration_seconds', sa.Numeric(precision=20, scale=2), nullable=True),
        sa.Column('notes', sa.String(), nullable=True),
        sa.ForeignKeyConstraint(['group_id'], ['position_groups.id']),
        sa.ForeignKeyConstraint(['loser_group_id'], ['position_groups.id']),
        sa.PrimaryKeyConstraint('id')
    )

    # Performance indexes
    op.create_index('ix_risk_actions_action_type', 'risk_actions', ['action_type'])
    op.create_index('ix_risk_actions_group_timestamp', 'risk_actions', ['group_id', 'timestamp'])

    # ===========================================
    # TABLE: dca_orders
    # ===========================================
    op.create_table('dca_orders',
        sa.Column('id', GUID(), nullable=False),
        sa.Column('group_id', GUID(), nullable=False),
        sa.Column('pyramid_id', GUID(), nullable=False),
        sa.Column('exchange_order_id', sa.String(), nullable=True),
        sa.Column('leg_index', sa.Integer(), nullable=False),
        sa.Column('symbol', sa.String(), nullable=False),
        sa.Column('side', sa.Enum('buy', 'sell', name='order_side_enum', create_type=False), nullable=False),
        sa.Column('order_type', sa.Enum('limit', 'market', name='order_type_enum', create_type=False), nullable=True),
        sa.Column('price', sa.Numeric(precision=20, scale=10), nullable=False),
        sa.Column('quantity', sa.Numeric(precision=20, scale=10), nullable=False),
        sa.Column('gap_percent', sa.Numeric(precision=10, scale=4), nullable=False),
        sa.Column('weight_percent', sa.Numeric(precision=10, scale=4), nullable=False),
        sa.Column('tp_percent', sa.Numeric(precision=10, scale=4), nullable=False),
        sa.Column('tp_price', sa.Numeric(precision=20, scale=10), nullable=False),
        sa.Column('status', sa.Enum('pending', 'trigger_pending', 'open', 'partially_filled', 'filled', 'cancelled', 'failed', name='order_status_enum', create_type=False), nullable=False),
        sa.Column('filled_quantity', sa.Numeric(precision=20, scale=10), nullable=True, server_default='0'),
        sa.Column('avg_fill_price', sa.Numeric(precision=20, scale=10), nullable=True),
        sa.Column('tp_hit', sa.Boolean(), nullable=True, server_default='false'),
        sa.Column('tp_order_id', sa.String(), nullable=True),
        sa.Column('tp_executed_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('submitted_at', sa.DateTime(), nullable=True),
        sa.Column('filled_at', sa.DateTime(), nullable=True),
        sa.Column('cancelled_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['group_id'], ['position_groups.id']),
        sa.ForeignKeyConstraint(['pyramid_id'], ['pyramids.id']),
        sa.PrimaryKeyConstraint('id')
    )

    # Performance indexes
    op.create_index('ix_dca_orders_group_status', 'dca_orders', ['group_id', 'status'])
    op.create_index('ix_dca_orders_pyramid_id', 'dca_orders', ['pyramid_id'])
    op.execute("""
        CREATE INDEX ix_dca_orders_exchange_order_id
        ON dca_orders (exchange_order_id)
        WHERE exchange_order_id IS NOT NULL
    """)
    op.execute("""
        CREATE INDEX ix_dca_orders_tp_order_id
        ON dca_orders (tp_order_id)
        WHERE tp_order_id IS NOT NULL
    """)


def downgrade() -> None:
    # Drop tables in reverse order (respecting foreign keys)
    op.drop_table('dca_orders')
    op.drop_table('risk_actions')
    op.drop_table('pyramids')
    op.drop_table('queued_signals')
    op.drop_table('position_groups')
    op.drop_table('dca_configurations')
    op.drop_table('users')

    # Drop enum types
    op.execute('DROP TYPE IF EXISTS riskactiontype')
    op.execute('DROP TYPE IF EXISTS take_profit_mode_enum')
    op.execute('DROP TYPE IF EXISTS tp_mode_enum')
    op.execute('DROP TYPE IF EXISTS entry_order_type_enum')
    op.execute('DROP TYPE IF EXISTS order_type_enum')
    op.execute('DROP TYPE IF EXISTS order_status_enum')
    op.execute('DROP TYPE IF EXISTS pyramid_status_enum')
    op.execute('DROP TYPE IF EXISTS queue_status_enum')
    op.execute('DROP TYPE IF EXISTS group_status_enum')
    op.execute('DROP TYPE IF EXISTS order_side_enum')
    op.execute('DROP TYPE IF EXISTS signal_side_enum')
    op.execute('DROP TYPE IF EXISTS position_side_enum')
