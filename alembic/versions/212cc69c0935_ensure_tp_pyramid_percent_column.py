"""ensure_tp_pyramid_percent_column

Revision ID: 212cc69c0935
Revises: a25f171b1872
Create Date: 2025-12-07 17:18:26.363759

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '212cc69c0935'
down_revision: Union[str, None] = 'a25f171b1872'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE position_groups ADD COLUMN IF NOT EXISTS tp_pyramid_percent NUMERIC(10, 4)")


def downgrade() -> None:
    # We choose not to drop it in downgrade to be safe, or we can look up if we should.
    # Since this is a "fix" migration, standard practice is to revert the change (drop column).
    op.execute("ALTER TABLE position_groups DROP COLUMN IF EXISTS tp_pyramid_percent")
