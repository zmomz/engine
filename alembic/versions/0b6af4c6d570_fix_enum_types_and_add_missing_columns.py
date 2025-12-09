"""fix_enum_types_and_add_missing_columns

Revision ID: 0b6af4c6d570
Revises: 972238fb0887
Create Date: 2025-12-07 15:23:56.992782

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '0b6af4c6d570'
down_revision: Union[str, None] = '972238fb0887'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add 'pyramid' to tp_mode_enum
    op.execute("ALTER TYPE tp_mode_enum ADD VALUE IF NOT EXISTS 'pyramid'")
    
    # Add 'trigger_pending' to order_status_enum
    op.execute("ALTER TYPE order_status_enum ADD VALUE IF NOT EXISTS 'trigger_pending'")
    
    # Add tp_pyramid_percent column to position_groups
    op.add_column('position_groups', sa.Column('tp_pyramid_percent', sa.Numeric(precision=10, scale=4), nullable=True))


def downgrade() -> None:
    # Note: PostgreSQL doesn't support removing enum values easily
    # We'll just remove the column
    op.drop_column('position_groups', 'tp_pyramid_percent')
