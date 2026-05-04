"""initial schema

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-05-04 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
import sqlmodel

from alembic import op

revision: str = "0001_initial_schema"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "user",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("email", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("password_hash", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column(
            "tier",
            sa.Enum("temporary", "free", "premium", name="usertier"),
            nullable=False,
        ),
        sa.Column("is_admin", sa.Boolean(), nullable=False),
        sa.Column("is_banned", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_user_email"), "user", ["email"], unique=True)

    op.create_table(
        "uploadgroupsettings",
        sa.Column("upload_group", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("is_public", sa.Boolean(), nullable=False),
        sa.Column("show_email_stats", sa.Boolean(), nullable=False),
        sa.Column("separate_download_counts", sa.Boolean(), nullable=False),
        sa.Column("title", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("description", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.PrimaryKeyConstraint("upload_group"),
    )
    op.create_index(
        op.f("ix_uploadgroupsettings_upload_group"),
        "uploadgroupsettings",
        ["upload_group"],
        unique=False,
    )

    op.create_table(
        "uploadpassword",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("upload_group", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("label", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("password_hash", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_uploadpassword_upload_group"),
        "uploadpassword",
        ["upload_group"],
        unique=False,
    )

    op.create_table(
        "uploademailrecipient",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("upload_group", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("email", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("token_hash", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("notified", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_uploademailrecipient_token_hash"),
        "uploademailrecipient",
        ["token_hash"],
        unique=False,
    )
    op.create_index(
        op.f("ix_uploademailrecipient_upload_group"),
        "uploademailrecipient",
        ["upload_group"],
        unique=False,
    )

    op.create_table(
        "verificationcode",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("email", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("code", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("used", sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_verificationcode_email"), "verificationcode", ["email"], unique=False
    )

    op.create_table(
        "authtoken",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("token", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_authtoken_token"), "authtoken", ["token"], unique=True)
    op.create_index(
        op.f("ix_authtoken_user_id"), "authtoken", ["user_id"], unique=False
    )

    op.create_table(
        "fileupload",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column(
            "original_filename", sqlmodel.sql.sqltypes.AutoString(), nullable=False
        ),
        sa.Column(
            "stored_filename", sqlmodel.sql.sqltypes.AutoString(), nullable=False
        ),
        sa.Column("content_hash", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("file_size_bytes", sa.Integer(), nullable=False),
        sa.Column("download_token", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("download_count", sa.Integer(), nullable=False),
        sa.Column("public_download_count", sa.Integer(), nullable=False),
        sa.Column("restricted_download_count", sa.Integer(), nullable=False),
        sa.Column("max_downloads", sa.Integer(), nullable=True),
        sa.Column("upload_group", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_fileupload_content_hash"), "fileupload", ["content_hash"], unique=False
    )
    op.create_index(
        op.f("ix_fileupload_download_token"),
        "fileupload",
        ["download_token"],
        unique=True,
    )
    op.create_index(
        op.f("ix_fileupload_upload_group"), "fileupload", ["upload_group"], unique=False
    )
    op.create_index(
        op.f("ix_fileupload_user_id"), "fileupload", ["user_id"], unique=False
    )

    op.create_table(
        "subscription",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column(
            "plan", sa.Enum("free", "premium", name="subscriptionplan"), nullable=False
        ),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_subscription_user_id"), "subscription", ["user_id"], unique=False
    )

    op.create_table(
        "transfer",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("upload_group", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("message", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column(
            "recipient_emails", sqlmodel.sql.sqltypes.AutoString(), nullable=True
        ),
        sa.Column("password_hash", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("notify_on_download", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_transfer_upload_group"), "transfer", ["upload_group"], unique=True
    )
    op.create_index(op.f("ix_transfer_user_id"), "transfer", ["user_id"], unique=False)

    op.create_table(
        "userlogin",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("auth_method", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("ip_address", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("logged_in_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["user.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_userlogin_user_id"), "userlogin", ["user_id"], unique=False
    )

    op.create_table(
        "downloadlog",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("upload_group", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("file_upload_id", sa.Integer(), nullable=True),
        sa.Column("access_type", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("upload_password_id", sa.Integer(), nullable=True),
        sa.Column("email_recipient_id", sa.Integer(), nullable=True),
        sa.Column("downloaded_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["email_recipient_id"], ["uploademailrecipient.id"]),
        sa.ForeignKeyConstraint(["file_upload_id"], ["fileupload.id"]),
        sa.ForeignKeyConstraint(["upload_password_id"], ["uploadpassword.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_downloadlog_upload_group"),
        "downloadlog",
        ["upload_group"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_downloadlog_upload_group"), table_name="downloadlog")
    op.drop_table("downloadlog")
    op.drop_index(op.f("ix_userlogin_user_id"), table_name="userlogin")
    op.drop_table("userlogin")
    op.drop_index(op.f("ix_transfer_user_id"), table_name="transfer")
    op.drop_index(op.f("ix_transfer_upload_group"), table_name="transfer")
    op.drop_table("transfer")
    op.drop_index(op.f("ix_subscription_user_id"), table_name="subscription")
    op.drop_table("subscription")
    op.drop_index(op.f("ix_fileupload_user_id"), table_name="fileupload")
    op.drop_index(op.f("ix_fileupload_upload_group"), table_name="fileupload")
    op.drop_index(op.f("ix_fileupload_download_token"), table_name="fileupload")
    op.drop_index(op.f("ix_fileupload_content_hash"), table_name="fileupload")
    op.drop_table("fileupload")
    op.drop_index(op.f("ix_authtoken_user_id"), table_name="authtoken")
    op.drop_index(op.f("ix_authtoken_token"), table_name="authtoken")
    op.drop_table("authtoken")
    op.drop_index(op.f("ix_verificationcode_email"), table_name="verificationcode")
    op.drop_table("verificationcode")
    op.drop_index(
        op.f("ix_uploademailrecipient_upload_group"), table_name="uploademailrecipient"
    )
    op.drop_index(
        op.f("ix_uploademailrecipient_token_hash"), table_name="uploademailrecipient"
    )
    op.drop_table("uploademailrecipient")
    op.drop_index(op.f("ix_uploadpassword_upload_group"), table_name="uploadpassword")
    op.drop_table("uploadpassword")
    op.drop_index(
        op.f("ix_uploadgroupsettings_upload_group"), table_name="uploadgroupsettings"
    )
    op.drop_table("uploadgroupsettings")
    op.drop_index(op.f("ix_user_email"), table_name="user")
    op.drop_table("user")
