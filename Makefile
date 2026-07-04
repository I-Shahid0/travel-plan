COMPOSE := docker compose -f infra/docker/compose.yml

.PHONY: install dev db-up db-down db-logs ingest ingest-sample serve test lint format

install:
	uv sync --all-extras

dev: install
	cp -n .env.example .env 2>/dev/null || true

db-up:
	$(COMPOSE) up -d postgres

db-down:
	$(COMPOSE) down

db-logs:
	$(COMPOSE) logs -f postgres

ingest:
	uv run ingest

ingest-sample:
	uv run ingest --limit 5000

serve:
	uv run serve

test:
	uv run pytest -q

lint:
	uv run ruff check src tests
	uv run ruff format --check src tests

format:
	uv run ruff check --fix src tests
	uv run ruff format src tests
