import os

os.environ.setdefault("RERANK_ENABLED", "false")
os.environ.setdefault("OTEL_ENABLED", "false")
# Prevent duplicate Prometheus timeseries when multiple FastAPI apps are
# imported into one test process (each service is its own process in prod).
os.environ.setdefault("METRICS_ENABLED", "false")
# Engines are built at import time (db/session.py); tests never connect, but
# the URL must parse even when no .env exists (CI, fresh clones).
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://test:test@localhost:5432/test")
