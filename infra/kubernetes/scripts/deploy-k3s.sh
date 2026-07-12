#!/usr/bin/env bash
set -euo pipefail

# Deploy the retrieval-engine chart to k3s (production VPS).
#
# Differences from deploy-minikube.sh: there is no VM to manage — k3s runs on
# the host and serves images from its embedded containerd. Images are either
# built locally and imported via `k3s ctr images import`, or pulled from a
# registry when IMAGE_REGISTRY is set.
#
# Environment knobs:
#   DEPLOY_PROFILE        external (default) | local — which values/env profile to use
#   RELEASE               Helm release name (default: retrieval)
#   IMAGE_TAG             reuse an existing tag instead of building (implies SKIP_BUILD=true)
#   IMAGE_REGISTRY        e.g. ghcr.io/you — push/pull images instead of importing
#   SKIP_BUILD            true to skip docker build (images must already exist)
#   INGRESS_HOST_QUERY    e.g. api.example.com    (Traefik host rule for the query API)
#   INGRESS_HOST_ITINERARY e.g. itinerary.example.com
#   INGRESS_HOST_GRAFANA  e.g. grafana.example.com
#   KUBECONFIG            defaults to /etc/rancher/k3s/k3s.yaml when readable

ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
DEPLOY_PROFILE="${DEPLOY_PROFILE:-external}"
RELEASE="${RELEASE:-retrieval}"
CHART="$ROOT/infra/kubernetes/helm/retrieval-engine"
IMAGE_REGISTRY="${IMAGE_REGISTRY:-}"
SKIP_BUILD="${SKIP_BUILD:-false}"
if [[ -n "${IMAGE_TAG:-}" ]]; then
  SKIP_BUILD="true"
else
  IMAGE_TAG="prod-$(date +%Y%m%d%H%M%S)"
fi

TARGETS=(query reranker itinerary worker image-enrichment web)

# web (Meridian) builds from its own Dockerfile; everything else is a target
# in the shared multi-stage infra/docker/Dockerfile.
build_image() {
  local target="$1"
  if [[ "$target" == "web" ]]; then
    docker build -f "$ROOT/apps/web/Dockerfile" -t "$(image_name web)" "$ROOT/apps/web"
  else
    docker build -f "$ROOT/infra/docker/Dockerfile" --target "$target" -t "$(image_name "$target")" "$ROOT"
  fi
}

# --- cluster access -----------------------------------------------------------
if [[ -z "${KUBECONFIG:-}" && -r /etc/rancher/k3s/k3s.yaml ]]; then
  export KUBECONFIG=/etc/rancher/k3s/k3s.yaml
fi
if ! kubectl cluster-info >/dev/null 2>&1; then
  echo "error: cannot reach the cluster. Is k3s running? (KUBECONFIG=${KUBECONFIG:-unset})" >&2
  echo "hint: sudo systemctl status k3s; or export KUBECONFIG=/etc/rancher/k3s/k3s.yaml" >&2
  exit 1
fi

# k3s ctr needs root; prefix with sudo when we are not.
SUDO=""
if [[ "$(id -u)" != "0" ]] && command -v sudo >/dev/null; then
  SUDO="sudo"
fi

# --- images -------------------------------------------------------------------
image_name() {
  local target="$1"
  if [[ -n "$IMAGE_REGISTRY" ]]; then
    echo "$IMAGE_REGISTRY/retrieval-$target:$IMAGE_TAG"
  else
    echo "retrieval-$target:$IMAGE_TAG"
  fi
}

if [[ "$SKIP_BUILD" != "true" ]]; then
  docker info >/dev/null
  echo "==> Building container images (tag=$IMAGE_TAG)"
  for target in "${TARGETS[@]}"; do
    build_image "$target"
  done
fi

if [[ -n "$IMAGE_REGISTRY" ]]; then
  if [[ "$SKIP_BUILD" != "true" ]]; then
    echo "==> Pushing images to $IMAGE_REGISTRY"
    for target in "${TARGETS[@]}"; do
      docker push "$(image_name "$target")"
    done
  fi
  PULL_POLICY="IfNotPresent"
else
  if [[ "$SKIP_BUILD" != "true" ]]; then
    echo "==> Importing images into k3s containerd"
    if ! command -v k3s >/dev/null; then
      echo "error: k3s binary not found; set IMAGE_REGISTRY to deploy from a registry instead" >&2
      exit 1
    fi
    for target in "${TARGETS[@]}"; do
      echo "    importing $(image_name "$target")"
      docker save "$(image_name "$target")" | $SUDO k3s ctr images import -
    done
  fi
  PULL_POLICY="Never"
