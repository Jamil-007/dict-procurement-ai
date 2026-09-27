#!/bin/bash
# Deploy the Procurement AI stack to Cloud Run.
#
# Two separate Cloud Run services live in project ai-innov-474401 (asia-southeast1):
#   - procurement-ai-backend  (FastAPI + agents)   -> backend/deploy.sh
#   - procurement-ai          (Next.js frontend)   -> frontend/deploy.sh
#
# Order matters: the backend must be deployed first. The frontend build bakes in
# NEXT_PUBLIC_API_URL by reading the backend's URL, so the backend has to exist
# before the frontend builds. frontend/deploy.sh fetches that URL automatically.
#
# Usage:
#   ./deploy.sh            # deploy both, backend first (full release)
#   ./deploy.sh backend    # deploy only the backend
#   ./deploy.sh frontend   # deploy only the frontend (uses existing backend URL)
#   ./deploy.sh both       # same as no argument
set -euo pipefail

# Run from the repo root regardless of where the script is invoked from.
cd "$(dirname "$0")"

TARGET="${1:-both}"

deploy_backend() {
  echo "════════════════════════════════════════"
  echo " Deploying BACKEND"
  echo "════════════════════════════════════════"
  (cd backend && ./deploy.sh)
}

deploy_frontend() {
  echo "════════════════════════════════════════"
  echo " Deploying FRONTEND"
  echo "════════════════════════════════════════"
  (cd frontend && ./deploy.sh)
}

case "${TARGET}" in
  backend)
    deploy_backend
    ;;
  frontend)
    deploy_frontend
    ;;
  both)
    deploy_backend    # must go first
    deploy_frontend   # reads the backend URL, bakes it in
    ;;
  *)
    echo "❌ Unknown target: '${TARGET}'"
    echo "   Usage: ./deploy.sh [backend|frontend|both]"
    exit 1
    ;;
esac

echo "✅ Done (${TARGET})."
