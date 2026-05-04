"""
Примеры aiohttp-запросов ко всем постбек-событиям Lead Tracker API.

Текущие эндпоинты (см. src/api/handlers/):
  POST /users/          — регистрация пользователя (первый заход)
  POST /users/trial     — отметка триала
  POST /users/connected — отметка «подключился»
  POST /payments/       — создание платежа (пользователь должен уже существовать)

Авторизация: заголовок X-API-Key (значение из API_KEY в .env сервиса).

Запуск (нужен пакет aiohttp, в проекте его нет по умолчанию):
  pip install aiohttp
  # или: uv pip install aiohttp

  set LEAD_TRACKER_BASE=http://127.0.0.1:8000
  set LEAD_TRACKER_API_KEY=ваш_ключ
  python examples/aiohttp_tracker_events.py
"""

from __future__ import annotations

import asyncio
import os
from typing import Any

import aiohttp

# Подставьте URL API и ключ (или задайте переменные окружения).
BASE_URL = os.environ.get("LEAD_TRACKER_BASE", "http://127.0.0.1:8000").rstrip("/")
API_KEY = os.environ.get("LEAD_TRACKER_API_KEY", "replace-with-your-api-key")

HEADERS = {"X-API-Key": API_KEY}


async def post_json(
    session: aiohttp.ClientSession,
    path: str,
    payload: dict[str, Any],
) -> tuple[int, Any]:
    url = f"{BASE_URL}{path}"
    async with session.post(url, headers=HEADERS, json=payload) as resp:
        text = await resp.text()
        try:
            body = await resp.json(content_type=None)
        except Exception:
            body = text
        return resp.status, body


async def event_user_registered(session: aiohttp.ClientSession) -> None:
    """POST /users/ — лид зарегистрирован в боте."""
    payload = {
        "user_id": 555000111,
        "username": "ivan_lead",
        "full_name": "Ivan Ivanov",
        "source": "instagram",
        "bot_id": 7643449197,
        "bot_name": "MySalesBot",
    }
    status, body = await post_json(session, "/users/", payload)
    print("[users/] register:", status, body)


async def event_user_trial(session: aiohttp.ClientSession) -> None:
    """POST /users/trial — пользователь взял триал (должен существовать POST /users/)."""
    payload = {
        "user_id": 555000111,
        "bot_id": 7643449197,
    }
    status, body = await post_json(session, "/users/trial", payload)
    print("[users/trial]:", status, body)


async def event_user_connected(session: aiohttp.ClientSession) -> None:
    """POST /users/connected — пользователь подключился (должен существовать POST /users/)."""
    payload = {
        "user_id": 555000111,
        "bot_id": 7643449197,
    }
    status, body = await post_json(session, "/users/connected", payload)
    print("[users/connected]:", status, body)


async def event_payment(session: aiohttp.ClientSession) -> None:
    """POST /payments/ — оплата (user_id+bot_id как у пользователя).

    Поле amount в JSON можно передать строкой ("1990.50") или числом (1990.5).
    """
    payload = {
        "user_id": 555000111,
        "bot_id": 7643449197,
        "amount": "1990.50",
    }
    status, body = await post_json(session, "/payments/", payload)
    print("[payments/]:", status, body)


async def main() -> None:
    timeout = aiohttp.ClientTimeout(total=30)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        await event_user_registered(session)
        await event_user_trial(session)
        await event_user_connected(session)
        await event_payment(session)


if __name__ == "__main__":
    asyncio.run(main())
