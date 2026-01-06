"""Add secure_signals to users table

Revision ID: 009_add_secure_signals
Revises: 008_add_closing_started_at
Create Date: 2026-01-06

This migration adds:
- users.secure_signals: Boolean flag to enable/disable webhook secret validation
  When True (default), webhook requests must include a valid secret in the payload.
  When False, webhooks are accepted without secret validation.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '009_add_secure_signals'
down_revision: Union[str, None] = '008_add_closing_started_at'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add secure_signals column to users with default True
    op.add_column('users',
        sa.Column('secure_signals', sa.Boolean(), nullable=False, server_default='true')
    )


def downgrade() -> None:
    op.drop_column('users', 'secure_signals')
