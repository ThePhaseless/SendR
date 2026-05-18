"""add scan status fields

Revision ID: 0002_add_scan_status
Revises: 0001_initial_schema
Create Date: 2026-05-17 00:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0002_add_scan_status"
down_revision: str | Sequence[str] | None = "0001_initial_schema"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    scan_status = sa.Enum(
        "queued",
        "scanning",
        "clean",
        "infected",
        "failed",
        name="scanstatus",
    )
    scan_status.create(op.get_bind(), checkfirst=True)

    op.add_column(
        "fileupload",
        sa.Column(
            "scan_status",
            scan_status,
            nullable=False,
            server_default="clean",
        ),
    )
    op.add_column(
        "fileupload",
        sa.Column("scan_enqueued_at", sa.DateTime(), nullable=True),
    )
    op.add_column(
        "fileupload",
        sa.Column("scan_started_at", sa.DateTime(), nullable=True),
    )
    op.add_column(
        "fileupload",
        sa.Column("scan_completed_at", sa.DateTime(), nullable=True),
    )
    op.add_column(
        "fileupload",
        sa.Column("scan_failure_code", sa.String(), nullable=True),
    )
    op.add_column(
        "fileupload",
        sa.Column("scan_failure_message", sa.String(), nullable=True),
    )
    op.add_column(
        "fileupload",
        sa.Column("malware_signature", sa.String(), nullable=True),
    )

    op.create_index(
        op.f("ix_fileupload_scan_status"),
        "fileupload",
        ["scan_status"],
        unique=False,
    )
    op.create_index(
        op.f("ix_fileupload_scan_enqueued_at"),
        "fileupload",
        ["scan_enqueued_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_fileupload_scan_enqueued_at"), table_name="fileupload")
    op.drop_index(op.f("ix_fileupload_scan_status"), table_name="fileupload")
    op.drop_column("fileupload", "malware_signature")
    op.drop_column("fileupload", "scan_failure_message")
    op.drop_column("fileupload", "scan_failure_code")
    op.drop_column("fileupload", "scan_completed_at")
    op.drop_column("fileupload", "scan_started_at")
    op.drop_column("fileupload", "scan_enqueued_at")
    op.drop_column("fileupload", "scan_status")

    sa.Enum(name="scanstatus").drop(op.get_bind(), checkfirst=True)
