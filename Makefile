include .env

COMPOSE := docker compose

SERVICES := api admin

nvim:
	uv run nvim

secret-key:
	python3 -m scripts.generate_api_key

ps:
	$(COMPOSE) ps -a

up:
	$(COMPOSE) up -d --build && $(COMPOSE) && make logs

build:
	$(COMPOSE) build

stop:
	$(COMPOSE) stop

start:
	$(COMPOSE) start && $(COMPOSE) && make logs 

restart:
	$(COMPOSE) restart && $(COMPOSE) && make logs

logs:
	$(COMPOSE) logs -f --tail=200 $(SERVICES)

migrate:
	$(COMPOSE) run --rm api uv run alembic revision --autogenerate

migrateup:
	$(COMPOSE) run --rm api uv run alembic upgrade head

db:
	$(COMPOSE) exec -it postgres psql -h localhost -U $(POSTGRES_USER) -d $(POSTGRES_DB)
