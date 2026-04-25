"""add separate download counts

Revision ID: h1i2j3k4l5m6
Revises: g1h2i3j4k5l6
Create Date: 2025-01-01 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "h1i2j3k4l5m6"
down_revision: str | None = "g1h2i3j4k5l6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "uploadgroupsettings",
        sa.Column("separate_download_counts", sa.Boolean(), nullable=False, server_default=sa.text("0")),
    )
    op.add_column(
        "fileupload",
        sa.Column("public_download_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
    )
    op.add_column(
        "fileupload",
        sa.Column("restricted_download_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
    )


def downgrade() -> None:
    op.drop_column("fileupload", "restricted_download_count")
    op.drop_column("fileupload", "public_download_count")
    op.drop_column("uploadgroupsettings", "separate_download_counts")
