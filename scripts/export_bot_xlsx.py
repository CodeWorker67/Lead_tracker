"""
Выгрузка пользователей и платежей бота в Excel (корень репозитория).

По умолчанию: bot_id=7412940598, отсечка 2026-05-04 04:50 UTC (ISO: 2026-05-04T04:50:00+00:00).
Файлы: users.xlsx (user_id, created_at, trial_at, connected_at),
       payments.xlsx (user_id, amount, created_at).

  uv run python scripts/export_bot_xlsx.py

  docker compose exec api uv run python scripts/export_bot_xlsx.py --out /app/repo

Если в БД naive-время не в UTC, задайте --since в том же «календаре», что и created_at в Postgres.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import datetime, timezone
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

DEFAULT_BOT_ID = 7412940598
# Отсечка по умолчанию: 04.05.2026 04:50 UTC (как 4 мая 2026, DD.MM; если нужен 5 апреля — см. --since)


def _parse_since(s: str) -> datetime:
    """ISO-8601, например 2026-05-04T04:50:00Z или 2026-05-04T04:50:00+00:00."""
    t = s.strip().replace("Z", "+00:00")
    dt = datetime.fromisoformat(t)
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _for_db_compare(dt_utc: datetime) -> datetime:
    """Сравнение с колонками DateTime без tz: отдаём naive UTC (как обычно для UTC-инстанта)."""
    return dt_utc.astimezone(timezone.utc).replace(tzinfo=None)


async def export_users(session, bot_id: int, since_cmp: datetime, out: Path) -> int:
    stmt = (
        select(User.user_id, User.created_at, User.trial_at, User.connected_at)
        .where(User.bot_id == bot_id, User.created_at > since_cmp)
        .order_by(User.created_at)
    )
    rows = (await session.execute(stmt)).all()
    df = pd.DataFrame(rows, columns=["user_id", "created_at", "trial_at", "connected_at"])
    df.to_excel(out, index=False, engine="openpyxl")
    logger.info("users: {} строк → {}", len(df), out)
    return len(df)


async def export_payments(session, bot_id: int, since_cmp: datetime, out: Path) -> int:
    stmt = (
        select(Payment.user_id, Payment.amount, Payment.created_at)
        .where(Payment.bot_id == bot_id, Payment.created_at > since_cmp)
        .order_by(Payment.created_at)
    )
    rows = (await session.execute(stmt)).all()
    data = [(r[0], float(r[1]) if isinstance(r[1], Decimal) else r[1], r[2]) for r in rows]
    df = pd.DataFrame(data, columns=["user_id", "amount", "created_at"])
    df.to_excel(out, index=False, engine="openpyxl")
    logger.info("payments: {} строк → {}", len(df), out)
    return len(df)


async def main_async(bot_id: int, since_utc: datetime, out_dir: Path) -> None:
    since_cmp = _for_db_compare(since_utc)
    out_dir.mkdir(parents=True, exist_ok=True)
    users_path = out_dir / "users.xlsx"
    payments_path = out_dir / "payments.xlsx"

    async with SessionFactory() as session:
        await export_users(session, bot_id, since_cmp, users_path)
        await export_payments(session, bot_id, since_cmp, payments_path)


def main() -> None:
    p = argparse.ArgumentParser(description="Экспорт users/payments в xlsx для бота.")
    p.add_argument(
        "--bot-id",
        type=int,
        default=DEFAULT_BOT_ID,
        help=f"Telegram bot_id (по умолчанию {DEFAULT_BOT_ID})",
    )
    p.add_argument(
        "--since",
        type=str,
        default="2026-05-04T04:50:00+00:00",
        help="Нижняя граница по времени (UTC), строго позже этой отметки",
    )
    p.add_argument(
        "--out",
        type=Path,
        default=_ROOT,
        help="Каталог для users.xlsx и payments.xlsx (по умолчанию корень репозитория)",
    )
    args = p.parse_args()
    since_utc = _parse_since(args.since)
    asyncio.run(main_async(args.bot_id, since_utc, args.out.resolve()))


if __name__ == "__main__":
    main()
