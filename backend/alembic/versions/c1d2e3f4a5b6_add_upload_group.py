"""add upload_group to fileupload

Revision ID: c1d2e3f4a5b6
Revises: b1c2d3e4f5a6
Create Date: 2026-03-18 14:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c1d2e3f4a5b6"
down_revision: str | Sequence[str] | None = "b1c2d3e4f5a6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("fileupload", sa.Column("upload_group", sa.String(), nullable=True))
    op.create_index(op.f("ix_fileupload_upload_group"), "fileupload", ["upload_group"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_fileupload_upload_group"), table_name="fileupload")
    op.drop_column("fileupload", "upload_group")
