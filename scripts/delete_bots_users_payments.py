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


async def _delete_table_in_batches(
    session,
    model,
    bot_ids: tuple[int, ...],
    batch_size: int,
    label: str,
) -> int:
    """Удаление пакетами по PK, commit после каждого пакета — меньше блокировок и виден прогресс."""
    total = 0
    while True:
        ids_sq = (
            select(model.id)
            .where(model.bot_id.in_(bot_ids))
            .limit(batch_size)
        )
        stmt = delete(model).where(model.id.in_(ids_sq))
        result = await session.execute(stmt)
        n = result.rowcount
        if n is None or n <= 0:
            await session.commit()
            break
        total += n
        await session.commit()
        logger.info("{}: пакет −{} строк, всего удалено {}", label, n, total)
    return total


async def run_delete(bot_ids: tuple[int, ...], batch_size: int) -> None:
    async with SessionFactory() as session:
        n_pay_before = await _count(session, Payment, bot_ids)
        n_user_before = await _count(session, User, bot_ids)
        logger.info(
            "Удаление: bot_id in {}. Сейчас в БД: payments={}, users={}",
            list(bot_ids),
            n_pay_before,
            n_user_before,
        )
        logger.info(
            "Пакеты по {} строк; между пакетами commit — на ~140k пользователей "
            "обычно 1–5+ минут, это не зависание.",
            batch_size,
        )

        logger.info("Сначала payments…")
        deleted_pay = await _delete_table_in_batches(
            session, Payment, bot_ids, batch_size, "payments"
        )
        logger.info("Затем users…")
        deleted_user = await _delete_table_in_batches(
            session, User, bot_ids, batch_size, "users"
        )

        logger.info(
            "Готово. Итого удалено payments={}, users={}.",
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
    p.add_argument(
        "--batch-size",
        type=int,
        default=5000,
        metavar="N",
        help="Размер пакета DELETE (по умолчанию 5000)",
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

    if args.batch_size < 1:
        raise SystemExit("--batch-size должен быть >= 1")

    asyncio.run(run_delete(bot_ids, args.batch_size))


if __name__ == "__main__":
    main()
