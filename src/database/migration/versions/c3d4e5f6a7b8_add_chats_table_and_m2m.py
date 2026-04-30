"""add chats table and m2m

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-02-06 20:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c3d4e5f6a7b8"
down_revision: str | None = "b2c3d4e5f6a7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Create chats table
    op.create_table(
        "chats",
        sa.Column("name", sa.String(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint("name"),
    )

    # 2. Create manager_account_chats junction table
    op.create_table(
        "manager_account_chats",
        sa.Column("manager_account_id", sa.BIGINT(), nullable=False),
        sa.Column("chat_name", sa.String(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint("manager_account_id", "chat_name"),
        sa.ForeignKeyConstraint(["manager_account_id"], ["manager_accounts.id"]),
        sa.ForeignKeyConstraint(["chat_name"], ["chats.name"]),
    )

    # 3. Migrate existing data from bot_accounts.chat_name
    op.execute(
        """
        INSERT INTO chats (name)
        SELECT DISTINCT chat_name FROM bot_accounts
        WHERE chat_name IS NOT NULL
        ON CONFLICT DO NOTHING
        """
    )
    op.execute(
        """
        INSERT INTO manager_account_chats (manager_account_id, chat_name)
        SELECT DISTINCT manager_account_id, chat_name FROM bot_accounts
        WHERE chat_name IS NOT NULL
        ON CONFLICT DO NOTHING
        """
    )

    # 4. Drop chat_name column from bot_accounts
    op.drop_column("bot_accounts", "chat_name")


def downgrade() -> None:
    # 1. Add chat_name column back
    op.add_column(
        "bot_accounts",
        sa.Column("chat_name", sa.String(), nullable=True),
    )

    # 2. Restore data from junction table
    # NOTE: если после upgrade у менеджера появилось >1 чата через junction,
    # при downgrade bot_account получит только один (произвольный) chat_name —
    # PostgreSQL UPDATE FROM при множественном совпадении выбирает одну строку недетерминированно.
    op.execute(
        """
        UPDATE bot_accounts ba
        SET chat_name = mac.chat_name
        FROM manager_account_chats mac
        WHERE mac.manager_account_id = ba.manager_account_id
        """
    )

    # 3. Drop junction table and chats table
    op.drop_table("manager_account_chats")
    op.drop_table("chats")
