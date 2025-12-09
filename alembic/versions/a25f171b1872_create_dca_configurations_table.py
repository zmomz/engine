"""create_dca_configurations_table

Revision ID: a25f171b1872
Revises: 0b6af4c6d570
Create Date: 2025-12-07 15:48:45.456168

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'a25f171b1872'
down_revision: Union[str, None] = '0b6af4c6d570'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Just create the table - enums should already exist from other migrations
    # Use raw SQL with IF NOT EXISTS for safety
    op.execute("""
        CREATE TABLE IF NOT EXISTS dca_configurations (
            id UUID PRIMARY KEY,
            user_id UUID NOT NULL REFERENCES users(id),
            pair VARCHAR NOT NULL,
            timeframe VARCHAR NOT NULL,
            exchange VARCHAR NOT NULL,
            entry_order_type VARCHAR NOT NULL DEFAULT 'limit',
            dca_levels JSON NOT NULL DEFAULT '[]'::json,
            tp_mode VARCHAR NOT NULL DEFAULT 'per_leg',
            tp_settings JSON NOT NULL DEFAULT '{}'::json,
            max_pyramids INTEGER NOT NULL DEFAULT 5,
            created_at TIMESTAMP,
            updated_at TIMESTAMP,
            CONSTRAINT uix_user_pair_timeframe_exchange UNIQUE (user_id, pair, timeframe, exchange)
        )
    """)


def downgrade() -> None:
    op.drop_table('dca_configurations')
    op.execute('DROP TYPE IF EXISTS entry_order_type_enum')
    op.execute('DROP TYPE IF EXISTS take_profit_mode_enum')
