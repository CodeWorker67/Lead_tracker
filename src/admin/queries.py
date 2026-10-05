import streamlit as st
from database.models import User
from sqlalchemy import func, select
from sqlalchemy.orm import Session


def get_distinct_bots(session: Session) -> list[tuple[int, str | None]]:
    """bot_id и отображаемое имя (последнее непустое bot_name)."""
    stmt = (
        select(User.bot_id, func.max(User.bot_name))
        .group_by(User.bot_id)
        .order_by(User.bot_id)
    )
    rows = session.execute(stmt).all()
    return [(int(r[0]), r[1]) for r in rows]


def _bot_label(bot_id: int, bot_name: str | None) -> str:
    name_part = (bot_name or "").strip()
    return f"{name_part} (id {bot_id})" if name_part else f"Бот {bot_id}"


def render_bot_filter(
    session: Session,
    column,
    allowed_bot_id: int | None = None,
) -> int | None:
    """
    Селектор бота. Возвращает bot_id или None = все боты.
    Если allowed_bot_id задан — только этот бот, без выбора «Все боты».
    """
    if allowed_bot_id is not None:
        rows = get_distinct_bots(session)
        match = next((r for r in rows if r[0] == allowed_bot_id), None)
        label = _bot_label(allowed_bot_id, match[1] if match else None)
        with column:
            st.selectbox("Бот", [label], index=0, disabled=True)
        return allowed_bot_id

    rows = get_distinct_bots(session)
    if not rows:
        return None

    labels = [_bot_label(bot_id, bot_name) for bot_id, bot_name in rows]

    with column:
        options = ["Все боты"] + labels
        choice = st.selectbox("Бот", options, index=0)
        if choice == "Все боты":
            return None
        idx = options.index(choice) - 1
        return rows[idx][0]
