#!/usr/bin/env bash
set -euo pipefail

# ==============================================================================
# Conflux HQ — Forge Kubernetes Deployment Script
# Tailored for Native Linux Docker Engine & Docker Hub
# ==============================================================================

if [ -z "${DOCKER_USERNAME:-}" ]; then
  read -rp "Enter your Docker Hub username: " DOCKER_USERNAME
fi

export KUBECONFIG="${KUBECONFIG:-team10.yml}"
NAMESPACE="team10"
GIT_SHA=$(git rev-parse --short HEAD)

BACKEND_IMAGE="${DOCKER_USERNAME}/conflux-backend:sha-${GIT_SHA}"
FRONTEND_IMAGE="${DOCKER_USERNAME}/conflux-frontend:sha-${GIT_SHA}"

echo "=========================================================="
echo " Conflux HQ Deployment to Forge ($NAMESPACE)"
echo " Docker User:    $DOCKER_USERNAME"
echo " Git Commit:     $GIT_SHA"
echo " Kubeconfig:     $KUBECONFIG"
echo " Backend Image:  $BACKEND_IMAGE"
echo " Frontend Image: $FRONTEND_IMAGE"
echo "=========================================================="

# 1. Build images natively on Linux amd64 (Zero QEMU emulation overhead)
echo "--> [1/5] Building Backend image (FastAPI + Worker)..."
docker build -t "$BACKEND_IMAGE" -f backend/Dockerfile backend

echo "--> [2/5] Building Frontend image (Next.js Standalone)..."
# Inject .env into frontend build context for Next.js build-time inlining
if [ -f .env ]; then
  cp -f .env frontend/.env.production.local
fi
(docker build -t "$FRONTEND_IMAGE" -f frontend/Dockerfile frontend) || { rm -f frontend/.env.production.local; exit 1; }
rm -f frontend/.env.production.local

# 2. Push images to Docker Hub
echo "--> [3/5] Pushing images to Docker Hub..."
docker push "$BACKEND_IMAGE"
docker push "$FRONTEND_IMAGE"

# 3. Apply Storage, ConfigMap, Secrets from .env, and Public Service
echo "--> [4/5] Applying Kubernetes base manifests and syncing secrets from .env..."
kubectl apply -f k8s/pvc.yaml -n "$NAMESPACE"
kubectl apply -f k8s/configmap.yaml -n "$NAMESPACE"
kubectl apply -f k8s/service.yaml -n "$NAMESPACE"

ENV_FILES=()
[ -f .env ] && ENV_FILES+=(--from-env-file=.env)
[ -f frontend/.env ] && ENV_FILES+=(--from-env-file=frontend/.env)

if [ ${#ENV_FILES[@]} -gt 0 ]; then
  echo "--> Injecting environment variables from ${ENV_FILES[*]} into secret/conflux-secrets..."
  kubectl create secret generic conflux-secrets \
    "${ENV_FILES[@]}" \
    --namespace="$NAMESPACE" \
    --dry-run=client -o yaml | kubectl apply -f -
fi

# 4. Generate deployment with real image tags and apply
echo "--> [5/5] Deploying pod (frontend, backend + embedded worker)..."
sed -e "s|DOCKER_IMAGE_FRONTEND|${FRONTEND_IMAGE}|g" \
    -e "s|DOCKER_IMAGE_BACKEND|${BACKEND_IMAGE}|g" \
    k8s/deployment.yaml | kubectl apply -f - -n "$NAMESPACE"

echo "--> Waiting for pod to become ready..."
kubectl rollout status deployment/conflux-app -n "$NAMESPACE" --timeout=180s

# 5. Run Database Migrations in the running pod
echo "--> Running Alembic database migrations inside backend container..."
POD_NAME=$(kubectl get pods -l app=conflux-app -n "$NAMESPACE" -o jsonpath="{.items[0].metadata.name}")
kubectl exec -i "$POD_NAME" -c backend -n "$NAMESPACE" -- alembic upgrade head

echo "=========================================================="
echo " Deployment Successfully Completed!"
echo " Public Endpoint: https://team10.xtradot.co"
echo " Active Pod:      $POD_NAME"
echo " Verify Health:   curl -I https://team10.xtradot.co/api/v1/healthz"
echo "=========================================================="
echo ""

read -rp "Would you like to forward BOTH Frontend (3000) & Backend (8000) to localhost now? (y/N): " START_PF
if [[ "$START_PF" =~ ^[Yy]$ ]]; then
  echo "Forwarding $POD_NAME to local ports:"
  echo "  -> Frontend: http://localhost:3000"
  echo "  -> Backend:  http://localhost:8000 (API docs: http://localhost:8000/docs)"
  echo "Press Ctrl+C to stop port-forwarding."
  kubectl port-forward pod/"$POD_NAME" 3000:3000 8000:8000 -n "$NAMESPACE"
fi
