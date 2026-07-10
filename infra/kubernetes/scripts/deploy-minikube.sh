#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
PROFILE="${MINIKUBE_PROFILE:-retrieval}"
DEPLOY_PROFILE="${DEPLOY_PROFILE:-local}"
RELEASE="${RELEASE:-retrieval}"
CHART="$ROOT/infra/kubernetes/helm/retrieval-engine"
CPUS="${MINIKUBE_CPUS:-4}"
MEMORY="${MINIKUBE_MEMORY:-6144}"

minikube_health() {
  if ! minikube status -p "$PROFILE" >/dev/null 2>&1; then
    echo "missing"
    return
  fi
  local host api
  host="$(minikube status -p "$PROFILE" | awk '/^host:/ {print $2}')"
  api="$(minikube status -p "$PROFILE" | awk '/^apiserver:/ {print $2}')"
  if [[ "$host" == "Running" && "$api" == "Running" ]]; then
    echo "healthy"
  elif [[ "$host" == "Running" ]]; then
    echo "broken"
  else
    echo "stopped"
  fi
}

delete_profile() {
  echo "==> Deleting minikube profile: $PROFILE"
  minikube stop -p "$PROFILE" || true
  minikube delete -p "$PROFILE" --purge || true
  if minikube status -p "$PROFILE" >/dev/null 2>&1; then
    echo "==> Single-profile delete unavailable; running minikube delete --all --purge"
    minikube delete --all --purge
  fi
}

start_profile() {
  local memory="$1"
  local k8s_version="${MINIKUBE_K8S_VERSION:-v1.31.4}"
  minikube stop -p minikube || true
  echo "==> Starting minikube profile: $PROFILE (cpus=$CPUS memory=${memory}MB k8s=$k8s_version)"
  minikube start -p "$PROFILE" --driver=docker --cpus="$CPUS" --memory="$memory" \
    --kubernetes-version="$k8s_version" --wait=all --wait-timeout=10m
}

docker info >/dev/null

health="$(minikube_health)"
if [[ "$health" == "healthy" ]]; then
  echo "==> Minikube profile already healthy: $PROFILE"
elif [[ "$health" == "broken" ]]; then
  echo "==> Minikube profile is broken; recreating"
  delete_profile
  start_profile "$MEMORY"
else
  start_profile "$MEMORY"
fi

kubectl config use-context "$PROFILE"
if ! kubectl cluster-info --context "$PROFILE" >/dev/null 2>&1; then
  echo "==> Cluster API unreachable; retrying with less memory"
  delete_profile
  retry_memory=$(( MEMORY * 3 / 4 ))
  if (( retry_memory < 4096 )); then retry_memory=4096; fi
  start_profile "$retry_memory"
  kubectl config use-context "$PROFILE"
  kubectl cluster-info --context "$PROFILE"
fi

minikube addons enable metrics-server -p "$PROFILE" || true

echo "==> Installing KEDA operator (ScaledObject CRDs required by the chart)"
helm repo add kedacore https://kedacore.github.io/charts || true
helm repo update kedacore || true
helm upgrade --install keda kedacore/keda --namespace keda --create-namespace --wait --timeout 5m

echo "==> Building container images"
IMAGE_TAG="dev-$(date +%Y%m%d%H%M%S)"
for target in query reranker itinerary worker image-enrichment; do
  image="retrieval-$target:$IMAGE_TAG"
  docker build -f "$ROOT/infra/docker/Dockerfile" --target "$target" -t "$image" "$ROOT"
  echo "    loading $image into minikube"
  minikube image load "$image" -p "$PROFILE"
done

echo "==> Loading app env from .env (profile=$DEPLOY_PROFILE)"
VALUES_LOCAL="$CHART/values.local.yaml"
VALUES_PROFILE="$CHART/values-$DEPLOY_PROFILE.yaml"
bash "$ROOT/infra/kubernetes/scripts/load-env.sh" "$ROOT" "$VALUES_LOCAL" "$DEPLOY_PROFILE"

echo "==> Removing stale resources from pre-rename Helm revisions"
for kind in deployment service statefulset horizontalpodautoscaler job; do
  while IFS= read -r name; do
    case "$name" in
      */retrieval-retrieval-engine-*)
        echo "    deleting $name"
        kubectl delete "$name" --ignore-not-found
        ;;
    esac
  done < <(kubectl get "$kind" -o name 2>/dev/null || true)
done

echo "==> Deploying Helm chart (profile=$DEPLOY_PROFILE)"
bootstrap_ingest="false"
if [[ "$DEPLOY_PROFILE" == "local" ]]; then
  bootstrap_ingest="true"
fi
helm upgrade --install "$RELEASE" "$CHART" \
  -f "$VALUES_PROFILE" \
  -f "$VALUES_LOCAL" \
  --set image.tag="$IMAGE_TAG" \
  --set image.pullPolicy=Never \
  --set nodePort.enabled=true \
  --set bootstrap.sampleIngest.enabled="$bootstrap_ingest" \
  --wait --timeout 15m

echo "==> Restarting workloads to pick up freshly loaded images"
kubectl rollout restart deployment -l "app.kubernetes.io/instance=$RELEASE" || true
kubectl rollout status deployment -l "app.kubernetes.io/instance=$RELEASE" --timeout=10m || true

kubectl get pods -l "app.kubernetes.io/instance=$RELEASE"

echo ""
echo "Quick access:"
echo "  Query:      minikube service ${RELEASE}-query -p $PROFILE --url"
echo "  Itinerary:  minikube service ${RELEASE}-itinerary -p $PROFILE --url"
echo "  Jaeger UI:  minikube service ${RELEASE}-jaeger -p $PROFILE --url"
echo "  Grafana:    minikube service ${RELEASE}-grafana -p $PROFILE --url"
echo "  Prometheus: kubectl port-forward svc/${RELEASE}-prometheus 9090:9090"
