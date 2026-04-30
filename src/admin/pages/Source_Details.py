import sys
from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

src_path = Path(__file__).parent.parent.parent
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from database.models import Payment, User
from sqlalchemy import select, tuple_

from admin.auth import logout, require_auth
from admin.db import get_session
from admin.queries import render_bot_filter

st.set_page_config(
    page_title="Детали источника - Lead Tracker",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown(
    """
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
""",
    unsafe_allow_html=True,
)

st.markdown(
    """
<style>
    .main { padding-top: 2rem; }
    .stMetric { background-color: transparent; padding: 10px 0; }
    .stMetric label { font-size: 0.95rem; color: #555; font-weight: 600; }
    .stMetric [data-testid="stMetricValue"] {
        font-size: 2.2rem; font-weight: 700; color: #1f77b4;
    }
    h1 { color: #1f77b4; font-weight: 700; }
    h2, h3 { color: #31333F; font-weight: 600; }
    .dataframe { font-size: 0.9rem; }
    [data-testid="stSidebar"][aria-expanded="true"] { display: none; }
    section[data-testid="stSidebar"] { display: none; }
    .icon-header {
        display: inline-flex; align-items: center; gap: 12px; color: #1f77b4;
    }
    .metric-icon { font-size: 1.5rem; color: #1f77b4; margin-right: 8px; }
</style>
""",
    unsafe_allow_html=True,
)


def get_users_with_payments(
    session,
    source_name: str,
    date_from: datetime | None,
    date_to: datetime | None,
    bot_id: int | None = None,
) -> list[dict[str, Any]]:
    if source_name == "(Без источника)":
        stmt = select(User).where(User.source.is_(None))
    else:
        stmt = select(User).where(User.source == source_name)

    if date_from:
        stmt = stmt.where(User.created_at >= date_from)
    if date_to:
        stmt = stmt.where(User.created_at <= date_to)
    if bot_id is not None:
        stmt = stmt.where(User.bot_id == bot_id)

    stmt = stmt.order_by(User.created_at.desc())
    users = list(session.execute(stmt).scalars())

    if not users:
        return []

    keys = [(u.user_id, u.bot_id) for u in users]
    pay_stmt = select(Payment).where(tuple_(Payment.user_id, Payment.bot_id).in_(keys))
    payments = list(session.execute(pay_stmt).scalars())

    payments_by_key: dict[tuple[int, int], list[Payment]] = defaultdict(list)
    for p in payments:
        payments_by_key[(p.user_id, p.bot_id)].append(p)

    out = []
    for user in users:
        ups = payments_by_key.get((user.user_id, user.bot_id), [])
        out.append(
            {
                "dashboard_id": user.id,
                "telegram_user_id": user.user_id,
                "bot_id": user.bot_id,
                "username": user.username,
                "full_name": user.full_name,
                "created_at": user.created_at,
                "trial_at": user.trial_at,
                "connected_at": user.connected_at,
                "payments": [
                    {
                        "id": p.id,
                        "amount": float(p.amount),
                        "created_at": p.created_at,
                    }
                    for p in ups
                ],
            }
        )
    return out


def create_users_timeline_chart(users_data: list[dict[str, Any]]) -> go.Figure:
    users_by_date: dict[date, int] = {}
    trial_by_date: dict[date, int] = {}
    conn_by_date: dict[date, int] = {}

    for user in users_data:
        d = user["created_at"].date()
        users_by_date[d] = users_by_date.get(d, 0) + 1
        if user["trial_at"]:
            t = user["trial_at"].date()
            trial_by_date[t] = trial_by_date.get(t, 0) + 1
        if user["connected_at"]:
            c = user["connected_at"].date()
            conn_by_date[c] = conn_by_date.get(c, 0) + 1

    if not users_by_date:
        fig = go.Figure()
        fig.add_annotation(
            text="Нет данных",
            xref="paper",
            yref="paper",
            x=0.5,
            y=0.5,
            showarrow=False,
            font={"size": 16, "color": "gray"},
        )
        fig.update_layout(height=400, margin={"l": 0, "r": 0, "t": 20, "b": 0})
        return fig

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=sorted(users_by_date.keys()),
            y=[users_by_date[d] for d in sorted(users_by_date.keys())],
            mode="lines+markers",
            name="Новые пользователи",
            line={"color": "#1f77b4", "width": 3},
        )
    )
    if trial_by_date:
        fig.add_trace(
            go.Scatter(
                x=sorted(trial_by_date.keys()),
                y=[trial_by_date[d] for d in sorted(trial_by_date.keys())],
                mode="lines+markers",
                name="Триал (по дате события)",
                line={"color": "#9467bd", "width": 2},
            )
        )
    if conn_by_date:
        fig.add_trace(
            go.Scatter(
                x=sorted(conn_by_date.keys()),
                y=[conn_by_date[d] for d in sorted(conn_by_date.keys())],
                mode="lines+markers",
                name="Подключились",
                line={"color": "#2ca02c", "width": 2},
            )
        )

    fig.update_layout(
        height=400,
        margin={"l": 0, "r": 0, "t": 20, "b": 0},
        xaxis_title="Дата",
        yaxis_title="Количество",
        hovermode="x unified",
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
    )
    return fig


