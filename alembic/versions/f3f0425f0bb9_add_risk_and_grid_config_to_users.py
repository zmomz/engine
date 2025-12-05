"""add risk and grid config to users

Revision ID: f3f0425f0bb9
Revises: e2e0425f0bb8
Create Date: 2025-11-21 20:50:00.000000

"""
from alembic import op
import sqlalchemy as sa
import json
from decimal import Decimal

# revision identifiers, used by Alembic.
revision = 'f3f0425f0bb9'
down_revision = 'e2e0425f0bb8'
branch_labels = None
depends_on = None

def decimal_default(obj):
    if isinstance(obj, Decimal):
        return str(obj)
    raise TypeError

def upgrade() -> None:
    # Add columns as nullable first
    op.add_column('users', sa.Column('risk_config', sa.JSON(), nullable=True))
    op.add_column('users', sa.Column('dca_grid_config', sa.JSON(), nullable=True))

    # Define default values
    default_risk_config = {
        "max_open_positions_global": 10,
        "max_open_positions_per_symbol": 1,
        "max_total_exposure_usd": "10000",
        "max_daily_loss_usd": "500",
        "loss_threshold_percent": "-1.5",
        "timer_start_condition": "after_all_dca_filled",
        "post_full_wait_minutes": 15,
        "max_winners_to_combine": 3,
        "use_trade_age_filter": False,
        "age_threshold_minutes": 120,
        "require_full_pyramids": True,
        "reset_timer_on_replacement": False,
        "partial_close_enabled": True,
        "min_close_notional": "10"
    }
    default_grid_config = []

    # Update existing rows
    op.execute(
        sa.text("UPDATE users SET risk_config = CAST(:risk_config AS JSON), dca_grid_config = CAST(:dca_grid_config AS JSON)").bindparams(
            risk_config=json.dumps(default_risk_config, default=decimal_default),
            dca_grid_config=json.dumps(default_grid_config)
        )
    )

    # Alter columns to be non-nullable
    op.alter_column('users', 'risk_config', nullable=False)
    op.alter_column('users', 'dca_grid_config', nullable=False)


def downgrade() -> None:
    op.drop_column('users', 'dca_grid_config')
    op.drop_column('users', 'risk_config')