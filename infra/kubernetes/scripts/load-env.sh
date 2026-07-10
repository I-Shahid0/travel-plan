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
  VARS["RERANKER_URL"]="http://${PREFIX}-reranker:8001"
  VARS["QUERY_SERVICE_URL"]="http://${PREFIX}-query:8000"
  VARS["OTEL_EXPORTER_OTLP_ENDPOINT"]="http://${PREFIX}-otel-collector:4317"
  VARS["EMBEDDING_DEVICE"]="cpu"
  VARS["RERANKER_DEVICE"]="cpu"
fi

parse_redis_url() {
  local url="$1"
  local tls="false"
  local rest="$url"

  if [[ "$url" == rediss://* ]]; then
    tls="true"
    rest="${url#rediss://}"
  elif [[ "$url" == redis://* ]]; then
    rest="${url#redis://}"
  else
    return 1
  fi

  rest="${rest%%/*}"
  local userpass="" hostport="$rest"
  if [[ "$rest" == *@* ]]; then
    userpass="${rest%%@*}"
    hostport="${rest#*@}"
  fi

  local password=""
  if [[ "$userpass" == *:* ]]; then
    password="${userpass#*:}"
  fi

  printf '%s\n' "$hostport" "$password" "$tls"
}

EXTERNAL_REDIS_ADDRESS=""
EXTERNAL_REDIS_PASSWORD=""
EXTERNAL_REDIS_TLS="false"
if [[ "$PROFILE" == "external" && -n "${VARS[REDIS_URL]:-}" ]]; then
  mapfile -t _redis_parts < <(parse_redis_url "${VARS[REDIS_URL]}")
  EXTERNAL_REDIS_ADDRESS="${_redis_parts[0]}"
  EXTERNAL_REDIS_PASSWORD="${_redis_parts[1]}"
  EXTERNAL_REDIS_TLS="${_redis_parts[2]}"
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
