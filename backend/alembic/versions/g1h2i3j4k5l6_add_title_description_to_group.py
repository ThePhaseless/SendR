"""add title and description to upload group settings

Revision ID: g1h2i3j4k5l6
Revises: f1a2b3c4d5e6
Create Date: 2025-01-01 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "g1h2i3j4k5l6"
down_revision: str | None = "f1a2b3c4d5e6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("uploadgroupsettings", sa.Column("title", sa.String(), nullable=True))
    op.add_column("uploadgroupsettings", sa.Column("description", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("uploadgroupsettings", "description")
    op.drop_column("uploadgroupsettings", "title")
