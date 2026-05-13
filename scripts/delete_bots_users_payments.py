"""
Удаление из БД всех пользователей и платежей для указанных bot_id.

По умолчанию bot_id: 8159162956, 8418427746, 8713389924.

ОПАСНО: данные безвозвратно удаляются. Запуск только с флагом --yes.

На остальные боты и дашборд по ним не влияет — удаляются только строки
с этими bot_id в таблицах users и payments.

  docker compose exec api uv run python scripts/delete_bots_users_payments.py --yes

  uv run python scripts/delete_bots_users_payments.py --yes
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

from loguru import logger
from sqlalchemy import delete, func, select

_ROOT = Path(__file__).resolve().parent.parent
_SRC = _ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from database.core import SessionFactory  # noqa: E402
from database.models import Payment, User  # noqa: E402

DEFAULT_BOT_IDS = (8159162956, 8418427746, 8713389924)


async def _count(session, model, bot_ids: tuple[int, ...]) -> int:
    stmt = select(func.count()).select_from(model).where(model.bot_id.in_(bot_ids))
    return int((await session.execute(stmt)).scalar_one())


async def run_delete(bot_ids: tuple[int, ...]) -> None:
    async with SessionFactory() as session:
        n_pay_before = await _count(session, Payment, bot_ids)
        n_user_before = await _count(session, User, bot_ids)
        logger.info(
            "Удаление: bot_id in {}. Сейчас в БД: payments={}, users={}",
            list(bot_ids),
            n_pay_before,
            n_user_before,
        )

        r_pay = await session.execute(delete(Payment).where(Payment.bot_id.in_(bot_ids)))
        deleted_pay = r_pay.rowcount if r_pay.rowcount is not None else 0
        r_user = await session.execute(delete(User).where(User.bot_id.in_(bot_ids)))
        deleted_user = r_user.rowcount if r_user.rowcount is not None else 0

        await session.commit()
        logger.info(
            "Готово. Удалено payments={}, users={} (платежи — до удаления пользователей).",
            deleted_pay,
            deleted_user,
        )


def main() -> None:
    p = argparse.ArgumentParser(
        description="Удалить users и payments для заданных bot_id.",
    )
    p.add_argument(
        "--yes",
        action="store_true",
        help="Подтверждение: без этого флага скрипт ничего не удалит",
    )
    p.add_argument(
        "--bot-ids",
        type=str,
        default=",".join(str(x) for x in DEFAULT_BOT_IDS),
        help="Список bot_id через запятую (по умолчанию три заданных бота)",
    )
    args = p.parse_args()

    if not args.yes:
        logger.error(
            "Отказ: передайте --yes для выполнения удаления. "
            "Пример: uv run python scripts/delete_bots_users_payments.py --yes"
        )
        raise SystemExit(1)

    raw = [x.strip() for x in args.bot_ids.split(",") if x.strip()]
    try:
        bot_ids = tuple(int(x) for x in raw)
    except ValueError as e:
        raise SystemExit(f"Некорректный --bot-ids: {e}") from e
    if not bot_ids:
        raise SystemExit("Пустой список bot_id")

    asyncio.run(run_delete(bot_ids))


if __name__ == "__main__":
    main()
