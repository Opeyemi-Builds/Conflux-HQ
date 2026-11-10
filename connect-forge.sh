#!/usr/bin/env bash
set -euo pipefail

# ==============================================================================
# Conflux HQ — Teammate Cluster Connection & Observation Tool
# Read-only tool: inspect status, stream logs, or forward both FE (3000) & BE (8000)
# ==============================================================================

export KUBECONFIG="${KUBECONFIG:-team10.yml}"
NAMESPACE="team10"

if ! command -v kubectl &> /dev/null; then
  echo "Error: kubectl is not installed or not in PATH."
  exit 1
fi

if [ ! -f "$KUBECONFIG" ]; then
  echo "Error: Kubeconfig file '$KUBECONFIG' not found in current directory."
  exit 1
fi

echo "=========================================================="
echo " Conflux HQ — Connecting to Forge Cluster ($NAMESPACE)"
echo " Kubeconfig: $KUBECONFIG"
echo "=========================================================="

# Check pod status
POD_NAME=$(kubectl get pods -l app=conflux-app -n "$NAMESPACE" -o jsonpath="{.items[0].metadata.name}" 2>/dev/null || true)

if [ -z "$POD_NAME" ]; then
  echo "No active Conflux pod found in namespace $NAMESPACE."
  echo "Make sure the deployment has been started."
  exit 1
fi

POD_STATUS=$(kubectl get pod "$POD_NAME" -n "$NAMESPACE" -o jsonpath="{.status.phase}")
echo "Active Pod: $POD_NAME (Status: $POD_STATUS)"
echo "----------------------------------------------------------"
kubectl get pod "$POD_NAME" -n "$NAMESPACE"
echo "----------------------------------------------------------"

echo ""
echo "Choose an action:"
echo "  1) Forward BOTH Frontend (3000) & Backend (8000) to localhost"
echo "  2) Stream logs from Backend (FastAPI API server)"
echo "  3) Stream logs from Worker (Queue & MaaS investigation engine)"
echo "  4) Stream logs from Frontend (Next.js SSR)"
echo "  5) Exit"
echo ""
read -rp "Enter choice [1-5]: " CHOICE

case "$CHOICE" in
  1)
    echo "Starting dual port-forwarding on $POD_NAME..."
    echo "  -> Frontend: http://localhost:3000"
    echo "  -> Backend:  http://localhost:8000 (API Docs: http://localhost:8000/docs)"
    echo "Press Ctrl+C to stop port-forwarding."
    kubectl port-forward pod/"$POD_NAME" 3000:3000 8000:8000 -n "$NAMESPACE"
    ;;
  2)
    echo "Streaming logs from container: backend..."
    kubectl logs -f "$POD_NAME" -c backend -n "$NAMESPACE"
    ;;
  3)
    echo "Streaming logs from container: worker..."
    kubectl logs -f "$POD_NAME" -c worker -n "$NAMESPACE"
    ;;
  4)
    echo "Streaming logs from container: frontend..."
    kubectl logs -f "$POD_NAME" -c frontend -n "$NAMESPACE"
    ;;
  *)
    echo "Exiting."
    exit 0
    ;;
esac

