import os

os.environ.setdefault("RERANK_ENABLED", "false")
os.environ.setdefault("OTEL_ENABLED", "false")
# Prevent duplicate Prometheus timeseries when multiple FastAPI apps are
# imported into one test process (each service is its own process in prod).
os.environ.setdefault("METRICS_ENABLED", "false")
