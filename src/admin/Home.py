import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

src_path = Path(__file__).parent.parent
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from database.models import Payment, User
from sqlalchemy import case, func, select

from admin.auth import logout, require_auth
from admin.db import get_session
from admin.queries import render_bot_filter

st.set_page_config(
    page_title="Админ панель - Lead Tracker",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown(
    """
<style>
    [data-testid="stSidebar"] { display: none; }
</style>
""",
    unsafe_allow_html=True,
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
    .stMetric [data-testid="stMetricDelta"] { font-size: 0.85rem; }
    h1 { color: #1f77b4; font-weight: 700; margin-bottom: 0.5rem; }
    h2, h3 { color: #31333F; font-weight: 600; }
    .dataframe { font-size: 0.9rem; }
    .icon-header {
        display: inline-flex; align-items: center; gap: 12px;
        color: #1f77b4;
    }
    .metric-icon { font-size: 1.5rem; color: #1f77b4; margin-right: 8px; }
    .stButton>button {
        border-radius: 8px; font-weight: 600; transition: all 0.3s ease;
    }
    .stButton>button:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 12px rgba(0,0,0,0.15);
    }
</style>
""",
    unsafe_allow_html=True,
)


def _apply_user_filters(stmt, date_from: datetime | None, date_to: datetime | None, bot_id: int | None):
    if date_from is not None:
        stmt = stmt.where(User.created_at >= date_from)
    if date_to is not None:
        stmt = stmt.where(User.created_at <= date_to)
    if bot_id is not None:
        stmt = stmt.where(User.bot_id == bot_id)
    return stmt


def _apply_payment_filters(stmt, date_from: datetime | None, date_to: datetime | None, bot_id: int | None):
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


def create_users_chart(sources_data: list[dict[str, Any]]) -> go.Figure:
    df = pd.DataFrame(sources_data).sort_values("total_users", ascending=True)
    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            y=df["source_name"],
            x=df["total_users"],
            orientation="h",
            marker={
                "color": df["total_users"],
                "colorscale": "Blues",
                "showscale": False,
            },
            text=df["total_users"],
            textposition="outside",
            hovertemplate="<b>%{y}</b><br>Пользователи: %{x:,.0f}<extra></extra>",
        )
    )
    fig.update_layout(
        height=max(300, len(sources_data) * 50),
        margin={"l": 0, "r": 0, "t": 0, "b": 0},
        xaxis_title="Пользователи",
        yaxis_title="",
        hovermode="y",
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
    )
    fig.update_xaxes(showgrid=True, gridcolor="lightgray")
    return fig


def create_revenue_chart(sources_data: list[dict[str, Any]]) -> go.Figure:
    df = pd.DataFrame(sources_data)
    df = df[df["total_revenue"] > 0]
    if df.empty:
        fig = go.Figure()
        fig.add_annotation(
            text="Нет данных о выручке",
            xref="paper",
            yref="paper",
            x=0.5,
            y=0.5,
            showarrow=False,
            font={"size": 16, "color": "gray"},
        )
        fig.update_layout(height=300, margin={"l": 0, "r": 0, "t": 0, "b": 0})
        return fig

    fig = go.Figure(
        data=[
            go.Pie(
                labels=df["source_name"],
                values=df["total_revenue"],
                hole=0.4,
                hovertemplate="<b>%{label}</b><br>Выручка: ₽%{value:,.0f}<br>%{percent}<extra></extra>",
                textposition="inside",
                textinfo="label+percent",
            )
        ]
    )
    fig.update_layout(
        height=300,
        margin={"l": 0, "r": 0, "t": 0, "b": 0},
        showlegend=False,
    )
    return fig


@require_auth
def main():
    col_title, col_logout = st.columns([6, 1])
    with col_title:
        st.markdown(
            '<h1 class="icon-header"><i class="fas fa-chart-line"></i> Панель управления Lead Tracker</h1>',
            unsafe_allow_html=True,
        )
        st.markdown("### Обзор по источникам трафика")
    with col_logout:
        st.markdown("")
        st.markdown("")
        if st.button("Выход", type="secondary"):
            logout()
    st.markdown("")

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
            selected_date = st.date_input("Дата", value=date.today())
        date_from = datetime.combine(selected_date, datetime.min.time())
        date_to = datetime.combine(selected_date, datetime.max.time())
    elif filter_option == "Произвольный период":
        with col2:
            date_from_input = st.date_input(
                "С", value=datetime.now() - timedelta(days=30)
            )
        with col3:
            date_to_input = st.date_input("По", value=datetime.now())
        date_from = datetime.combine(date_from_input, datetime.min.time())
        date_to = datetime.combine(date_to_input, datetime.max.time())
    else:
        date_from = None
        date_to = None

    session = get_session()
    try:
        selected_bot_id = render_bot_filter(session, col4)
    finally:
        session.close()

    st.markdown("")
    show_dashboard(date_from, date_to, selected_bot_id)


def show_dashboard(
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    bot_id: int | None = None,
):
    session = get_session()
    try:
        sources_data = get_sources_stats(session, date_from, date_to, bot_id)

        if not sources_data:
            st.info("Нет данных за выбранные фильтры.")
            return

        total_users = sum(s["total_users"] for s in sources_data)
        total_trial = sum(s["trial_users"] for s in sources_data)
        total_connected = sum(s["connected_users"] for s in sources_data)
        total_paid_users = sum(s["paid_users"] for s in sources_data)
        total_payments = sum(s["total_payments"] for s in sources_data)
        total_revenue = sum(s["total_revenue"] for s in sources_data)

        trial_rate = (total_trial / total_users * 100) if total_users > 0 else 0.0
        connected_rate = (
            (total_connected / total_users * 100) if total_users > 0 else 0.0
        )
        paid_rate = (
            (total_paid_users / total_users * 100) if total_users > 0 else 0.0
        )
        avg_check = total_revenue / total_payments if total_payments > 0 else 0.0

        c1, c2, c3, c4, c5, c6 = st.columns(6)
        with c1:
            st.markdown('<i class="fas fa-users metric-icon"></i>', unsafe_allow_html=True)
            st.metric(
                label="Пользователи",
                value=f"{total_users:,}",
                delta=f"{len(sources_data)} источников",
            )
        with c2:
            st.markdown(
                '<i class="fas fa-flask metric-icon"></i>', unsafe_allow_html=True
            )
            st.metric(
                label="Триал",
                value=f"{total_trial:,}",
                delta=f"{trial_rate:.1f}% охват",
            )
        with c3:
            st.markdown(
                '<i class="fas fa-plug metric-icon"></i>', unsafe_allow_html=True
            )
            st.metric(
                label="Подключились",
                value=f"{total_connected:,}",
                delta=f"{connected_rate:.1f}% охват",
            )
        with c4:
            st.markdown(
                '<i class="fas fa-user-check metric-icon"></i>', unsafe_allow_html=True
            )
            st.metric(
                label="Оплатили",
                value=f"{total_paid_users:,}",
                delta=f"{paid_rate:.1f}% от новых пользователей"
                if total_users > 0
                else "нет новых пользователей за период",
            )
        with c5:
            st.markdown(
                '<i class="fas fa-credit-card metric-icon"></i>', unsafe_allow_html=True
            )
            st.metric(
                label="Платежи",
                value=f"{total_payments:,}",
                delta="по дате оплаты",
            )
        with c6:
            st.markdown(
                '<i class="fas fa-ruble-sign metric-icon"></i>', unsafe_allow_html=True
            )
            st.metric(
                label="Выручка",
                value=f"₽{total_revenue:,.0f}",
                delta=f"₽{avg_check:.0f} средний чек · по дате оплаты",
            )

        st.caption(
            "Пользователи, триал и подключения — по дате регистрации (created_at). "
            "Платежи и выручка (включая круговую диаграмму) — по дате платежа за период. "
            "«Оплатили» — уникальные пользователи этой когорты, у которых в данных есть "
            "хотя бы один платёж (без ограничения по дате оплаты)."
        )

        st.markdown("---")

        col1, col2 = st.columns(2)
        with col1:
            st.markdown(
                '<h3 class="icon-header"><i class="fas fa-chart-bar"></i> Пользователи по источникам</h3>',
                unsafe_allow_html=True,
            )
            st.plotly_chart(create_users_chart(sources_data), width="stretch")
        with col2:
            st.markdown(
                '<h3 class="icon-header"><i class="fas fa-coins"></i> Выручка по источникам</h3>',
                unsafe_allow_html=True,
            )
            st.plotly_chart(create_revenue_chart(sources_data), width="stretch")

        st.markdown("---")
        st.markdown(
            '<h3 class="icon-header"><i class="fas fa-table"></i> Детализация по источникам</h3>',
            unsafe_allow_html=True,
        )

        col_s, _ = st.columns([2, 1])
        with col_s:
            search_query = st.text_input(
                "Поиск источника",
                placeholder="Название источника...",
                label_visibility="collapsed",
            )

        filtered = sources_data
        if search_query:
            filtered = [
                s
                for s in sources_data
                if search_query.lower() in s["source_name"].lower()
            ]

        if not filtered:
            st.info("По запросу ничего не найдено.")
        else:
            df = pd.DataFrame(filtered)
            df["trial_rate"] = (
                (df["trial_users"] / df["total_users"] * 100)
                .where(df["total_users"] > 0, 0)
                .round(1)
            )
            df["connected_rate"] = (
                (df["connected_users"] / df["total_users"] * 100)
                .where(df["total_users"] > 0, 0)
                .round(1)
            )
            df["paid_rate"] = (
                (df["paid_users"] / df["total_users"] * 100)
                .where(df["total_users"] > 0, 0)
                .round(1)
            )
            df["avg_revenue"] = (df["total_revenue"] / df["total_payments"]).round(2)
            df["avg_revenue"] = df["avg_revenue"].fillna(0)

            df = df[
                [
                    "source_name",
                    "total_users",
                    "trial_users",
                    "trial_rate",
                    "connected_users",
                    "connected_rate",
                    "paid_users",
                    "paid_rate",
                    "total_payments",
                    "total_revenue",
                    "avg_revenue",
                ]
            ]
            df.columns = [
                "Источник",
                "Пользователи",
                "Триал",
                "Триал %",
                "Подключились",
                "Подкл. %",
                "Оплатили",
                "Оплатили %",
                "Платежи",
                "Выручка ₽",
                "Средний чек ₽",
            ]

            st.markdown("Выберите строку для детализации источника")
            event = st.dataframe(
                df.style.format(
                    {
                        "Пользователи": "{:,.0f}",
                        "Триал": "{:,.0f}",
                        "Триал %": "{:.1f}%",
                        "Подключились": "{:,.0f}",
                        "Подкл. %": "{:.1f}%",
                        "Оплатили": "{:,.0f}",
                        "Оплатили %": "{:.1f}%",
                        "Платежи": "{:,.0f}",
                        "Выручка ₽": "₽{:,.0f}",
                        "Средний чек ₽": "₽{:.0f}",
                    }
                ),
                width="stretch",
                hide_index=True,
                on_select="rerun",
                selection_mode="single-row",
            )

            if event.selection and event.selection.rows:
                selected_idx = event.selection.rows[0]
                selected_source = df.iloc[selected_idx]["Источник"]
                st.session_state["selected_source"] = selected_source
                st.switch_page("pages/Source_Details.py")
    finally:
        session.close()


if __name__ == "__main__":
    main()
