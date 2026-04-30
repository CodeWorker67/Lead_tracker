"""add bot_id to bot_accounts

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-02-06 18:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b2c3d4e5f6a7"
down_revision: str | None = "a1b2c3d4e5f6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "bot_accounts",
        sa.Column("bot_id", sa.BIGINT(), nullable=True),
    )
    op.create_unique_constraint("bot_accounts_bot_id_key", "bot_accounts", ["bot_id"])


def downgrade() -> None:
    op.drop_constraint("bot_accounts_bot_id_key", "bot_accounts", type_="unique")
    op.drop_column("bot_accounts", "bot_id")
