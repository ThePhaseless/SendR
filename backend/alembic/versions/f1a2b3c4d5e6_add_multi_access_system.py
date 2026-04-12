"""add multi-access system (passwords, emails, download logs)

Revision ID: f1a2b3c4d5e6
Revises: e1f2a3b4c5d6
Create Date: 2026-04-12 00:00:00.000000

"""

from collections.abc import Sequence
from uuid import uuid4

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f1a2b3c4d5e6"
down_revision: str | Sequence[str] | None = "e1f2a3b4c5d6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Create new tables
    op.create_table(
        "uploadgroupsettings",
        sa.Column("upload_group", sa.String(), nullable=False, primary_key=True),
        sa.Column("is_public", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("show_email_stats", sa.Boolean(), nullable=False, server_default=sa.text("0")),
    )
    op.create_index("ix_uploadgroupsettings_upload_group", "uploadgroupsettings", ["upload_group"])

    op.create_table(
        "uploadpassword",
        sa.Column("id", sa.Integer(), nullable=False, primary_key=True, autoincrement=True),
        sa.Column("upload_group", sa.String(), nullable=False),
        sa.Column("label", sa.String(), nullable=False),
        sa.Column("password_hash", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_uploadpassword_upload_group", "uploadpassword", ["upload_group"])

    op.create_table(
        "uploademailrecipient",
        sa.Column("id", sa.Integer(), nullable=False, primary_key=True, autoincrement=True),
        sa.Column("upload_group", sa.String(), nullable=False),
        sa.Column("email", sa.String(), nullable=False),
        sa.Column("token_hash", sa.String(), nullable=False),
        sa.Column("notified", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_uploademailrecipient_upload_group", "uploademailrecipient", ["upload_group"])
    op.create_index("ix_uploademailrecipient_token_hash", "uploademailrecipient", ["token_hash"])

    op.create_table(
        "downloadlog",
        sa.Column("id", sa.Integer(), nullable=False, primary_key=True, autoincrement=True),
        sa.Column("upload_group", sa.String(), nullable=False),
        sa.Column("file_upload_id", sa.Integer(), sa.ForeignKey("fileupload.id"), nullable=True),
        sa.Column("access_type", sa.String(), nullable=False),
        sa.Column("upload_password_id", sa.Integer(), sa.ForeignKey("uploadpassword.id"), nullable=True),
        sa.Column("email_recipient_id", sa.Integer(), sa.ForeignKey("uploademailrecipient.id"), nullable=True),
        sa.Column("downloaded_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_downloadlog_upload_group", "downloadlog", ["upload_group"])

    # 2. Backfill NULL upload_group values with UUIDs
    conn = op.get_bind()
    rows = conn.execute(sa.text("SELECT id FROM fileupload WHERE upload_group IS NULL")).fetchall()
    for row in rows:
        conn.execute(
            sa.text("UPDATE fileupload SET upload_group = :group WHERE id = :id"),
            {"group": str(uuid4()), "id": row[0]},
        )

    # 3. Migrate existing password_hash entries into uploadpassword table
    rows_with_pw = conn.execute(
        sa.text(
            "SELECT DISTINCT upload_group, password_hash FROM fileupload "
            "WHERE password_hash IS NOT NULL AND upload_group IS NOT NULL"
        )
    ).fetchall()
    for row in rows_with_pw:
        conn.execute(
            sa.text(
                "INSERT INTO uploadpassword (upload_group, label, password_hash, created_at) "
                "VALUES (:group, :label, :hash, datetime('now'))"
            ),
            {"group": row[0], "label": "Password", "hash": row[1]},
        )

    # 4. Create UploadGroupSettings for existing groups
    existing_groups = conn.execute(
        sa.text("SELECT DISTINCT upload_group FROM fileupload WHERE upload_group IS NOT NULL")
    ).fetchall()
    for row in existing_groups:
        conn.execute(
            sa.text(
                "INSERT OR IGNORE INTO uploadgroupsettings (upload_group, is_public, show_email_stats) "
                "VALUES (:group, 1, 0)"
            ),
            {"group": row[0]},
        )

    # 5. Drop password_hash column from fileupload
    # SQLite doesn't support DROP COLUMN directly before 3.35.0,
    # but Alembic batch mode handles this
    with op.batch_alter_table("fileupload") as batch_op:
        batch_op.drop_column("password_hash")


def downgrade() -> None:
    with op.batch_alter_table("fileupload") as batch_op:
        batch_op.add_column(sa.Column("password_hash", sa.String(), nullable=True))

    op.drop_table("downloadlog")
    op.drop_table("uploademailrecipient")
    op.drop_table("uploadpassword")
    op.drop_table("uploadgroupsettings")