def create_payments_timeline_chart(users_data: list[dict[str, Any]]) -> go.Figure:
    payments_by_date: dict[date, int] = {}
    revenue_by_date: dict[date, float] = {}

    for user in users_data:
        for payment in user["payments"]:
            dk = payment["created_at"].date()
            payments_by_date[dk] = payments_by_date.get(dk, 0) + 1
            revenue_by_date[dk] = revenue_by_date.get(dk, 0.0) + payment["amount"]

    if not payments_by_date:
        fig = go.Figure()
        fig.add_annotation(
            text="Нет данных о платежах",
            xref="paper",
            yref="paper",
            x=0.5,
            y=0.5,
            showarrow=False,
            font={"size": 16, "color": "gray"},
        )
        fig.update_layout(height=400, margin={"l": 0, "r": 0, "t": 20, "b": 0})
        return fig

    dates = sorted(payments_by_date.keys())
    df = pd.DataFrame(
        [
            {
                "date": d,
                "payments": payments_by_date[d],
                "revenue": revenue_by_date[d],
            }
            for d in dates
        ]
    )

    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            x=df["date"],
            y=df["revenue"],
            name="Выручка",
            marker={"color": df["revenue"], "colorscale": "Greens", "showscale": False},
        )
    )
    fig.add_trace(
        go.Scatter(
            x=df["date"],
            y=df["payments"],
            name="Платежи",
            yaxis="y2",
            mode="lines+markers",
            line={"color": "#ff7f0e", "width": 3},
        )
    )
    fig.update_layout(
        height=400,
        margin={"l": 0, "r": 0, "t": 20, "b": 0},
        xaxis_title="Дата",
        yaxis={"title": "Выручка (₽)"},
        yaxis2={
            "title": "Количество платежей",
            "overlaying": "y",
            "side": "right",
        },
        hovermode="x unified",
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
    )
    return fig