fi

# --- Traefik: Let's Encrypt resolver for the public ingress hosts ---------------
echo "==> Applying Traefik ACME config (HelmChartConfig)"
kubectl apply -f "$ROOT/infra/kubernetes/k3s/traefik-config.yaml"

# --- KEDA (ScaledObject CRDs required by the chart) -----------------------------
echo "==> Installing KEDA operator"
helm repo add kedacore https://kedacore.github.io/charts >/dev/null 2>&1 || true
helm repo update kedacore >/dev/null 2>&1 || true
helm upgrade --install keda kedacore/keda --namespace keda --create-namespace --wait --timeout 5m

# --- env + chart values ---------------------------------------------------------
echo "==> Loading app env from .env (profile=$DEPLOY_PROFILE)"
VALUES_LOCAL="$CHART/values.local.yaml"
VALUES_PROFILE="$CHART/values-$DEPLOY_PROFILE.yaml"
bash "$ROOT/infra/kubernetes/scripts/load-env.sh" "$ROOT" "$VALUES_LOCAL" "$DEPLOY_PROFILE"

INGRESS_ARGS=()
[[ -n "${INGRESS_HOST_WEB:-}" ]] && INGRESS_ARGS+=(--set "ingress.hosts.web=$INGRESS_HOST_WEB")
[[ -n "${INGRESS_HOST_QUERY:-}" ]] && INGRESS_ARGS+=(--set "ingress.hosts.query=$INGRESS_HOST_QUERY")
[[ -n "${INGRESS_HOST_ITINERARY:-}" ]] && INGRESS_ARGS+=(--set "ingress.hosts.itinerary=$INGRESS_HOST_ITINERARY")
[[ -n "${INGRESS_HOST_GRAFANA:-}" ]] && INGRESS_ARGS+=(--set "ingress.hosts.grafana=$INGRESS_HOST_GRAFANA")

REGISTRY_ARGS=()
[[ -n "$IMAGE_REGISTRY" ]] && REGISTRY_ARGS+=(--set "image.registry=$IMAGE_REGISTRY")

# Grafana is public behind the ingress (anonymous = Viewer); take the admin
# password from the environment or the VPS .env rather than the chart default.
GRAFANA_ADMIN_PASSWORD="${GRAFANA_ADMIN_PASSWORD:-$(sed -n 's/^GRAFANA_ADMIN_PASSWORD=//p' "$ROOT/.env" 2>/dev/null | head -n1)}"
GRAFANA_ARGS=()
[[ -n "$GRAFANA_ADMIN_PASSWORD" ]] && GRAFANA_ARGS+=(--set "observability.grafana.adminPassword=$GRAFANA_ADMIN_PASSWORD")

echo "==> Deploying Helm chart (profile=$DEPLOY_PROFILE)"
helm upgrade --install "$RELEASE" "$CHART" \
  -f "$VALUES_PROFILE" \
  -f "$CHART/values-k3s.yaml" \
  -f "$VALUES_LOCAL" \
  --set image.tag="$IMAGE_TAG" \
  --set image.pullPolicy="$PULL_POLICY" \
  "${INGRESS_ARGS[@]+"${INGRESS_ARGS[@]}"}" \
  "${REGISTRY_ARGS[@]+"${REGISTRY_ARGS[@]}"}" \
  "${GRAFANA_ARGS[@]+"${GRAFANA_ARGS[@]}"}" \
  --wait --timeout 15m

echo "==> Restarting workloads to pick up freshly loaded images"
kubectl rollout restart deployment -l "app.kubernetes.io/instance=$RELEASE" || true
kubectl rollout status deployment -l "app.kubernetes.io/instance=$RELEASE" --timeout=10m || true

kubectl get pods -l "app.kubernetes.io/instance=$RELEASE"

echo ""
echo "Quick access:"
echo "  Ingress:    kubectl get ingress $RELEASE   (Traefik listens on :80/:443)"
echo "  Query:      kubectl port-forward svc/${RELEASE}-query 8000:8000"
echo "  Grafana:    kubectl port-forward svc/${RELEASE}-grafana 3000:3000"
echo "  Prometheus: kubectl port-forward svc/${RELEASE}-prometheus 9090:9090"
