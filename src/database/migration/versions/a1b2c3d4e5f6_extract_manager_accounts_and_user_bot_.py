"""extract manager_accounts and user_bot_accounts

Revision ID: a1b2c3d4e5f6
Revises: 5d490abdc3a2
Create Date: 2026-02-06 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: str | None = "5d490abdc3a2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    # 1. Create manager_accounts table
    op.create_table(
        "manager_accounts",
        sa.Column("id", sa.BIGINT(), nullable=False),
        sa.Column("username", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )

    # 2. Create user_bot_accounts junction table
    op.create_table(
        "user_bot_accounts",
        sa.Column("user_id", sa.BIGINT(), nullable=False),
        sa.Column("bot_account_id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["bot_account_id"], ["bot_accounts.id"]),
        sa.PrimaryKeyConstraint("user_id", "bot_account_id"),
    )

    # 3. Add manager_account_id column to bot_accounts (nullable initially)
    op.add_column(
        "bot_accounts",
        sa.Column("manager_account_id", sa.BIGINT(), nullable=True),
    )

    # 4. Migrate data: insert distinct managers from bot_accounts
    op.execute(
        """
        INSERT INTO manager_accounts (id, username, created_at)
        SELECT DISTINCT bot_id, username, created_at
        FROM bot_accounts
        """
    )

    # 5. Set manager_account_id = bot_id for all existing bot_accounts
    op.execute(
        """
        UPDATE bot_accounts SET manager_account_id = bot_id
        """
    )

    # 6. Migrate user -> bot_account links to junction table
    op.execute(
        """
        INSERT INTO user_bot_accounts (user_id, bot_account_id, created_at)
        SELECT id, source_account_id, created_at
        FROM users
        WHERE source_account_id IS NOT NULL
        """
    )

    # 7. Make manager_account_id NOT NULL
    op.alter_column(
        "bot_accounts",
        "manager_account_id",
        nullable=False,
    )

    # 8. Add FK and index on bot_accounts.manager_account_id
    op.create_foreign_key(
        "bot_accounts_manager_account_id_fkey",
        "bot_accounts",
        "manager_accounts",
        ["manager_account_id"],
        ["id"],
    )
    op.create_index(
        op.f("ix_bot_accounts_manager_account_id"),
        "bot_accounts",
        ["manager_account_id"],
    )

    # 9. Drop unique constraint and columns (bot_id, username) from bot_accounts
    op.drop_constraint("bot_accounts_bot_id_key", "bot_accounts", type_="unique")
    op.drop_column("bot_accounts", "bot_id")
    op.drop_column("bot_accounts", "username")

    # 10. Drop FK, index and column source_account_id from users
    op.drop_constraint("users_source_account_id_fkey", "users", type_="foreignkey")
    op.drop_index("ix_users_source_account_id", table_name="users")
    op.drop_column("users", "source_account_id")


def downgrade() -> None:
    """Downgrade schema."""
    # 1. Re-add source_account_id to users
    op.add_column(
        "users",
        sa.Column("source_account_id", sa.UUID(), nullable=True),
    )
    op.create_index("ix_users_source_account_id", "users", ["source_account_id"])

    # 2. Re-add bot_id and username to bot_accounts
    op.add_column(
        "bot_accounts",
        sa.Column("bot_id", sa.BIGINT(), nullable=True),
    )
    op.add_column(
        "bot_accounts",
        sa.Column("username", sa.String(), nullable=True),
    )

    # 3. Restore bot_id and username from manager_accounts
    op.execute(
        """
        UPDATE bot_accounts
        SET bot_id = manager_account_id,
            username = (
                SELECT ma.username
                FROM manager_accounts ma
                WHERE ma.id = bot_accounts.manager_account_id
            )
        """
    )

    # 4. Make bot_id NOT NULL and unique
    op.alter_column("bot_accounts", "bot_id", nullable=False)
    op.create_unique_constraint("bot_accounts_bot_id_key", "bot_accounts", ["bot_id"])

    # 5. Restore source_account_id from junction table
    op.execute(
        """
        UPDATE users
        SET source_account_id = uba.bot_account_id
        FROM (
            SELECT DISTINCT ON (user_id) user_id, bot_account_id
            FROM user_bot_accounts
            ORDER BY user_id, created_at
        ) uba
        WHERE users.id = uba.user_id
        """
    )

    # 6. Re-add FK on users.source_account_id
    op.create_foreign_key(
        "users_source_account_id_fkey",
        "users",
        "bot_accounts",
        ["source_account_id"],
        ["id"],
    )

    # 7. Drop manager_account_id from bot_accounts
    op.drop_index(op.f("ix_bot_accounts_manager_account_id"), table_name="bot_accounts")
    op.drop_constraint(
        "bot_accounts_manager_account_id_fkey", "bot_accounts", type_="foreignkey"
    )
    op.drop_column("bot_accounts", "manager_account_id")

    # 8. Drop junction table and manager_accounts
    op.drop_table("user_bot_accounts")
    op.drop_table("manager_accounts")
