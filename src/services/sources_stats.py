from __future__ import annotations

from datetime import datetime
from typing import Any

from database.models import Payment, User
from sqlalchemy import case, func, select


def _apply_user_filters(
    stmt,
    date_from: datetime | None,
    date_to: datetime | None,
    bot_id: int | None,
):
    if date_from is not None:
        stmt = stmt.where(User.created_at >= date_from)
    if date_to is not None:
        stmt = stmt.where(User.created_at <= date_to)
    if bot_id is not None:
        stmt = stmt.where(User.bot_id == bot_id)
    return stmt


def _apply_payment_filters(
    stmt,
    date_from: datetime | None,
    date_to: datetime | None,
    bot_id: int | None,
):
    """Фильтр по дате самого платежа (когда деньги пришли в трекер)."""
    if date_from is not None:
        stmt = stmt.where(Payment.created_at >= date_from)
    if date_to is not None:
        stmt = stmt.where(Payment.created_at <= date_to)
    if bot_id is not None:
        stmt = stmt.where(Payment.bot_id == bot_id)
    return stmt


def get_sources_stats(
    session,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    bot_id: int | None = None,
) -> list[dict[str, Any]]:
    user_stmt = (
        select(
            func.coalesce(User.source, "(Без источника)").label("source_name"),
            func.count(User.id).label("total_users"),
            func.sum(case((User.trial_at.isnot(None), 1), else_=0)).label("trial_users"),
            func.sum(
                case((User.connected_at.isnot(None), 1), else_=0)
            ).label("connected_users"),
        )
        .select_from(User)
        .group_by(func.coalesce(User.source, "(Без источника)"))
        .order_by(func.count(User.id).desc())
    )
    user_stmt = _apply_user_filters(user_stmt, date_from, date_to, bot_id)
    user_rows = session.execute(user_stmt).all()

    pay_stmt = (
        select(
            func.coalesce(User.source, "(Без источника)").label("source_name"),
            func.count(Payment.id).label("total_payments"),
            func.coalesce(func.sum(Payment.amount), 0).label("total_revenue"),
        )
        .select_from(Payment)
        .join(
            User,
            (User.user_id == Payment.user_id) & (User.bot_id == Payment.bot_id),
        )
        .group_by(func.coalesce(User.source, "(Без источника)"))
    )
    pay_stmt = _apply_payment_filters(pay_stmt, date_from, date_to, bot_id)
    pay_map = {r.source_name: r for r in session.execute(pay_stmt).all()}

    paid_inner = (
        select(
            func.coalesce(User.source, "(Без источника)").label("source_name"),
            Payment.user_id,
            Payment.bot_id,
        )
        .select_from(Payment)
        .join(
            User,
            (User.user_id == Payment.user_id) & (User.bot_id == Payment.bot_id),
        )
        .distinct()
    )
    # Когорта по регистрации; платёж без ограничения по дате — «оплатили когда-либо».
    paid_inner = _apply_user_filters(paid_inner, date_from, date_to, bot_id)
    paid_sub = paid_inner.subquery()
    paid_stmt = (
        select(paid_sub.c.source_name, func.count().label("paid_users"))
        .select_from(paid_sub)
        .group_by(paid_sub.c.source_name)
    )
    paid_map = {
        r.source_name: int(r.paid_users or 0)
        for r in session.execute(paid_stmt).all()
    }

    user_by_src = {r.source_name: r for r in user_rows}
    all_sources = set(user_by_src) | set(pay_map) | set(paid_map)

    def _sort_key(name: str) -> tuple[int, str]:
        urow = user_by_src.get(name)
        n = int(urow.total_users or 0) if urow else 0
        return (-n, name)

    out: list[dict[str, Any]] = []
    for src in sorted(all_sources, key=_sort_key):
        ur = user_by_src.get(src)
        pr = pay_map.get(src)
        out.append(
            {
                "source_name": src,
                "total_users": int(ur.total_users or 0) if ur else 0,
                "trial_users": int(ur.trial_users or 0) if ur else 0,
                "connected_users": int(ur.connected_users or 0) if ur else 0,
                "paid_users": paid_map.get(src, 0),
                "total_payments": int(pr.total_payments) if pr else 0,
                "total_revenue": float(pr.total_revenue) if pr else 0.0,
            }
        )
    return out
