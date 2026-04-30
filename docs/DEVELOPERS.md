# Lead Tracker — документация для разработчиков

Документ описывает архитектуру, модель данных, API, паттерны кода и операционные процедуры сервиса Lead Tracker. Ориентирован на разработчика, который впервые открыл репозиторий и должен начать дорабатывать или поддерживать сервис.

> Краткий обзор и инструкции по запуску — в корневом [`README.md`](../README.md).

---

## Содержание

1. [Назначение и контекст](#1-назначение-и-контекст)
2. [Архитектура](#2-архитектура)
3. [Стек технологий](#3-стек-технологий)
4. [Структура репозитория](#4-структура-репозитория)
5. [Модель данных](#5-модель-данных)
6. [API](#6-api)
7. [Admin Panel (Streamlit)](#7-admin-panel-streamlit)
8. [Слой работы с БД: UoW и репозитории](#8-слой-работы-с-бд-uow-и-репозитории)
9. [Миграции (Alembic)](#9-миграции-alembic)
10. [Конфигурация и переменные окружения](#10-конфигурация-и-переменные-окружения)
11. [Локальная разработка](#11-локальная-разработка)
12. [Тестирование](#12-тестирование)
13. [Линтинг и стиль кода](#13-линтинг-и-стиль-кода)
14. [Деплой и эксплуатация](#14-деплой-и-эксплуатация)
15. [Скрипты и утилиты](#15-скрипты-и-утилиты)
16. [Известные особенности и техдолг](#16-известные-особенности-и-техдолг)

---

## 1. Назначение и контекст

Lead Tracker решает задачу учёта потока лидов (пользователей) и платежей, поступающих в **Telegram-боты клиента**. Внешние боты (продуктовые/продающие, разрабатываются отдельно от этого репозитория) сообщают этому сервису о событиях через REST API:

- зарегистрировался новый пользователь (с пометкой об источнике трафика, например, `instagram`, `youtube`, конкретная UTM-метка);
- менеджер (оператор бота) вступил в диалог с пользователем (touch);
- пользователь совершил платёж (статус: `completed` / `cancelled`).

На основе этих данных Streamlit-панель строит аналитические дашборды:

- сколько лидов с каждого источника;
- сколько из них реально получили касание менеджера (touch rate);
- сколько оплат и общая выручка (conversion rate, средний чек);
- разбивка по конкретным аккаунтам менеджеров (`bot_account`) и временным периодам.

---

## 2. Архитектура

```
                ┌──────────────────────┐
                │  Внешние Telegram-   │
                │  боты клиента        │
                └──────────┬───────────┘
                           │  HTTPS + X-API-Key
                           ▼
┌──────────────────────────────────────────────────┐
│                   FastAPI (api)                   │
│   /bot-accounts  /users  /payments  /sources      │
└──────────────────────────┬───────────────────────┘
                           │  asyncpg
                           ▼
                  ┌────────────────┐
                  │   PostgreSQL   │◀───────┐
                  └────────────────┘        │
                                            │ sync SQLAlchemy
                                            │
                                  ┌─────────┴─────────┐
                                  │ Streamlit (admin) │
                                  │  Home + Source_…  │
                                  └───────────────────┘
```

Все компоненты — отдельные процессы в Docker Compose (`api`, `admin`, `postgres`).

---

## 3. Стек технологий

| Слой         | Технология                                                              |
| ------------ | ----------------------------------------------------------------------- |
| Язык         | Python 3.13                                                             |
| Менеджер пакетов | [`uv`](https://docs.astral.sh/uv/) (lock-файл: `uv.lock`)           |
| API          | FastAPI, Uvicorn                                                        |
| ORM          | SQLAlchemy 2.0 (async) + advanced-alchemy (репозитории)                 |
| Драйвер БД   | asyncpg (API), psycopg2-binary (Streamlit, sync)                        |
| Миграции     | Alembic                                                                 |
| Валидация    | Pydantic v2, pydantic-settings                                          |
| Admin UI     | Streamlit, Plotly, Pandas, extra-streamlit-components                   |
| Логирование  | loguru                                                                  |
| Контейнеры   | Docker, Docker Compose                                                  |
| Тесты        | pytest, pytest-asyncio, httpx                                           |
| Линтер       | ruff                                                                    |

---

## 4. Структура репозитория

```
lead_tracker/
├── src/
│   ├── api/
│   │   ├── main.py              # создание FastAPI app, dependency verify_api_key
│   │   ├── handlers/
│   │   │   ├── bot_accounts.py  # CRUD bot_account + связь с менеджерами/чатами
│   │   │   ├── users.py         # создание, статистика, touch, info, list
│   │   │   ├── payments.py      # создание, выборки
│   │   │   └── sources.py       # список источников + статистика
│   │   └── schemas/             # Pydantic-модели запросов/ответов
│   │
│   ├── admin/
│   │   ├── Home.py              # главный дашборд (entrypoint Streamlit)
│   │   ├── pages/
│   │   │   └── Source_Details.py # детальная страница источника
│   │   ├── auth.py              # cookie-аутентификация (HMAC-токен)
│   │   ├── db.py                # sync engine, SessionLocal
│   │   └── queries.py           # переиспользуемые SQL-запросы и UI-фильтры
│   │
│   ├── database/
│   │   ├── core.py              # async engine, SessionFactory, get_uow / get_session
│   │   ├── uow.py               # UnitOfWork: один session, все репозитории
│   │   ├── models/              # SQLAlchemy-модели
│   │   ├── repos/               # advanced-alchemy SQLAlchemyAsyncRepository per model
│   │   └── migration/           # Alembic env.py + versions/
│   │
│   └── config.py                # pydantic-settings (читает .env)
│
├── tests/                       # pytest (модули api/, admin/)
├── scripts/
│   ├── generate_api_key.py      # make secret-key
│   ├── import_users.py          # импорт пользователей из CSV
│   ├── cleanup_users.py         # очистка
│   └── users_with_touched_at.csv
├── docs/
│   └── DEVELOPERS.md            # этот документ
├── .streamlit/config.toml       # тема Streamlit + headless режим
├── docker-compose.yaml
├── Dockerfile                   # python:3.13-slim + uv sync
├── Makefile                     # обёртки над docker compose / alembic
├── pyproject.toml               # зависимости + pytest + alembic config
├── uv.lock
├── example.env
├── CLAUDE.md
└── README.md
```

---

## 5. Модель данных

Все таблицы определены в `src/database/models/`. Базовый класс — `Base(DeclarativeBase)` из `models/base.py`.

### 5.1. `users`

| Поле          | Тип             | Заметки                                       |
| ------------- | --------------- | --------------------------------------------- |
| `id` (PK)     | `BIGINT`        | Telegram user id (передаётся внешним ботом).  |
| `username`    | `VARCHAR` null  | Telegram username без `@`.                    |
| `full_name`   | `VARCHAR` null  |                                               |
| `source`      | `VARCHAR` null  | Имя источника (FK по значению — см. `sources`). |
| `touched_at`  | `TIMESTAMP` null | Момент первого касания менеджером.           |
| `created_at`  | `TIMESTAMP`     | `default=datetime.now`                        |
| `updated_at`  | `TIMESTAMP`     | `onupdate=datetime.now`                       |

### 5.2. `payments`

| Поле                | Тип               | Заметки                                          |
| ------------------- | ----------------- | ------------------------------------------------ |
| `id` (PK)           | `UUID`            | Генерируется при создании записи (`uuid4`).      |
| `user_id`           | `BIGINT`          | Связь с `users.id` (без FK, см. §16).            |
| `amount`            | `NUMERIC(10,2)`   | В рублях.                                        |
| `status`            | `VARCHAR`         | Enum `PaymentStatus`: `completed` / `cancelled`. |
| `meta`              | `JSONB` null      | Произвольный payload от платёжки.                |
| `source_account_id` | `UUID` null, FK   | → `bot_accounts.id`. К какому боту относится.    |
| `created_at`        | `TIMESTAMP`       |                                                  |

### 5.3. `sources`

| Поле          | Тип       | Заметки                            |
| ------------- | --------- | ---------------------------------- |
| `name` (PK)   | `VARCHAR` | Имя источника (уникально).         |
| `created_at`  | `TIMESTAMP` |                                   |

`Source` создаётся автоматически при первом `POST /users/` с новым значением `source`.

### 5.4. `bot_accounts`

Описывает аккаунт продающего бота, события которого мы принимаем. Один менеджер может иметь несколько ботов.

| Поле                  | Тип       | Заметки                                          |
| --------------------- | --------- | ------------------------------------------------ |
| `id` (PK)             | `UUID`    | `default=uuid4`                                  |
| `manager_account_id`  | `BIGINT`  | FK → `manager_accounts.id`                       |
| `bot_id`              | `BIGINT` null, unique | Telegram id бота.                  |
| `bot_username`        | `VARCHAR` null |                                             |
| `created_at`          | `TIMESTAMP` |                                                |

### 5.5. `manager_accounts`

| Поле          | Тип       | Заметки                            |
| ------------- | --------- | ---------------------------------- |
| `id` (PK)     | `BIGINT`  | Telegram id менеджера.             |
| `username`    | `VARCHAR` null | Telegram username.            |
| `created_at`  | `TIMESTAMP` |                                  |

### 5.6. `chats`

Чаты, в которых работает менеджер (для отображения в фильтре).

| Поле          | Тип       |
| ------------- | --------- |
| `name` (PK)   | `VARCHAR` |
| `created_at`  | `TIMESTAMP` |

### 5.7. `manager_account_chats` (M2M)

| Поле                  | Тип       | FK                          |
| --------------------- | --------- | --------------------------- |
| `manager_account_id` (PK)  | `BIGINT`  | → `manager_accounts.id` |
| `chat_name` (PK)      | `VARCHAR` | → `chats.name`              |
| `created_at`          | `TIMESTAMP` |                           |

### 5.8. `user_bot_accounts` (M2M)

Связывает пользователей с ботами, через которые они пришли (с `ON DELETE CASCADE` на `users`).

| Поле                  | Тип       | FK                                  |
| --------------------- | --------- | ----------------------------------- |
| `user_id` (PK)        | `BIGINT`  | → `users.id` ON DELETE CASCADE      |
| `bot_account_id` (PK) | `UUID`    | → `bot_accounts.id`                 |
| `created_at`          | `TIMESTAMP` |                                   |

### 5.9. ER-диаграмма (упрощённая)

```
manager_accounts ──< manager_account_chats >── chats
        │
        │ 1:N
        ▼
   bot_accounts ──< user_bot_accounts >── users ──┐
        │                                          │
        │ 1:N (source_account_id)                 │ 1:N (user_id)
        ▼                                          ▼
                  payments  ◀──────────────  (логическая связь)

sources ◀── (по значению поля User.source) ──── users
```

---

## 6. API

Базовый URL (локально): `http://localhost:8000`. Все эндпоинты требуют заголовок `X-API-Key: <API_KEY>` (проверяется в `verify_api_key`, `src/api/main.py`). При несовпадении — `401 Invalid X-API-KEY`.

Swagger UI: `/docs`. ReDoc: `/redoc`.

### 6.1. Bot Accounts — `/bot-accounts`

| Метод   | Путь                  | Назначение                                                                 |
| ------- | --------------------- | -------------------------------------------------------------------------- |
| `POST`  | `/bot-accounts/`      | Создать `bot_account`. Если `manager_id` нет — создаётся `ManagerAccount`. Если передан `chat_name` — создаётся `Chat` и связь M2M. Идемпотентен по `manager_account_id`. |
| `GET`   | `/bot-accounts/`      | Список всех `bot_account`.                                                 |
| `GET`   | `/bot-accounts/{bot_id}` | Получить по Telegram-`bot_id`. 404, если нет.                           |

**`POST /bot-accounts/` body (`BotAccountCreate`):**

```json
{
  "manager_id": 123456789,
  "username": "manager_tg",
  "bot_id": 1111111111,
  "bot_username": "my_sales_bot",
  "chat_name": "Группа поддержки A"
}
```

### 6.2. Users — `/users`

| Метод   | Путь                  | Назначение                                                                 |
| ------- | --------------------- | -------------------------------------------------------------------------- |
| `GET`   | `/users/stats`        | Статистика: `total`, `touched_count`, `conversion_percent`. Опц. `?bot_id=`. |
| `POST`  | `/users/`             | Создать пользователя. Идемпотентен по `id`. Требует существующий `bot_account` с переданным `bot_id`. Создаёт `Source` при необходимости и M2M `user_bot_accounts`. |
| `GET`   | `/users/{user_id}/info` | Подробная карточка: пользователь + связанные боты с менеджерами и их чатами. |
| `GET`   | `/users/{user_id}`    | Базовый объект `UserResponse`.                                             |
| `GET`   | `/users/`             | Список + связанные платежи (`UserDTO`). Фильтры: `created_from`, `created_to`, `from_source`. Сортировка по `created_at desc`. |
| `PUT`   | `/users/{user_id}/touch` | Установить `touched_at = now()`.                                        |

**`POST /users/` body (`UserCreate`):**

```json
{
  "id": 555000111,
  "bot_id": 1111111111,
  "username": "ivan",
  "full_name": "Ivan Ivanov",
  "source": "instagram",
  "touched_at": null
}
```

### 6.3. Payments — `/payments`

| Метод   | Путь                       | Назначение                                                                 |
| ------- | -------------------------- | -------------------------------------------------------------------------- |
| `POST`  | `/payments/`               | Создать платёж. Поле `id` генерируется на сервере (UUID). Поиск bot_account: сначала по `bot_id`, fallback по `manager_account_id`. |
| `GET`   | `/payments/{payment_id}`   | Получить платёж по UUID.                                                    |
| `GET`   | `/payments/user/{user_id}` | Все платежи пользователя.                                                  |
| `GET`   | `/payments/`               | Список с пагинацией `?skip=&limit=` (default `0/100`).                     |

**`POST /payments/` body (`PaymentCreate`):**

```json
{
  "user_id": 555000111,
  "bot_id": 1111111111,
  "amount": "1990.00"
}
```

> ⚠️ В `PaymentCreate.bot_id` сейчас задано дефолтное значение `7643449197` с пометкой `TODO: remove after release`. После полного перехода клиентов на передачу `bot_id` дефолт нужно удалить.

### 6.4. Sources — `/sources`

| Метод   | Путь                  | Назначение                                                                 |
| ------- | --------------------- | -------------------------------------------------------------------------- |
| `GET`   | `/sources/`           | Список источников. Опц. флаги `?count=true` и `?today_count=true` — добавляют статистику по пользователям. |
| `GET`   | `/sources/{name}`     | Получить источник по имени.                                                |

### 6.5. Коды ответов

- `200` — OK / успешное создание (используется и для POST вместо `201`).
- `401` — отсутствует/неверный `X-API-Key`.
- `404` — сущность не найдена (`User`, `Payment`, `BotAccount`, `Source`).
- `422` — ошибка валидации Pydantic.

---

## 7. Admin Panel (Streamlit)

Точка входа: `src/admin/Home.py`. Дополнительные страницы — в `src/admin/pages/` (Streamlit автоматически делает их доступными по URL `/Source_Details` и т. д.).

### 7.1. Аутентификация

`src/admin/auth.py`:

- логин/пароль из `settings.admin_username` / `settings.admin_password` (по умолчанию `admin/admin`);
- после входа выпускается HMAC-SHA256 токен (`username:timestamp:signature`), подписанный `settings.admin_cookie_secret`;
- токен хранится в cookie `lead_tracker_auth`, TTL — 1 сутки;
- декоратор `@require_auth` оборачивает `main()` каждой страницы.

> 🔒 **Перед продакшеном** обязательно установить нетривиальные `ADMIN_USERNAME`, `ADMIN_PASSWORD`, `ADMIN_COOKIE_SECRET` через `.env`.

### 7.2. Подключение к БД

В админке используется **синхронный** SQLAlchemy engine (`src/admin/db.py`) — Streamlit плохо дружит с async. DSN из настроек преобразуется: `postgresql+asyncpg://` → `postgresql://`.

### 7.3. Дашборд (Home)

- Фильтры: период (7/30 дней, конкретный день, произвольный диапазон, всё время) + аккаунт (`render_account_filter`).
- Метрики: всего пользователей, касаний, платежей, выручка, средний чек, конверсия, охват.
- Графики (Plotly): bar по пользователям, donut по выручке.
- Таблица источников с поиском и кликабельной строкой → переход в `Source_Details`.

### 7.4. Тема

`/.streamlit/config.toml` задаёт тёмную тему и `headless = true` (для Docker без браузера).

---

## 8. Слой работы с БД: UoW и репозитории

### 8.1. Engine и сессии

`src/database/core.py`:

```python
engine = create_async_engine(settings.postgres_dsn, pool_size=10, max_overflow=20, pool_pre_ping=True)
SessionFactory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
```

### 8.2. UnitOfWork

`src/database/uow.py` — обёртка вокруг сессии, агрегирует все репозитории. Использовать через `async with UnitOfWork(SessionFactory) as uow:` или через FastAPI-dependency `get_uow`.

```python
async def get_uow() -> AsyncGenerator[UnitOfWork]:
    async with UnitOfWork(session_factory=SessionFactory) as uow:
        yield uow
```

`__aenter__` создаёт `session` и инициализирует все `*_repo`. `__aexit__` делает `rollback()` при исключении и всегда закрывает сессию. Коммит — явно, через `await uow.commit()`.

### 8.3. Репозитории

`src/database/repos/*.py` — наследники `advanced_alchemy.repository.SQLAlchemyAsyncRepository[Model]`. Из коробки доступно: `add`, `get_one_or_none`, `list`, `update`, `delete`, и т. д.

Пример:

```python
class UserRepository(SQLAlchemyAsyncRepository[User]):
    model_type = User
```

Если нужны кастомные запросы — добавлять методы в соответствующий репозиторий или писать `select(...)` прямо в handler через `uow.user_repo.session`.

### 8.4. Канонический паттерн handler-а

```python
@router.post("/", response_model=UserResponse)
async def create_user(
    data: UserCreate, uow: Annotated[UnitOfWork, Depends(get_uow)]
) -> UserResponse:
    existing = await uow.user_repo.get_one_or_none(id=data.id)
    if existing:
        return UserResponse.model_validate(existing)

    user = User(id=data.id, ...)
    user = await uow.user_repo.add(user)
    await uow.commit()
    return UserResponse.model_validate(user)
```

---

## 9. Миграции (Alembic)

Конфигурация задана в `pyproject.toml`:

```toml
[tool.alembic]
script_location = "%(here)s/src/database/migration"
prepend_sys_path = [".", "src"]
```

Файла `alembic.ini` нет — настройки берутся из `pyproject.toml` (поддерживается современным Alembic).

### 9.1. Команды

```bash
# Создать новую миграцию по diff моделей
make migrate
# == docker compose run --rm api uv run alembic revision --autogenerate -m "..."

# Накатить до head
make migrateup

# Откатить (в контейнере)
docker compose run --rm api uv run alembic downgrade -1
```

При создании новой миграции **обязательно**:

1. Указать осмысленный `-m "..."` (отредактировать вручную команду в `Makefile` или дернуть alembic напрямую).
2. Открыть сгенерированный файл в `src/database/migration/versions/` и проверить, что autogenerate не выкинул лишнего и не переименовал таблицы вместо `add/drop`.

### 9.2. Правки моделей

Все модели импортируются в `src/database/models/__init__.py`. При добавлении новой модели:

1. Создать файл в `src/database/models/`, унаследовать `Base`.
2. Импортировать модель в `models/__init__.py` (иначе Alembic её не увидит).
3. Создать репозиторий в `src/database/repos/` и зарегистрировать в `repos/__init__.py` и в `UnitOfWork`.
4. Сгенерировать миграцию.

---

## 10. Конфигурация и переменные окружения

`src/config.py`:

```python
class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    postgres_dsn: str
    api_key: str | None = None
    admin_username: str = "admin"
    admin_password: str = "admin"
    admin_cookie_secret: str = "default-secret-change-in-production"
```

### Переменные окружения

| Переменная             | Кем используется               | Обязательная   | Назначение                                                       |
| ---------------------- | ------------------------------ | -------------- | ---------------------------------------------------------------- |
| `POSTGRES_USER`        | `docker-compose`               | да             | Пользователь Postgres.                                           |
| `POSTGRES_PASSWORD`    | `docker-compose`               | да             | Пароль Postgres.                                                 |
| `POSTGRES_DB`          | `docker-compose`               | да             | Имя БД.                                                          |
| `POSTGRES_DSN`         | `Settings` (внутри контейнера) | да             | Полный DSN, формируется в `docker-compose.yaml` автоматически.   |
| `API_KEY`              | API                            | да             | Секрет для заголовка `X-API-Key`. Сгенерировать `make secret-key`. |
| `API_PORT`             | `docker-compose`               | да             | Порт, на котором экспонируется API (обычно `8000`).             |
| `ADMIN_PORT`           | `docker-compose`               | нет            | Порт Streamlit (default `8501`).                                 |
| `ADMIN_USERNAME`       | Admin Panel                    | нет            | Логин админа (default `admin`).                                  |
| `ADMIN_PASSWORD`       | Admin Panel                    | нет            | Пароль админа (default `admin`).                                 |
| `ADMIN_COOKIE_SECRET`  | Admin Panel                    | **в проде да** | Секрет для подписи cookie. Default небезопасен.                 |

`example.env` содержит шаблон.

---

## 11. Локальная разработка

### 11.1. Через Docker (рекомендованный способ)

```bash
cp example.env .env       # заполнить
make up
make migrateup
```

Код в `src/` смонтирован в контейнеры `api` и `admin` томом — изменения подхватываются (FastAPI запускается без `--reload`, поэтому для API нужен `make restart` или дописать `--reload` в команду запуска docker-compose).

### 11.2. Локально без Docker

```bash
uv sync                                 # python 3.13 + установка зависимостей
# Поднять Postgres любым удобным способом (например, docker compose up -d postgres)

# Применить миграции
uv run alembic upgrade head

# Запустить API
uv run uvicorn src.api.main:app --reload --host 0.0.0.0 --port 8000

# Запустить Admin
cd src && uv run streamlit run admin/Home.py --server.port 8501
```

`PYTHONPATH` уже задан в `Dockerfile` и `pyproject.toml.[tool.pytest.ini_options]`. Для локального запуска `streamlit` критично работать из `src/` (как в Docker `working_dir: /app/src`), иначе импорт `from config import settings` сломается.

---

## 12. Тестирование

```bash
uv run pytest                                # все тесты
uv run pytest tests/api/                     # подмножество
uv run pytest tests/api/test_users.py::test_create_user -v
```

Конфигурация в `pyproject.toml`:

```toml
[tool.pytest.ini_options]
addopts = "-xs"               # стоп на первом упавшем тесте, без захвата stdout
pythonpath = ["src"]
```

Используются:

- `pytest-asyncio` — для async-тестов API;
- `httpx.AsyncClient` — для HTTP-вызовов в тестах FastAPI.

При написании новых тестов:

- использовать отдельную тестовую БД (или `pytest-fixture`, поднимающую транзакцию-обёртку и откатывающую её);
- покрывать как минимум: создание сущности, идемпотентность повторного POST, обработку 404/401.

---

## 13. Линтинг и стиль кода

```bash
uv run ruff check src/         # проверка
uv run ruff check src/ --fix   # автофиксы
uv run ruff format src/        # форматирование
```

Конкретный набор правил ruff не зафиксирован в `pyproject.toml` — действуют дефолты. При желании ужесточить — добавить секцию `[tool.ruff]`.

Стилевые соглашения по коду:

- Async везде, кроме админки;
- Pydantic-схемы только в `src/api/schemas/`;
- В handler-ах — паттерн «получи через UoW → проверь → измени → commit → верни Pydantic-модель»;
- Логирование — через `loguru` (`from loguru import logger`), а не `print` или стандартный `logging`.

---

## 14. Деплой и эксплуатация

### 14.1. Сборка и запуск на сервере

```bash
git clone <repo> lead_tracker
cd lead_tracker
cp example.env .env
# отредактировать .env: продовые секреты, реальные пароли, ADMIN_COOKIE_SECRET
make up
make migrateup
```

### 14.2. Чек-лист перед продакшеном

- [ ] `API_KEY` сгенерирован случайно (`make secret-key`), длина ≥ 32 байт.
- [ ] `POSTGRES_PASSWORD` нетривиальный.
- [ ] `ADMIN_USERNAME` и `ADMIN_PASSWORD` изменены с дефолтных.
- [ ] `ADMIN_COOKIE_SECRET` заменён на случайный секрет.
- [ ] Admin Panel и API закрыты от интернета (доступ только через VPN / reverse-proxy с basic-auth / IP-whitelist).
- [ ] Включён HTTPS (например, через nginx + certbot перед `api`/`admin`).
- [ ] Настроен бэкап `postgres_data` (volume).
- [ ] Настроен мониторинг логов (`make logs` хорошо для отладки, на проде — централизованный сборщик).
- [ ] Понятен план миграций при выкатке (см. ниже).

### 14.3. Деплой обновления

```bash
git pull
make up               # пересобрать и поднять
make migrateup        # применить новые миграции
```

При несовместимых изменениях схемы — сначала остановить API, прогнать миграцию, поднять API.

### 14.4. Бэкапы Postgres

```bash
# дамп
docker compose exec postgres pg_dump -U $POSTGRES_USER $POSTGRES_DB > backup_$(date +%F).sql

# восстановление
cat backup.sql | docker compose exec -T postgres psql -U $POSTGRES_USER $POSTGRES_DB
```

---

## 15. Скрипты и утилиты

`scripts/`:

- `generate_api_key.py` — печатает случайный токен для `API_KEY`. Запуск: `make secret-key` или `python3 -m scripts.generate_api_key`.
- `import_users.py` — импортирует пользователей из CSV (см. `scripts/users_with_touched_at.csv` как пример формата). Использовать осторожно — пишет в продовую БД.
- `cleanup_users.py` — удаление пользователей. Перед запуском внимательно прочитать код.
- `vps_deploy_ip.sh` — развёртывание на Ubuntu VPS по IP (Docker, без домена); см. комментарии в начале файла.
- `vps_nuke_db.sh` — полный сброс данных Postgres в текущем проекте Docker Compose (`down -v`), затем `up` и `alembic upgrade head`; требует ввода `DELETE` для подтверждения.

Python-скрипты предполагают, что переменные окружения подгружены и Postgres доступен. Bash-скрипты для VPS вызывают `docker compose` из каталога с `docker-compose.yaml`.

---

## 16. Известные особенности и техдолг

| Что                                                                                                       | Где                                              | Влияние   |
| --------------------------------------------------------------------------------------------------------- | ------------------------------------------------ | --------- |
| `PaymentCreate.bot_id` имеет дефолтное значение `7643449197` с пометкой `TODO: remove after release`.     | `src/api/schemas/payment.py`                     | После окончательного перехода клиентов на передачу `bot_id` дефолт удалить.  |
| У `payments.user_id` нет FK на `users.id` (и нет FK у `users.source` на `sources.name`).                  | `src/database/models/payment.py`, `user.py`      | Допускает рассинхрон данных; добавить FK миграцией при возможности.          |
| Дефолтные `admin_username/password/cookie_secret` совпадают с публичными.                                 | `src/config.py`                                  | Обязательно переопределить в проде (см. чек-лист §14.2).                     |
| FastAPI запускается без `--reload`; правки требуют `make restart`.                                        | `docker-compose.yaml` (`command:`)               | Для удобства разработки можно добавить `--reload`.                           |
| Время в `Dockerfile` зашито в `Europe/Moscow`.                                                            | `Dockerfile`                                     | Все `created_at`/`touched_at` пишутся в МСК. Учитывать при отчётах.          |
| `make up` строит образы каждый раз; нет CI.                                                               | `Makefile`                                       | На больших командах добавить GitHub Actions / lint+test pipeline.            |

---

## Контакты и поддержка

Для вопросов по архитектуре и ранее принятым решениям — смотреть git-лог и комментарии в коде. Документ обновлять при добавлении новых эндпоинтов, моделей и значимых изменений в инфраструктуре.
