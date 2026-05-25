from __future__ import annotations

import re
from typing import Any

SHEET_HEADERS = [
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

_SPREADSHEET_ID_RE = re.compile(r"/spreadsheets/d/([a-zA-Z0-9-_]+)")


def parse_spreadsheet_id(path_or_url: str) -> str:
    match = _SPREADSHEET_ID_RE.search(path_or_url)
    if match:
        return match.group(1)
    return path_or_url.strip()


def _pct(part: int, total: int) -> str:
    if total <= 0:
        return "0.0%"
    return f"{part / total * 100:.1f}%"


def _avg_check(revenue: float, payments: int) -> float:
    if payments <= 0:
        return 0.0
    return round(revenue / payments, 2)


def _source_row(source: dict[str, Any]) -> list[str | int | float]:
    total_users = source["total_users"]
    trial_users = source["trial_users"]
    connected_users = source["connected_users"]
    paid_users = source["paid_users"]
    total_payments = source["total_payments"]
    total_revenue = source["total_revenue"]

    return [
        source["source_name"],
        total_users,
        trial_users,
        _pct(trial_users, total_users),
        connected_users,
        _pct(connected_users, total_users),
        paid_users,
        _pct(paid_users, total_users),
        total_payments,
        round(total_revenue),
        round(_avg_check(total_revenue, total_payments)),
    ]


def build_sheet_rows(sources_data: list[dict[str, Any]]) -> list[list[str | int | float]]:
    total_users = sum(s["total_users"] for s in sources_data)
    total_trial = sum(s["trial_users"] for s in sources_data)
    total_connected = sum(s["connected_users"] for s in sources_data)
    total_paid_users = sum(s["paid_users"] for s in sources_data)
    total_payments = sum(s["total_payments"] for s in sources_data)
    total_revenue = sum(s["total_revenue"] for s in sources_data)

    rows: list[list[str | int | float]] = [SHEET_HEADERS]
    rows.append(
        [
            "Всего",
            total_users,
            total_trial,
            _pct(total_trial, total_users),
            total_connected,
            _pct(total_connected, total_users),
            total_paid_users,
            _pct(total_paid_users, total_users),
            total_payments,
            round(total_revenue),
            round(_avg_check(total_revenue, total_payments)),
        ]
    )
    rows.extend(_source_row(source) for source in sources_data)
    return rows
