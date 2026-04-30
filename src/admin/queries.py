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


def render_bot_filter(session: Session, column) -> int | None:
    """Селектор бота. Возвращает bot_id или None = все боты."""
    rows = get_distinct_bots(session)
    if not rows:
        return None

    labels: list[str] = []
    for bot_id, bot_name in rows:
        name_part = (bot_name or "").strip()
        labels.append(f"{name_part} (id {bot_id})" if name_part else f"Бот {bot_id}")

    with column:
        options = ["Все боты"] + labels
        choice = st.selectbox("Бот", options, index=0)
        if choice == "Все боты":
            return None
        idx = options.index(choice) - 1
        return rows[idx][0]
