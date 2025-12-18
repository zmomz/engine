"""add_pyramid_aggregate_tp_mode

Revision ID: add_pyramid_aggregate_tp_001
Revises: add_new_risk_action_types_001
Create Date: 2025-12-18

Adds new enum value to TakeProfitMode:
- PYRAMID_AGGREGATE: Closes entire pyramid when aggregate TP target is hit
"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'add_pyramid_aggregate_tp_001'
down_revision: Union[str, None] = 'add_new_risk_action_types_001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add new enum value to take_profit_mode_enum
    # PostgreSQL requires ALTER TYPE to add new enum values
    op.execute("ALTER TYPE take_profit_mode_enum ADD VALUE IF NOT EXISTS 'pyramid_aggregate'")


def downgrade() -> None:
    # PostgreSQL doesn't support removing enum values directly
    # Would need to recreate the enum type, which is complex
    # For now, we'll leave the enum value in place during downgrade
    pass
