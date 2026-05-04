"""
Импорт пользователей и платежей из Excel (бот Open21 VPN / open21vpn_bot) в БД Lead Tracker.

Формат файла такой же, как у gamer_import.xlsx (лист users + те же листы платежей).

Платежи с суммой ровно 10.00 (триал) не импортируются.

Запуск
------

На сервере с Docker (файл в корне репозитория на хосте монтируется в контейнер как /app/repo):

  docker compose exec api uv run python scripts/open21_import.py /app/repo/open21_import.xlsx
  docker compose exec api uv run python scripts/open21_import.py --dry-run /app/repo/open21_import.xlsx

Локально из корня репозитория (нужны .env и доступ к Postgres):

  uv run python scripts/open21_import.py ./open21_import.xlsx
  uv run python scripts/open21_import.py --dry-run ./open21_import.xlsx

Без аргумента пути берётся ./open21_import.xlsx или /app/repo/open21_import.xlsx в Docker.

Лист users: user_id, create_user, in_panel, is_connect, ref, stamp.
  trial_at = create_user только если in_panel=TRUE; connected_at = create_user только если is_connect=TRUE.
  source: если ref задан — строка "referral", иначе значение колонки stamp.
Листы платежей: payments_wata_sbp, payments_wata_card, payments_stars, payments_cryptobot,
  payments_sbp, payments_cards, payments_fk_sbp — только строки со статусом confirmed или paid;
  строки с amount = 10.00 пропускаются (триал).

Повторный запуск: пользователи с тем же (user_id, bot_id) не дублируются (ON CONFLICT DO NOTHING).
Платежи без уникального ключа в БД при повторном запуске могут продублироваться.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
import uuid
from collections.abc import Iterator
from datetime import datetime
from decimal import Decimal
from pathlib import Path

import pandas as pd
from loguru import logger
from sqlalchemy import bindparam, select
from sqlalchemy.dialects.postgresql import insert as pg_insert

_ROOT = Path(__file__).resolve().parent.parent
_SRC = _ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from database.core import SessionFactory  # noqa: E402
from database.models import Payment, User  # noqa: E402

BOT_ID = 8159162956
BOT_NAME = "open21vpn_bot"

# Триал в выгрузке — не переносим в Lead Tracker как платёж
SKIP_TRIAL_AMOUNT = Decimal("10.00")

PAYMENT_SHEETS = (
    "payments_wata_sbp",
    "payments_wata_card",
    "payments_stars",
    "payments_cryptobot",
    "payments_sbp",
    "payments_cards",
    "payments_fk_sbp",
)


def _default_xlsx_path() -> str:
    mounted = Path("/app/repo/open21_import.xlsx")
    if mounted.parent.is_dir():
        return str(mounted)
    return str(_ROOT / "open21_import.xlsx")


def _norm_key(name: object) -> str:
    return str(name).strip().lower().replace(" ", "_")


def _col_map(df: pd.DataFrame) -> dict[str, str]:
    return {_norm_key(c): str(c) for c in df.columns}


def _col(df: pd.DataFrame, *candidates: str) -> str | None:
    mp = _col_map(df)
    for cand in candidates:
        k = _norm_key(cand)
        if k in mp:
            return mp[k]
    return None


def _status_column(df: pd.DataFrame) -> str | None:
    status_c = _col(df, "status", "Status", "state", "State")
    if status_c:
        return status_c
    for k, orig in _col_map(df).items():
        if "status" in k:
            return orig
    return None


def _parse_dt(val: object) -> datetime | None:
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return None
    if isinstance(val, datetime):
        return val
    ts = pd.Timestamp(val)
    if pd.isna(ts):
        return None
    if ts.tzinfo is not None:
        ts = ts.tz_convert(None)
    return ts.to_pydatetime()


def _parse_int(val: object) -> int | None:
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return None
    try:
        return int(Decimal(str(val)))
    except (ValueError, ArithmeticError):
        try:
            return int(float(val))
        except (ValueError, TypeError):
            return None


def _parse_amount(val: object) -> Decimal | None:
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return None
    try:
        return Decimal(str(val)).quantize(Decimal("0.01"))
    except (ArithmeticError, ValueError, TypeError):
        return None


def _truthy_excel(val: object) -> bool:
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return False
    if isinstance(val, bool):
        return val
    if isinstance(val, (int, float)) and not isinstance(val, bool):
        return val != 0
    s = str(val).strip().lower()
    return s in ("true", "1", "yes", "да", "t")


def _user_source(row: pd.Series, df: pd.DataFrame) -> str | None:
    ref_c = _col(df, "ref")
    stamp_c = _col(df, "stamp")
    ref_val = row.get(ref_c) if ref_c else None
    if ref_val is not None and not (isinstance(ref_val, float) and pd.isna(ref_val)):
        if str(ref_val).strip():
            return "referral"
    if stamp_c:
        v = row.get(stamp_c)
        if v is None or (isinstance(v, float) and pd.isna(v)):
            return None
        s = str(v).strip()
        return s or None
    return None


def _status_ok(val: object) -> bool:
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return False
    s = str(val).strip().lower()
    return s in ("confirmed", "paid")


def _batched[T](items: list[T], size: int) -> Iterator[list[T]]:
    for i in range(0, len(items), size):
        yield items[i : i + size]


def load_users_rows(xl: pd.ExcelFile) -> list[dict]:
    if "users" not in xl.sheet_names:
        raise ValueError("В файле нет листа users")
    df = pd.read_excel(xl, sheet_name="users", engine="openpyxl")
    uid_c = _col(df, "user_id")
    if not uid_c:
        raise ValueError("На листе users не найдена колонка user_id")

    create_c = _col(df, "create_user")
    if not create_c:
        raise ValueError("На листе users не найдена колонка create_user")

    in_panel_c = _col(df, "in_panel")
    is_connect_c = _col(df, "is_connect")

    now = datetime.now()
    rows: list[dict] = []
    for _, row in df.iterrows():
        uid = _parse_int(row.get(uid_c))
        if uid is None:
            continue
        created = _parse_dt(row.get(create_c))
        if created is None:
            logger.warning("Пропуск user_id={}: нет даты create_user", uid)
            continue
        trial_at = created if (in_panel_c and _truthy_excel(row.get(in_panel_c))) else None
        connected_at = (
            created if (is_connect_c and _truthy_excel(row.get(is_connect_c))) else None
        )
        rows.append(
            {
                "id": uuid.uuid4(),
                "user_id": uid,
                "username": None,
                "full_name": None,
                "source": _user_source(row, df),
                "created_at": created,
                "bot_id": BOT_ID,
                "bot_name": BOT_NAME,
                "updated_at": now,
                "trial_at": trial_at,
                "connected_at": connected_at,
            }
        )

    by_uid: dict[int, dict] = {}
    for r in rows:
        by_uid[r["user_id"]] = r
    out = list(by_uid.values())
    logger.info("users: строк в Excel после фильтра и дедупа по user_id: {}", len(out))
    return out


def load_payment_rows(xl: pd.ExcelFile, sheet: str) -> list[dict]:
    if sheet not in xl.sheet_names:
        logger.warning("Лист {!r} отсутствует, пропуск", sheet)
        return []

    df = pd.read_excel(xl, sheet_name=sheet, engine="openpyxl")
    uid_c = _col(df, "user_id")
    amt_c = _col(df, "amount", "Amount")
    time_c = _col(df, "time_created", "Time Created", "time created")
    status_c = _status_column(df)

    if not uid_c or not amt_c or not time_c:
        logger.warning(
            "Лист {!r}: не хватает колонок (нужны user_id, Amount, Time Created). Пропуск",
            sheet,
        )
        return []

    if not status_c:
        logger.warning(
            "Лист {!r}: нет колонки статуса — платежи с листа не импортируются",
            sheet,
        )
        return []

    out: list[dict] = []
    skipped_trial = 0
    for _, row in df.iterrows():
        if not _status_ok(row.get(status_c)):
            continue
        uid = _parse_int(row.get(uid_c))
        amt = _parse_amount(row.get(amt_c))
        ts = _parse_dt(row.get(time_c))
        if uid is None or amt is None or ts is None:
            continue
        if amt == SKIP_TRIAL_AMOUNT:
            skipped_trial += 1
            continue
        out.append(
            {
                "id": uuid.uuid4(),
                "user_id": uid,
                "bot_id": BOT_ID,
                "amount": amt,
                "created_at": ts,
            }
        )
    logger.info(
        "payments {!r}: отобрано строк: {} (пропущено триал {}₽: {})",
        sheet,
        len(out),
        SKIP_TRIAL_AMOUNT,
        skipped_trial,
    )
    return out


async def import_users(session, rows: list[dict], chunk: int = 2000) -> int:
    if not rows:
        return 0

    stmt = (
        pg_insert(User)
        .values(
            id=bindparam("id"),
            user_id=bindparam("user_id"),
            username=bindparam("username"),
            full_name=bindparam("full_name"),
            source=bindparam("source"),
            created_at=bindparam("created_at"),
            bot_id=bindparam("bot_id"),
            bot_name=bindparam("bot_name"),
            updated_at=bindparam("updated_at"),
            trial_at=bindparam("trial_at"),
            connected_at=bindparam("connected_at"),
        )
        .on_conflict_do_nothing(constraint="uq_users_telegram_bot")
    )

    total = 0
    for batch in _batched(rows, chunk):
        await session.execute(stmt, batch)
        total += len(batch)
        await session.commit()
        logger.info("users: отправлено в БД {} / {}", total, len(rows))
    return total


async def import_payments(session, rows: list[dict], chunk: int = 2000) -> int:
    if not rows:
        return 0

    stmt = insert_payment_stmt()

    inserted = 0
    for batch in _batched(rows, chunk):
        uids = {r["user_id"] for r in batch}
        res = await session.execute(
            select(User.user_id).where(User.user_id.in_(uids), User.bot_id == BOT_ID)
        )
        existing = {r[0] for r in res.all()}

        to_write = [r for r in batch if r["user_id"] in existing]
        skipped = len(batch) - len(to_write)
        if skipped:
            logger.debug("Пакет: пропущено платежей (нет user в БД): {}", skipped)

        if to_write:
            await session.execute(stmt, to_write)
            inserted += len(to_write)
        await session.commit()

    logger.info("payments: записано строк: {}", inserted)
    return inserted


def insert_payment_stmt():
    return pg_insert(Payment).values(
        id=bindparam("id"),
        user_id=bindparam("user_id"),
        bot_id=bindparam("bot_id"),
        amount=bindparam("amount"),
        created_at=bindparam("created_at"),
    )


async def main_async(xlsx: Path) -> None:
    if not xlsx.is_file():
        raise SystemExit(f"Файл не найден: {xlsx}")

    logger.info("Читаю {}", xlsx.resolve())
    xl = pd.ExcelFile(xlsx, engine="openpyxl")
    user_rows = load_users_rows(xl)

    pay_rows: list[dict] = []
    for sh in PAYMENT_SHEETS:
        pay_rows.extend(load_payment_rows(xl, sh))
    logger.info("Всего строк платежей (после фильтра, без триала {}₽): {}", SKIP_TRIAL_AMOUNT, len(pay_rows))

    async with SessionFactory() as session:
        await import_users(session, user_rows)
        await import_payments(session, pay_rows)

    logger.info("Готово.")


def main() -> None:
    p = argparse.ArgumentParser(description="Импорт users + payments из Excel (Open21 VPN / open21vpn_bot).")
    p.add_argument(
        "xlsx",
        nargs="?",
        default=_default_xlsx_path(),
        help="Путь к .xlsx (по умолчанию ./open21_import.xlsx или /app/repo/open21_import.xlsx в Docker)",
    )
    p.add_argument("--dry-run", action="store_true", help="Только прочитать Excel и вывести счётчики")
    args = p.parse_args()
    path = Path(args.xlsx)
    if args.dry_run:
        if not path.is_file():
            raise SystemExit(f"Файл не найден: {path}")
        xl = pd.ExcelFile(path, engine="openpyxl")
        u = load_users_rows(xl)
        n = 0
        for sh in PAYMENT_SHEETS:
            n += len(load_payment_rows(xl, sh))
        logger.info("DRY-RUN: users {}, платежей всего (без триала {}₽): {}", len(u), SKIP_TRIAL_AMOUNT, n)
        return
    asyncio.run(main_async(path))


if __name__ == "__main__":
    main()
