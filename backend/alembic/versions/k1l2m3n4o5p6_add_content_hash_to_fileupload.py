"""add content hash to fileupload

Revision ID: k1l2m3n4o5p6
Revises: j1k2l3m4n5o6
Create Date: 2026-05-02 22:50:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "k1l2m3n4o5p6"
down_revision: str | Sequence[str] | None = "j1k2l3m4n5o6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("fileupload", sa.Column("content_hash", sa.String(), nullable=True))
    op.create_index(op.f("ix_fileupload_content_hash"), "fileupload", ["content_hash"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_fileupload_content_hash"), table_name="fileupload")
    op.drop_column("fileupload", "content_hash")