"""remove_pyramid_tp_mode

Revision ID: a9f8d2c1e4b3
Revises: 138cbc15282d
Create Date: 2025-12-09 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a9f8d2c1e4b3'
down_revision: Union[str, None] = '138cbc15282d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Update any existing records using 'pyramid' mode to 'per_leg'
    op.execute("""
        UPDATE dca_configurations
        SET tp_mode = 'per_leg'
        WHERE tp_mode = 'pyramid'
    """)

    op.execute("""
        UPDATE position_groups
        SET tp_mode = 'per_leg'
        WHERE tp_mode = 'pyramid'
    """)

    # Remove tp_pyramid_percent column from position_groups
    op.drop_column('position_groups', 'tp_pyramid_percent')

    # Recreate the enum without 'pyramid'
    # Create new enum type
    op.execute("CREATE TYPE take_profit_mode_enum_new AS ENUM ('per_leg', 'aggregate', 'hybrid')")

    # Update dca_configurations table
    op.execute("""
        ALTER TABLE dca_configurations
          ALTER COLUMN tp_mode DROP DEFAULT,
          ALTER COLUMN tp_mode TYPE take_profit_mode_enum_new
            USING tp_mode::text::take_profit_mode_enum_new,
          ALTER COLUMN tp_mode SET DEFAULT 'per_leg'::take_profit_mode_enum_new
    """)

    # Update position_groups table
    op.execute("""
        ALTER TABLE position_groups
          ALTER COLUMN tp_mode TYPE take_profit_mode_enum_new
            USING tp_mode::text::take_profit_mode_enum_new
    """)

    # Drop old enum and rename new one
    op.execute("DROP TYPE take_profit_mode_enum")
    op.execute("ALTER TYPE take_profit_mode_enum_new RENAME TO take_profit_mode_enum")


def downgrade() -> None:
    # Recreate the enum with 'pyramid'
    op.execute("CREATE TYPE take_profit_mode_enum_new AS ENUM ('per_leg', 'pyramid', 'aggregate', 'hybrid')")

    # Update dca_configurations table
    op.execute("""
        ALTER TABLE dca_configurations
          ALTER COLUMN tp_mode DROP DEFAULT,
          ALTER COLUMN tp_mode TYPE take_profit_mode_enum_new
            USING tp_mode::text::take_profit_mode_enum_new,
          ALTER COLUMN tp_mode SET DEFAULT 'per_leg'::take_profit_mode_enum_new
    """)

    # Update position_groups table
    op.execute("""
        ALTER TABLE position_groups
          ALTER COLUMN tp_mode TYPE take_profit_mode_enum_new
            USING tp_mode::text::take_profit_mode_enum_new
    """)

    # Drop old enum and rename new one
    op.execute("DROP TYPE take_profit_mode_enum")
    op.execute("ALTER TYPE take_profit_mode_enum_new RENAME TO take_profit_mode_enum")

    # Re-add tp_pyramid_percent column to position_groups
    op.add_column('position_groups',
                  sa.Column('tp_pyramid_percent', sa.Numeric(10, 4), nullable=True))
