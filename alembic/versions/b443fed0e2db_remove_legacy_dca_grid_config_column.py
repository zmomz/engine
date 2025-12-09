"""remove_legacy_dca_grid_config_column

Revision ID: b443fed0e2db
Revises: 212cc69c0935
Create Date: 2025-12-07 20:23:27.110691

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b443fed0e2db'
down_revision: Union[str, None] = '212cc69c0935'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_column('users', 'dca_grid_config')


def downgrade() -> None:
    # Re-add the column with JSON type and default value
    # Default value should structurally match DCAGridConfig(levels=[]) which is {"levels": [], ...}
    # But for raw JSON, '{}' or a more proper default is safer. 
    # Based on User model: default=DCAGridConfig(levels=[]).model_dump(mode='json')
    # {"levels": [], "tp_mode": "per_leg", ...}
    
    # We will just add it as nullable=True first, or nullable=False with server_default='{}'
    op.add_column('users', sa.Column('dca_grid_config', sa.JSON(), nullable=False, server_default='{"levels": [], "tp_mode": "per_leg"}'))