def aggregate_daily_stats(users_data: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_date: dict[date, dict[str, Any]] = defaultdict(
        lambda: {
            "new_users": 0,
            "trial": 0,
            "connected": 0,
            "payments": 0,
            "revenue": 0.0,
        }
    )

    for user in users_data:
        by_date[user["created_at"].date()]["new_users"] += 1
        if user["trial_at"]:
            by_date[user["trial_at"].date()]["trial"] += 1
        if user["connected_at"]:
            by_date[user["connected_at"].date()]["connected"] += 1
        for payment in user["payments"]:
            pd = payment["created_at"].date()
            by_date[pd]["payments"] += 1
            by_date[pd]["revenue"] += payment["amount"]

    return [
        {
            "date": d,
            "new_users": by_date[d]["new_users"],
            "trial": by_date[d]["trial"],
            "connected": by_date[d]["connected"],
            "payments": by_date[d]["payments"],
            "revenue": by_date[d]["revenue"],
        }
        for d in sorted(by_date.keys())
    ]


@require_auth
def main():
    if "selected_source" not in st.session_state:
        st.warning("Выберите источник на главной странице")
        if st.button("На главную", type="primary"):
            st.switch_page("Home.py")
        st.stop()

    source_name = st.session_state["selected_source"]

    col1, col2, col3 = st.columns([3, 1, 1])
    with col1:
        st.markdown(
            f'<h1 class="icon-header"><i class="fas fa-chart-line"></i> {source_name}</h1>',
            unsafe_allow_html=True,
        )
        st.markdown("### Детальная аналитика источника")
    with col2:
        st.markdown("")
        if st.button("На главную", type="primary", use_container_width=True):
            st.switch_page("Home.py")
    with col3:
        st.markdown("")
        if st.button("Выход", type="secondary", use_container_width=True):
            logout()

    st.markdown(
        '<h3 class="icon-header"><i class="fas fa-filter"></i> Фильтры</h3>',
        unsafe_allow_html=True,
    )
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        filter_option = st.selectbox(
            "Период времени",
            [
                "Последние 7 дней",
                "Последние 30 дней",
                "Все время",
                "Конкретный день",
                "Произвольный период",
            ],
            index=2,
        )

    if filter_option == "Последние 7 дней":
        date_from = datetime.now() - timedelta(days=7)
        date_to = datetime.now()
    elif filter_option == "Последние 30 дней":
        date_from = datetime.now() - timedelta(days=30)
        date_to = datetime.now()
    elif filter_option == "Конкретный день":
        with col2:
            sd = st.date_input("Дата", value=date.today())
        date_from = datetime.combine(sd, datetime.min.time())
        date_to = datetime.combine(sd, datetime.max.time())
    elif filter_option == "Произвольный период":
        with col2:
            df_i = st.date_input("С", value=datetime.now() - timedelta(days=30))
        with col3:
            dt_i = st.date_input("По", value=datetime.now())
        date_from = datetime.combine(df_i, datetime.min.time())
        date_to = datetime.combine(dt_i, datetime.max.time())
    else:
        date_from = None
        date_to = None

    session = get_session()
    try:
        selected_bot_id = render_bot_filter(session, col4)
    finally:
        session.close()

    show_source_details(source_name, date_from, date_to, selected_bot_id)


def show_source_details(
    source_name: str,
    date_from: datetime | None,
    date_to: datetime | None,
    bot_id: int | None = None,
):
    session = get_session()
    try:
        users_data = get_users_with_payments(
            session, source_name, date_from, date_to, bot_id
        )

        if not users_data:
            st.info("Нет пользователей за выбранные фильтры.")
            return

        total_users = len(users_data)
        trial_users = sum(1 for u in users_data if u["trial_at"])
        conn_users = sum(1 for u in users_data if u["connected_at"])
        pay_count = sum(len(u["payments"]) for u in users_data)
        total_revenue = sum(
            sum(p["amount"] for p in u["payments"]) for u in users_data
        )

        tr = (trial_users / total_users * 100) if total_users else 0
        cr = (conn_users / total_users * 100) if total_users else 0
        conv = (pay_count / total_users * 100) if total_users else 0
        avg_rev = total_revenue / pay_count if pay_count else 0

        c1, c2, c3, c4, c5 = st.columns(5)
        with c1:
            st.markdown('<i class="fas fa-users metric-icon"></i>', unsafe_allow_html=True)
            st.metric("Пользователи", f"{total_users:,}")
        with c2:
            st.markdown(
                '<i class="fas fa-flask metric-icon"></i>', unsafe_allow_html=True
            )
            st.metric("Триал", f"{trial_users:,}", delta=f"{tr:.1f}% охват")
        with c3:
            st.markdown(
                '<i class="fas fa-plug metric-icon"></i>', unsafe_allow_html=True
            )
            st.metric("Подключились", f"{conn_users:,}", delta=f"{cr:.1f}% охват")
        with c4:
            st.markdown(
                '<i class="fas fa-credit-card metric-icon"></i>', unsafe_allow_html=True
            )
            st.metric("Платежи", f"{pay_count:,}", delta=f"{conv:.1f}% конверсия")
        with c5:
            st.markdown(
                '<i class="fas fa-ruble-sign metric-icon"></i>', unsafe_allow_html=True
            )
            st.metric("Выручка", f"₽{total_revenue:,.0f}", delta=f"₽{avg_rev:.0f} средний")

        st.markdown("---")
        tab1, tab2 = st.tabs(
            ["Пользователи / триал / подключения", "Платежи и выручка"]
        )
        with tab1:
            st.plotly_chart(create_users_timeline_chart(users_data), width="stretch")
        with tab2:
            st.plotly_chart(create_payments_timeline_chart(users_data), width="stretch")

        st.markdown("---")
        st.markdown(
            '<h4 class="icon-header"><i class="fas fa-table"></i> По дням</h4>',
            unsafe_allow_html=True,
        )
        daily = aggregate_daily_stats(users_data)
        if daily:
            df_d = pd.DataFrame(daily)
            df_d.columns = [
                "Дата",
                "Новые юзеры",
                "Триал",
                "Подключились",
                "Платежи",
                "Выручка ₽",
            ]
            st.dataframe(
                df_d.style.format(
                    {
                        "Новые юзеры": "{:,.0f}",
                        "Триал": "{:,.0f}",
                        "Подключились": "{:,.0f}",
                        "Платежи": "{:,.0f}",
                        "Выручка ₽": "₽{:,.0f}",
                    }
                ),
                width="stretch",
                hide_index=True,
            )
        else:
            st.info("Нет данных по дням")

        st.markdown("---")
        st.markdown(
            '<h3 class="icon-header"><i class="fas fa-users"></i> Пользователи</h3>',
            unsafe_allow_html=True,
        )

        rows = []
        for u in users_data:
            rev = sum(p["amount"] for p in u["payments"])
            rows.append(
                {
                    "ID (дашборд)": str(u["dashboard_id"]),
                    "Telegram ID": u["telegram_user_id"],
                    "Бот": u["bot_id"],
                    "Username": u["username"] or "-",
                    "ФИО": u["full_name"] or "-",
                    "Создан": u["created_at"].strftime("%Y-%m-%d %H:%M"),
                    "Триал": u["trial_at"].strftime("%Y-%m-%d %H:%M")
                    if u["trial_at"]
                    else "-",
                    "Подключился": u["connected_at"].strftime("%Y-%m-%d %H:%M")
                    if u["connected_at"]
                    else "-",
                    "Платежей": len(u["payments"]),
                    "Выручка ₽": rev,
                }
            )
        st.dataframe(
            pd.DataFrame(rows)
            .style.format({"Платежей": "{:,.0f}", "Выручка ₽": "₽{:,.0f}"}),
            width="stretch",
            hide_index=True,
        )
    finally:
        session.close()


if __name__ == "__main__":
    main()
