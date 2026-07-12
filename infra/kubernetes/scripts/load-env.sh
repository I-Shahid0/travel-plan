#!/usr/bin/env bash
set -euo pipefail

ROOT="${1:?repo root required}"
OUT_FILE="${2:?output file required}"
PROFILE="${3:-local}"
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

if [[ "$PROFILE" == "local" ]]; then
  VARS["DATABASE_URL"]="postgresql+asyncpg://retrieval:retrieval@${PREFIX}-postgres:5432/retrieval"
  VARS["DATABASE_URL_SYNC"]="postgresql://retrieval:retrieval@${PREFIX}-postgres:5432/retrieval"
  VARS["REDIS_URL"]="redis://${PREFIX}-redis:6379/0"
fi

# In-cluster service DNS — always rewrite (even when DB/Redis are external).
VARS["RERANKER_URL"]="http://${PREFIX}-reranker:8001"
VARS["QUERY_SERVICE_URL"]="http://${PREFIX}-query:8000"
VARS["OTEL_EXPORTER_OTLP_ENDPOINT"]="http://${PREFIX}-otel-collector:4317"
VARS["EMBEDDING_DEVICE"]="cpu"
VARS["RERANKER_DEVICE"]="cpu"

# URL normalization lives in the Python package (single source of truth).
# retrieval_engine.env_normalize prints KEY=VALUE lines for the vars it fixes.
EXTERNAL_REDIS_ADDRESS=""
EXTERNAL_REDIS_PASSWORD=""
EXTERNAL_REDIS_TLS="false"
if [[ "$PROFILE" == "external" ]]; then
  while IFS= read -r line; do
    key="${line%%=*}"
    val="${line#*=}"
    case "$key" in
      DATABASE_URL|DATABASE_URL_SYNC|REDIS_URL) VARS["$key"]="$val" ;;
      REDIS_ADDRESS) EXTERNAL_REDIS_ADDRESS="$val" ;;
      REDIS_PASSWORD) EXTERNAL_REDIS_PASSWORD="$val" ;;
      REDIS_TLS) EXTERNAL_REDIS_TLS="$val" ;;
    esac
  done < <(
    DATABASE_URL="${VARS[DATABASE_URL]:-}" \
    DATABASE_URL_SYNC="${VARS[DATABASE_URL_SYNC]:-}" \
    REDIS_URL="${VARS[REDIS_URL]:-}" \
    uv run --project "$ROOT" python -m retrieval_engine.env_normalize
  )
fi

SECRET_KEYS=(DATABASE_URL DATABASE_URL_SYNC REDIS_URL GOOGLE_API_KEY FIRECRAWL_API_KEY)

mkdir -p "$(dirname "$OUT_FILE")"
{
  echo "appEnv:"
  for key in "${!VARS[@]}"; do
    skip=false
    for secret_key in "${SECRET_KEYS[@]}"; do
      if [[ "$key" == "$secret_key" ]]; then
        skip=true
        break
      fi
    done
    if $skip; then continue; fi
    printf '  %s: "%s"\n' "$key" "${VARS[$key]//\"/\\\"}"
  done
  has_secrets=false
  for secret_key in "${SECRET_KEYS[@]}"; do
    [[ -n "${VARS[$secret_key]:-}" ]] && has_secrets=true && break
  done
  if $has_secrets; then
    echo "appSecrets:"
    for secret_key in "${SECRET_KEYS[@]}"; do
      [[ -n "${VARS[$secret_key]:-}" ]] || continue
      printf '  %s: "%s"\n' "$secret_key" "${VARS[$secret_key]//\"/\\\"}"
    done
  fi
  if [[ "$PROFILE" == "external" && -n "$EXTERNAL_REDIS_ADDRESS" ]]; then
    echo "externalRedis:"
    printf '  address: "%s"\n' "${EXTERNAL_REDIS_ADDRESS//\"/\\\"}"
    printf '  password: "%s"\n' "${EXTERNAL_REDIS_PASSWORD//\"/\\\"}"
    printf '  tls: %s\n' "$EXTERNAL_REDIS_TLS"
  fi
} > "$OUT_FILE"

echo "==> Wrote Helm env values (profile=$PROFILE) from $(basename "$ENV_FILE") -> $OUT_FILE"
