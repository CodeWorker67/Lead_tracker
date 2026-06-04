"""
Выгрузка всех пользователей и платежей бота в Excel (корень репозитория).

По умолчанию: bot_id=8425963080 (fastmobilevpnbot), без отсечки по времени.
Файлы: users.xlsx, payments.xlsx.

  uv run python scripts/export_bot_xlsx.py

  docker compose exec api uv run python scripts/export_bot_xlsx.py --out /app/repo
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from decimal import Decimal
from pathlib import Path

import pandas as pd
from loguru import logger
from sqlalchemy import select

_ROOT = Path(__file__).resolve().parent.parent
_SRC = _ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from database.core import SessionFactory  # noqa: E402
from database.models import Payment, User  # noqa: E402

DEFAULT_BOT_ID = 8425963080

USER_COLUMNS = [
    "user_id",
    "username",
    "full_name",
    "source",
    "created_at",
    "trial_at",
    "connected_at",
    "bot_id",
    "bot_name",
    "updated_at",
]

PAYMENT_COLUMNS = ["user_id", "amount", "created_at"]


async def export_users(session, bot_id: int, out: Path) -> int:
    stmt = (
        select(
            User.user_id,
            User.username,
            User.full_name,
            User.source,
            User.created_at,
            User.trial_at,
            User.connected_at,
            User.bot_id,
            User.bot_name,
            User.updated_at,
        )
        .where(User.bot_id == bot_id)
        .order_by(User.created_at)
    )
    rows = (await session.execute(stmt)).all()
    df = pd.DataFrame(rows, columns=USER_COLUMNS)
    df.to_excel(out, index=False, engine="openpyxl")
    logger.info("users: {} строк → {}", len(df), out)
    return len(df)


async def export_payments(session, bot_id: int, out: Path) -> int:
    stmt = (
        select(Payment.user_id, Payment.amount, Payment.created_at)
        .where(Payment.bot_id == bot_id)
        .order_by(Payment.created_at)
    )
    rows = (await session.execute(stmt)).all()
    data = [(r[0], float(r[1]) if isinstance(r[1], Decimal) else r[1], r[2]) for r in rows]
    df = pd.DataFrame(data, columns=PAYMENT_COLUMNS)
    df.to_excel(out, index=False, engine="openpyxl")
    logger.info("payments: {} строк → {}", len(df), out)
    return len(df)


async def main_async(bot_id: int, out_dir: Path) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    users_path = out_dir / "users.xlsx"
    payments_path = out_dir / "payments.xlsx"

    async with SessionFactory() as session:
        await export_users(session, bot_id, users_path)
        await export_payments(session, bot_id, payments_path)


def main() -> None:
    p = argparse.ArgumentParser(
        description="Экспорт всех users/payments в xlsx для бота (без фильтра по дате)."
    )
    p.add_argument(
        "--bot-id",
        type=int,
        default=DEFAULT_BOT_ID,
        help=f"Telegram bot_id (по умолчанию {DEFAULT_BOT_ID})",
    )
    p.add_argument(
        "--out",
        type=Path,
        default=_ROOT,
        help="Каталог для users.xlsx и payments.xlsx (по умолчанию корень репозитория)",
    )
    args = p.parse_args()
    asyncio.run(main_async(args.bot_id, args.out.resolve()))


if __name__ == "__main__":
    main()
