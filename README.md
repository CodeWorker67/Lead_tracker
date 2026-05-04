# Lead Tracker

Сервис учёта лидов и платежей для Telegram-ботов с веб-панелью аналитики.

Lead Tracker принимает события о пользователях и платежах от внешних Telegram-ботов через REST API, хранит их в PostgreSQL и предоставляет руководителю/маркетологу веб-интерфейс для анализа конверсии по источникам трафика и аккаунтам менеджеров.

> 📘 **Подробная документация для разработчиков:** [`docs/DEVELOPERS.md`](docs/DEVELOPERS.md)
> Там описаны архитектура, модель данных, API-эндпоинты, миграции, локальная разработка, деплой и операционные процедуры.

---

## Состав сервиса

| Компонент       | Стек                          | Порт   | Назначение                                                                 |
| --------------- | ----------------------------- | ------ | -------------------------------------------------------------------------- |
| **API**         | FastAPI + SQLAlchemy 2 (async) | `8000` | Приём событий от ботов: пользователи, платежи, привязка к менеджерам.       |
| **Admin Panel** | Streamlit + Plotly             | `8501` | Дашборд: метрики, графики, фильтры по источникам, аккаунтам, периодам.     |
| **PostgreSQL**  | Postgres 17                    | —      | Основное хранилище.                                                        |

Все компоненты собираются и запускаются в Docker Compose.

---

## Быстрый старт

### 1. Требования

- Docker и Docker Compose
- `make`
- (опционально, для локальной разработки без Docker) Python 3.13 + [`uv`](https://docs.astral.sh/uv/)

### 2. Подготовить `.env`

Скопировать пример и заполнить значения:

```bash
cp example.env .env
```

Минимально необходимые переменные (см. `example.env` и [`docs/DEVELOPERS.md`](docs/DEVELOPERS.md#переменные-окружения)):

```env
# API
API_KEY=<сгенерировать секретный ключ, см. ниже>
API_PORT=8000

# PostgreSQL
POSTGRES_USER=lead_tracker
POSTGRES_PASSWORD=<пароль>
POSTGRES_DB=lead_tracker

# Admin panel
ADMIN_PORT=8501
ADMIN_USERNAME=admin
ADMIN_PASSWORD=admin
ADMIN_COOKIE_SECRET=<случайный секрет для подписи cookie>
```

Сгенерировать `API_KEY`:

```bash
make secret-key
```

### 3. Поднять сервисы

```bash
make up           # сборка + запуск всех контейнеров + хвост логов
make migrateup    # применить миграции БД
```

После запуска:

- API: <http://localhost:8000>
- Swagger UI: <http://localhost:8000/docs>
- Admin Panel: <http://localhost:8501>
  - Логин/пароль по умолчанию: `admin` / `admin` (меняются через `ADMIN_USERNAME`, `ADMIN_PASSWORD` в `.env`)

### 4. Проверить работоспособность

```bash
# Создать bot account (админский внешний бот, события которого будем принимать)
curl -X POST http://localhost:8000/bot-accounts/ \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"manager_id": 123456789, "username": "manager_tg", "bot_id": 111, "bot_username": "my_bot"}'

# Создать пользователя
curl -X POST http://localhost:8000/users/ \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"id": 555, "bot_id": 111, "username": "user1", "source": "instagram"}'
```

Подробное описание всех эндпоинтов — в [`docs/DEVELOPERS.md`](docs/DEVELOPERS.md#api).

---

## Полезные команды

```bash
make up           # build + up -d + logs
make stop         # остановить контейнеры
make start        # запустить (без пересборки)
make restart      # рестарт
make logs         # хвост логов api + admin
make ps           # статус контейнеров
make migrate      # сгенерировать новую миграцию (alembic revision --autogenerate)
make migrateup    # накатить миграции
make db           # psql внутри контейнера postgres
make secret-key   # сгенерировать API_KEY
```

Локально (без Docker):

```bash
uv sync                                  # установить зависимости
uv run pytest                            # тесты
uv run ruff check src/                   # линтинг
uv run uvicorn src.api.main:app --reload # API
```

---

## Структура репозитория

```
lead_tracker/
├── src/
│   ├── api/              # FastAPI: handlers, schemas, main
│   ├── admin/            # Streamlit-панель: Home.py, pages/, auth, queries
│   ├── database/         # Модели SQLAlchemy, репозитории, UoW, миграции Alembic
│   └── config.py         # pydantic-settings
├── tests/                # pytest (api, admin)
├── scripts/              # ключ, импорт/очистка пользователей, vps_deploy_ip / vps_nuke_db (Docker)
├── docs/
│   └── DEVELOPERS.md     # ⬅️ полная документация для разработчиков
├── docker-compose.yaml
├── Dockerfile
├── Makefile
├── pyproject.toml
├── CLAUDE.md             # инструкция для AI-ассистента (Claude Code)
└── README.md             # этот файл
```

---

## Куда дальше

- **Архитектура, модели, паттерны (UoW, репозитории), полный список эндпоинтов, миграции, тестирование, чек-лист деплоя:** [`docs/DEVELOPERS.md`](docs/DEVELOPERS.md)
- **Контекст для AI-ассистента (Claude Code):** [`CLAUDE.md`](CLAUDE.md)


Очистка БД на впс
chmod +x scripts/vps_nuke_db.sh
./scripts/vps_nuke_db.sh