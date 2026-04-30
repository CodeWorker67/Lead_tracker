# CLAUDE.md

Этот файл — инструкция для Claude Code (claude.ai/code) и других AI-ассистентов при работе в данном репозитории. Все технические детали (архитектура, API, модели, деплой) — в [`docs/DEVELOPERS.md`](docs/DEVELOPERS.md). Этот файл — только то, что нужно знать AI-агенту, чтобы быстро ориентироваться и не ломать конвенции.

---

## 1. Что это за проект

**Lead Tracker** — сервис учёта лидов (пользователей) и платежей для Telegram-ботов клиента, с веб-панелью аналитики на Streamlit.

- Внешние Telegram-боты шлют события в FastAPI (`/users/`, `/payments/`, `/bot-accounts/`, `/sources/`) с заголовком `X-API-Key`.
- Данные хранятся в PostgreSQL.
- Маркетолог/руководитель смотрит дашборды в Streamlit (порт 8501).

Краткий обзор для людей — [`README.md`](README.md). Полная разработческая документация — [`docs/DEVELOPERS.md`](docs/DEVELOPERS.md).

---

## 2. Где что лежит

```
src/
├── api/             # FastAPI: handlers/, schemas/, main.py (verify_api_key)
├── admin/           # Streamlit: Home.py, pages/, auth.py, db.py, queries.py
├── database/
│   ├── core.py      # async engine, SessionFactory, get_uow / get_session
│   ├── uow.py       # UnitOfWork (агрегирует все репозитории)
│   ├── models/      # SQLAlchemy 2.0 (async) модели
│   ├── repos/       # advanced_alchemy SQLAlchemyAsyncRepository per model
│   └── migration/   # Alembic env.py + versions/
└── config.py        # pydantic-settings из .env

tests/               # pytest (api/, admin/)
scripts/             # generate_api_key, import_users, cleanup_users, vps_deploy_ip.sh, vps_nuke_db.sh
docs/DEVELOPERS.md   # ⬅️ полная документация — сюда за деталями
```

Сущности: `User`, `Payment`, `Source`, `BotAccount`, `ManagerAccount`, `Chat`, плюс M2M-таблицы `ManagerAccountChat`, `UserBotAccount`. ER — в `docs/DEVELOPERS.md` §5.

---

## 3. Команды

```bash
# Docker
make up               # build + up -d + logs (поднимает api, admin, postgres)
make stop / start / restart
make logs             # хвост логов api + admin
make ps               # статус
make db               # psql внутрь контейнера postgres

# Миграции (Alembic, конфиг в pyproject.toml)
make migrate          # alembic revision --autogenerate
make migrateup        # alembic upgrade head

# Утилиты
make secret-key       # сгенерировать API_KEY

# Локально (без Docker)
uv sync
uv run pytest
uv run pytest path/to/test.py::test_name -v
uv run ruff check src/
uv run ruff check src/ --fix
uv run uvicorn src.api.main:app --reload
```

---

## 4. Канонические паттерны кода — соблюдать

### 4.1. FastAPI handler

Всегда через `UnitOfWork` (DI через `Depends(get_uow)`), явный `await uow.commit()`, ответ — через `Pydantic.model_validate(...)`:

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

Идемпотентность `POST /users/` по паре (`user_id`, `bot_id`) — норма. `POST /payments/` каждый раз создаёт новую запись с серверным UUID. Не ломать контракт без согласования.

### 4.2. Репозитории

Тонкие наследники `SQLAlchemyAsyncRepository[Model]`. Кастомные методы — добавлять в репозиторий, **не дублировать в handler-ах**. Сложные `select(...)` допустимы прямо в handler через `uow.<repo>.session`, но если запрос переиспользуется — выносить.

### 4.3. Pydantic-схемы

- Только в `src/api/schemas/`.
- `model_config = ConfigDict(from_attributes=True)` для response-схем.
- При добавлении схемы — экспортировать через `src/api/schemas/__init__.py`.

### 4.4. Логирование

`from loguru import logger`. Никаких `print` и стандартного `logging`.

### 4.5. Async vs sync

- API, БД-репозитории, UoW — async (`asyncpg`).
- Streamlit (`src/admin/`) — sync (отдельный engine в `src/admin/db.py`, DSN преобразуется `postgresql+asyncpg://` → `postgresql://`).
- Не смешивать.

### 4.6. Добавление новой модели

1. Файл в `src/database/models/`, наследник `Base`.
2. Импорт в `src/database/models/__init__.py` (иначе Alembic не увидит).
3. Репозиторий в `src/database/repos/`, экспорт в `repos/__init__.py`.
4. Поле в `UnitOfWork.__aenter__`.
5. `make migrate` → проверить сгенерированную миграцию глазами → `make migrateup`.

---

## 5. Конфигурация

`src/config.py` (pydantic-settings, читает `.env`). Полный список переменных — в `docs/DEVELOPERS.md` §11. Минимум:

- `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`, `POSTGRES_DSN`
- `API_KEY`, `API_PORT`
- (опц.) `ADMIN_USERNAME`, `ADMIN_PASSWORD`, `ADMIN_COOKIE_SECRET`, `ADMIN_PORT`

Дефолты `admin_username/password/cookie_secret` небезопасны — это нормально для dev, но при правках в проде проверять, что они переопределены.

---

## 6. Чувствительные/опасные зоны — действовать аккуратно

- **`.env`, `auth.json`** — никогда не коммитить, не выводить содержимое в ответы.
- **`scripts/cleanup_users.py`** — удаляет пользователей. Перед запуском подтверждать у юзера.
- **Миграции** — autogenerate периодически выдаёт `drop_table` вместо `rename`. Всегда читать сгенерированный файл перед `migrateup`.
- **`PaymentCreate.bot_id`** имеет TODO-дефолт (`7643449197`). Не удалять без согласования — клиенты могут ещё не передавать `bot_id`.
- **Время в Docker — Europe/Moscow** (`Dockerfile`). Все `created_at` пишутся в МСК.

---

## 7. Стиль ответов AI

- Технический Markdown (документация, код, коммиты, README/PR) — нормальный русский/английский язык, развёрнуто.
- Чат с пользователем — следовать правилам из глобального `~/.claude/CLAUDE.md` (caveman-ultra). Этот файл их **не** переопределяет.
- При предложении изменений модели/схемы — всегда упоминать необходимость миграции.
- При добавлении эндпоинта — обновлять `docs/DEVELOPERS.md` §6.

---

## 8. Куда смотреть, если…

| Вопрос                                         | Файл                                            |
| ---------------------------------------------- | ----------------------------------------------- |
| Как устроен API endpoint?                      | `src/api/handlers/<name>.py` + `docs/DEVELOPERS.md` §6 |
| Какие поля у модели?                           | `src/database/models/<name>.py` + `docs/DEVELOPERS.md` §5 |
| Как добавить миграцию?                         | `docs/DEVELOPERS.md` §10                        |
| Как работает аутентификация админки?           | `src/admin/auth.py` + `docs/DEVELOPERS.md` §7.1 |
| Что задеплоить на проде?                       | `docs/DEVELOPERS.md` §14 (чек-лист)             |
| Какие переменные окружения нужны?              | `example.env` + `docs/DEVELOPERS.md` §10        |
| Известные баги / техдолг?                      | `docs/DEVELOPERS.md` §16                        |
