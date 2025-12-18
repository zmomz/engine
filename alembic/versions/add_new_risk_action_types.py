"""add_new_risk_action_types

Revision ID: add_new_risk_action_types_001
Revises: add_close_action_fields_001
Create Date: 2025-12-18

Adds new enum values to RiskActionType:
- MANUAL_CLOSE
- ENGINE_CLOSE
- TP_HIT
"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = 'add_new_risk_action_types_001'
down_revision: Union[str, None] = 'add_close_action_fields_001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add new enum values to riskactiontype
    # PostgreSQL requires ALTER TYPE to add new enum values
    op.execute("ALTER TYPE riskactiontype ADD VALUE IF NOT EXISTS 'manual_close'")
    op.execute("ALTER TYPE riskactiontype ADD VALUE IF NOT EXISTS 'engine_close'")
    op.execute("ALTER TYPE riskactiontype ADD VALUE IF NOT EXISTS 'tp_hit'")


def downgrade() -> None:
    # PostgreSQL doesn't support removing enum values directly
    # Would need to recreate the enum type, which is complex
    # For now, we'll leave the enum values in place during downgrade
    pass
