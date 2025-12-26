"""add telegram_config to users

Revision ID: telegram_config_001
Revises: fd17aff21f62
Create Date: 2025-12-13

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSON


# revision identifiers, used by Alembic.
revision = 'telegram_config_001'
down_revision = 'fd17aff21f62'
branch_labels = None
depends_on = None


def upgrade():
    # Add telegram_config column to users table
    op.add_column('users', sa.Column('telegram_config', JSON, nullable=True))


def downgrade():
    # Remove telegram_config column from users table
    op.drop_column('users', 'telegram_config')
