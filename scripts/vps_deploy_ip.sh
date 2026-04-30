#!/usr/bin/env bash
# Развёртывание Lead Tracker на Ubuntu VPS без домена: доступ по http://IP:порт
# Запуск из корня репозитория (рядом с docker-compose.yaml):
#   chmod +x scripts/vps_deploy_ip.sh
#   ./scripts/vps_deploy_ip.sh
#
# Опции окружения:
#   OPEN_UFW=1       — открыть в ufw SSH + API_PORT + ADMIN_PORT (осторожно на удалённой машине)
#   SKIP_DOCKER=1    — не ставить Docker (уже установлен)
#
# Важно: трафик по HTTP без шифрования. Для продакшена лучше домен + HTTPS.

set -euo pipefail

REPO_ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
cd "$REPO_ROOT"

if [[ ! -f docker-compose.yaml ]] || [[ ! -f example.env ]]; then
  echo "Запускайте скрипт из клонированного репозитория (нужны docker-compose.yaml и example.env)." >&2
  exit 1
fi

need_cmd() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "Нужна команда: $1" >&2
    exit 1
  }
}

if [[ "${SKIP_DOCKER:-}" != "1" ]]; then
  if ! command -v docker >/dev/null 2>&1; then
    echo ">>> Установка Docker (get.docker.com)..."
    need_cmd curl
    curl -fsSL https://get.docker.com | sudo sh
    sudo systemctl enable --now docker
    if ! getent group docker | grep -q "\b${USER}\b"; then
      sudo usermod -aG docker "$USER"
    fi
    echo ">>> Docker установлен. Если дальше будет «permission denied», выполните: newgrp docker" >&2
    echo "    или перелогиньтесь в SSH и запустите скрипт снова." >&2
  fi
fi

need_cmd docker
docker compose version >/dev/null 2>&1 || {
  echo "Нужен Docker Compose v2 (плагин docker compose)." >&2
  exit 1
}

if ! docker info >/dev/null 2>&1; then
  echo "Нет доступа к сокету Docker (permission denied)." >&2
  echo "Выполните: newgrp docker" >&2
  echo "или выйдите из SSH и зайдите снова, затем повторите: $0" >&2
  exit 1
fi

if [[ ! -f .env ]]; then
  echo ">>> Создаю .env с случайными секретами..."
  need_cmd openssl
  cp example.env .env
  API_KEY=$(openssl rand -hex 32)
  PG_USER=lead_tracker
  PG_DB=lead_tracker
  PG_PASS=$(openssl rand -hex 16)
  COOKIE=$(openssl rand -hex 32)
  ADMIN_PASS=$(openssl rand -hex 12)
  sed -i \
    -e "s/^API_KEY=.*/API_KEY=${API_KEY}/" \
    -e "s/^POSTGRES_USER=.*/POSTGRES_USER=${PG_USER}/" \
    -e "s/^POSTGRES_PASSWORD=.*/POSTGRES_PASSWORD=${PG_PASS}/" \
    -e "s/^POSTGRES_DB=.*/POSTGRES_DB=${PG_DB}/" \
    -e "s/^ADMIN_COOKIE_SECRET=.*/ADMIN_COOKIE_SECRET=${COOKIE}/" \
    -e "s/^ADMIN_PASSWORD=.*/ADMIN_PASSWORD=${ADMIN_PASS}/" \
    .env
  echo ">>> Сохраните учётку админки (сгенерирована случайно):"
  echo "    ADMIN_USERNAME=admin"
  echo "    ADMIN_PASSWORD=${ADMIN_PASS}"
  echo "    (значения также в файле .env)"
else
  echo ">>> Файл .env уже есть — не перезаписываю."
fi

read_env_key() {
  grep -E "^${1}=" .env 2>/dev/null | head -1 | cut -d= -f2- | tr -d '\r' || true
}

API_KEY_VAL=$(read_env_key API_KEY)
PG_USER_VAL=$(read_env_key POSTGRES_USER)
PG_PASS_VAL=$(read_env_key POSTGRES_PASSWORD)
PG_DB_VAL=$(read_env_key POSTGRES_DB)

if [[ -z "${API_KEY_VAL}" ]] || [[ -z "${PG_USER_VAL}" ]] || [[ -z "${PG_PASS_VAL}" ]] || [[ -z "${PG_DB_VAL}" ]]; then
  echo "В .env должны быть заданы API_KEY, POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_DB." >&2
  exit 1
fi

API_PORT=$(read_env_key API_PORT)
ADMIN_PORT=$(read_env_key ADMIN_PORT)
API_PORT="${API_PORT:-8000}"
ADMIN_PORT="${ADMIN_PORT:-8501}"

if [[ "${OPEN_UFW:-}" == "1" ]]; then
  echo ">>> Настройка ufw (SSH + порты API и admin)..."
  sudo ufw allow OpenSSH
  sudo ufw allow "${API_PORT}/tcp"
  sudo ufw allow "${ADMIN_PORT}/tcp"
  sudo ufw --force enable || true
  sudo ufw status
fi

echo ">>> Сборка и запуск контейнеров..."
docker compose up -d --build

echo ">>> Ожидание готовности Postgres..."
sleep 5

echo ">>> Миграции Alembic..."
docker compose run --rm api uv run alembic upgrade head

echo ">>> Состояние:"
docker compose ps

PUBLIC_IP=""
if command -v curl >/dev/null 2>&1; then
  PUBLIC_IP=$(curl -fsS --connect-timeout 3 https://ifconfig.me 2>/dev/null || true)
fi
if [[ -z "${PUBLIC_IP}" ]]; then
  PUBLIC_IP=$(hostname -I 2>/dev/null | awk '{print $1}' || echo "<IP_сервера>")
fi

echo ""
echo "========== Готово (доступ по IP, без домена) =========="
echo " API (Swagger):  http://${PUBLIC_IP}:${API_PORT}/docs"
echo " API (корень):   http://${PUBLIC_IP}:${API_PORT}/"
echo " Admin (Streamlit): http://${PUBLIC_IP}:${ADMIN_PORT}/"
echo ""
echo " Проверка ключа (подставьте свой API_KEY из .env):"
echo "  curl -sS -o /dev/null -w '%{http_code}\\n' -H \"X-API-Key: \$(grep ^API_KEY= .env | cut -d= -f2-)\" \"http://127.0.0.1:${API_PORT}/docs\""
echo ""
echo " Интеграции ботов: URL http://${PUBLIC_IP}:${API_PORT} , заголовок X-API-Key"
echo " Внимание: HTTP без TLS — не передавайте секреты по недоверенным сетям."
echo "========================================================"
