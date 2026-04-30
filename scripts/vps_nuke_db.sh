#!/usr/bin/env bash
# Полное удаление данных PostgreSQL в Docker Compose (том postgres_data) и повторное
# применение миграций. Все пользователи, платежи и прочие данные в БД уничтожаются.
#
# Запуск из корня репозитория (рядом с docker-compose.yaml и .env):
#   chmod +x scripts/vps_nuke_db.sh
#   ./scripts/vps_nuke_db.sh
#
# Требуется ввести слово DELETE (заглавными) для подтверждения.
#
# Опции окружения:
#   SKIP_UP=1   — только docker compose down -v (не поднимать сервисы и не гонять alembic)

set -euo pipefail

REPO_ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "$REPO_ROOT"

if [[ ! -f docker-compose.yaml ]]; then
  echo "Нужен docker-compose.yaml в текущем каталоге репозитория." >&2
  exit 1
fi

if [[ ! -f .env ]]; then
  echo "Нужен файл .env (скопируйте из example.env и заполните)." >&2
  exit 1
fi

need_cmd() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "Нужна команда: $1" >&2
    exit 1
  }
}

need_cmd docker
docker compose version >/dev/null 2>&1 || {
  echo "Нужен Docker Compose v2 (docker compose)." >&2
  exit 1
}

if ! docker info >/dev/null 2>&1; then
  echo "Нет доступа к Docker. Выполните: newgrp docker или перелогиньтесь в SSH." >&2
  exit 1
fi

echo ""
echo "╔════════════════════════════════════════════════════════════════════╗"
echo "║  ВНИМАНИЕ: будут УДАЛЕНЫ ВСЕ ДАННЫЕ PostgreSQL этого проекта.      ║"
echo "║  Команда: docker compose down -v  (том postgres_data исчезнет)      ║"
echo "╚════════════════════════════════════════════════════════════════════╝"
echo ""
read -r -p "Чтобы продолжить, введите DELETE заглавными буквами: " confirm
if [[ "${confirm}" != "DELETE" ]]; then
  echo "Отмена (ожидалось ровно: DELETE)." >&2
  exit 1
fi

echo ">>> Останавливаю контейнеры и удаляю том с данными Postgres..."
docker compose down -v

if [[ "${SKIP_UP:-}" == "1" ]]; then
  echo ">>> SKIP_UP=1 — контейнеры не поднимаю. Запустите вручную: docker compose up -d && docker compose run --rm api uv run alembic upgrade head"
  exit 0
fi

echo ">>> Запускаю сервисы..."
docker compose up -d

echo ">>> Ожидание Postgres..."
sleep 5

echo ">>> Миграции Alembic..."
docker compose run --rm api uv run alembic upgrade head

echo ">>> Готово. Состояние:"
docker compose ps
echo ""
echo "База пустая (схема создана миграциями). Данных пользователей и платежей нет."
