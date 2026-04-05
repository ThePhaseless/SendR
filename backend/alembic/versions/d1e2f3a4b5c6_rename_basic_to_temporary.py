"""rename_basic_to_temporary

Revision ID: d1e2f3a4b5c6
Revises: 8cb9b35cf603
Create Date: 2026-04-04 00:00:00.000000

"""

from typing import TYPE_CHECKING

import sqlalchemy as sa

from alembic import op

if TYPE_CHECKING:
    from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "d1e2f3a4b5c6"
down_revision: str | Sequence[str] | None = "8cb9b35cf603"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Rename 'basic' tier to 'temporary'."""
    op.execute(sa.text("UPDATE user SET tier = 'temporary' WHERE tier = 'basic'"))


def downgrade() -> None:
    """Rename 'temporary' tier back to 'basic'."""
    op.execute(sa.text("UPDATE user SET tier = 'basic' WHERE tier = 'temporary'"))
