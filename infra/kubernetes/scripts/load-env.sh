#!/usr/bin/env bash
set -euo pipefail

ROOT="${1:?repo root required}"
OUT_FILE="${2:?output file required}"
RELEASE="${RELEASE:-retrieval}"
PREFIX="${HELM_FULLNAME_OVERRIDE:-$RELEASE}"

ENV_FILE="$ROOT/.env"
if [[ ! -f "$ENV_FILE" ]]; then
  ENV_FILE="$ROOT/.env.example"
  echo "warning: no .env found; using .env.example" >&2
fi

declare -A VARS=()
while IFS= read -r line || [[ -n "$line" ]]; do
  line="${line%%#*}"
  line="$(echo "$line" | xargs)"
  [[ -z "$line" ]] && continue
  key="${line%%=*}"
  val="${line#*=}"
  VARS["$key"]="$val"
done < "$ENV_FILE"

VARS["DATABASE_URL"]="postgresql+asyncpg://retrieval:retrieval@${PREFIX}-postgres:5432/retrieval"
VARS["DATABASE_URL_SYNC"]="postgresql://retrieval:retrieval@${PREFIX}-postgres:5432/retrieval"
VARS["REDIS_URL"]="redis://${PREFIX}-redis:6379/0"
VARS["RERANKER_URL"]="http://${PREFIX}-reranker:8001"
VARS["QUERY_SERVICE_URL"]="http://${PREFIX}-query:8000"
VARS["OTEL_EXPORTER_OTLP_ENDPOINT"]="http://${PREFIX}-otel-collector:4317"
VARS["EMBEDDING_DEVICE"]="cpu"
VARS["RERANKER_DEVICE"]="cpu"

mkdir -p "$(dirname "$OUT_FILE")"
{
  echo "appEnv:"
  for key in "${!VARS[@]}"; do
    [[ "$key" == "GOOGLE_API_KEY" || "$key" == "FIRECRAWL_API_KEY" ]] && continue
    printf '  %s: "%s"\n' "$key" "${VARS[$key]//\"/\\\"}"
  done
  if [[ -n "${VARS[GOOGLE_API_KEY]:-}" || -n "${VARS[FIRECRAWL_API_KEY]:-}" ]]; then
    echo "appSecrets:"
    if [[ -n "${VARS[GOOGLE_API_KEY]:-}" ]]; then
      printf '  GOOGLE_API_KEY: "%s"\n' "${VARS[GOOGLE_API_KEY]//\"/\\\"}"
    fi
    if [[ -n "${VARS[FIRECRAWL_API_KEY]:-}" ]]; then
      printf '  FIRECRAWL_API_KEY: "%s"\n' "${VARS[FIRECRAWL_API_KEY]//\"/\\\"}"
    fi
  fi
} > "$OUT_FILE"

echo "==> Wrote Helm env values from $(basename "$ENV_FILE") -> $OUT_FILE"
