COMPOSE := docker compose -f infra/docker/compose.yml
DOCKERFILE := infra/docker/Dockerfile
HELM_CHART := infra/kubernetes/helm/retrieval-engine
MINIKUBE_PROFILE := retrieval

.PHONY: install dev db-up db-down db-logs otel-up obs-up redis-up ingest ingest-sample embed index-fts eval eval-degradation serve serve-reranker serve-itinerary serve-worker serve-image-enrichment-worker test lint format docker-build k8s-deploy k8s-reset k8s-loadtest k8s-urls

install:
	uv sync --all-groups
	uv pip install --reinstall onnxruntime-gpu --index-url https://aiinfra.pkgs.visualstudio.com/PublicPackages/_packaging/onnxruntime-cuda-12/pypi/simple/

dev: install
	cp -n .env.example .env 2>/dev/null || true

db-up:
	$(COMPOSE) up -d postgres

redis-up:
	$(COMPOSE) up -d redis

otel-up:
	$(COMPOSE) up -d jaeger otel-collector

obs-up:
	$(COMPOSE) up -d jaeger otel-collector prometheus grafana

eval-degradation:
	uv run eval --degradation --skip-beir

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

serve-itinerary:
	uv run serve-itinerary

serve-worker:
	uv run serve-worker

serve-image-enrichment-worker:
	uv run serve-image-enrichment-worker

test:
	uv run pytest -q

lint:
	uv run ruff check src tests
	uv run ruff format --check src tests

format:
	uv run ruff check --fix src tests
	uv run ruff format src tests

docker-build:
	docker build -f $(DOCKERFILE) --target query -t retrieval-query:latest .
	docker build -f $(DOCKERFILE) --target reranker -t retrieval-reranker:latest .
	docker build -f $(DOCKERFILE) --target itinerary -t retrieval-itinerary:latest .
	docker build -f $(DOCKERFILE) --target worker -t retrieval-worker:latest .
	docker build -f $(DOCKERFILE) --target image-enrichment -t retrieval-image-enrichment:latest .
	docker build -f $(DOCKERFILE) --target corpus-operator -t retrieval-corpus-operator:latest .

k8s-deploy:
	powershell -ExecutionPolicy Bypass -File infra/kubernetes/scripts/deploy-minikube.ps1

k8s-reset:
	minikube stop -p $(MINIKUBE_PROFILE) || true
	minikube delete --all --purge

k8s-urls:
	minikube service list -p $(MINIKUBE_PROFILE)

k8s-loadtest:
	k6 run tests/load/search.js
