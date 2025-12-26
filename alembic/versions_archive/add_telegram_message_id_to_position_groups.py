"""add_telegram_message_id_to_position_groups

Revision ID: add_telegram_message_id_001
Revises: add_pyramid_aggregate_tp_001
Create Date: 2025-12-26

Adds telegram_message_id column to position_groups table for persisting
Telegram message IDs across restarts. This enables updating existing messages
instead of sending new ones.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'add_telegram_message_id_001'
down_revision: Union[str, None] = 'add_pyramid_aggregate_tp_001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('position_groups', sa.Column('telegram_message_id', sa.BigInteger(), nullable=True))


def downgrade() -> None:
    op.drop_column('position_groups', 'telegram_message_id')
