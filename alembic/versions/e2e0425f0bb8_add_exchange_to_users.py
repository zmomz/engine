"""add exchange to users

Revision ID: e2e0425f0bb8
Revises: d1ca0ad60d16
Create Date: 2025-11-20 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e2e0425f0bb8'
down_revision: Union[str, None] = 'd1ca0ad60d16'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('users', sa.Column('exchange', sa.String(), nullable=False, server_default='binance'))


def downgrade() -> None:
    op.drop_column('users', 'exchange')
