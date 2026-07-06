COMPOSE := docker compose -f infra/docker/compose.yml

.PHONY: install dev db-up db-down db-logs otel-up ingest ingest-sample embed index-fts eval serve serve-reranker test lint format

install:
	uv sync --all-extras
	-uv pip uninstall onnxruntime

dev: install
	cp -n .env.example .env 2>/dev/null || true

db-up:
	$(COMPOSE) up -d postgres

otel-up:
	$(COMPOSE) up -d jaeger otel-collector

db-down:
	$(COMPOSE) down

db-logs:
	$(COMPOSE) logs -f postgres

ingest:
	uv run ingest

ingest-sample:
	uv run ingest --limit 5000

embed:
	uv run embed

index-fts:
	uv run index-fts

eval:
	uv run eval

serve:
	uv run serve

serve-reranker:
	uv run serve-reranker

test:
	uv run pytest -q

lint:
	uv run ruff check src tests
	uv run ruff format --check src tests

format:
	uv run ruff check --fix src tests
	uv run ruff format src tests
