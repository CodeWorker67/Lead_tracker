"""postback dashboard schema (users uuid, payments composite fk)

Revision ID: e8f9a0b1c2d3
Revises: 05fb0aa51d37
Create Date: 2026-04-30

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "e8f9a0b1c2d3"
down_revision: Union[str, None] = "05fb0aa51d37"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_table("payments")
    op.drop_table("user_bot_accounts")
    op.drop_table("bot_accounts")
    op.drop_table("manager_account_chats")
    op.drop_table("chats")
    op.drop_table("manager_accounts")
    op.drop_table("sources")
    op.drop_table("users")

    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("username", sa.String(), nullable=True),
        sa.Column("full_name", sa.String(), nullable=True),
        sa.Column("source", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("bot_id", sa.BigInteger(), nullable=False),
        sa.Column("bot_name", sa.String(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.Column("trial_at", sa.DateTime(), nullable=True),
        sa.Column("connected_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "bot_id", name="uq_users_telegram_bot"),
    )

    op.create_table(
        "payments",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("bot_id", sa.BigInteger(), nullable=False),
        sa.Column("amount", sa.Numeric(10, 2), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id", "bot_id"],
            ["users.user_id", "users.bot_id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade() -> None:
    raise NotImplementedError("Возврат к старой схеме не поддерживается")
