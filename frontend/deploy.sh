#!/bin/bash
# Deploy the Procurement AI frontend (Next.js) to Cloud Run as "procurement-ai".
# Automatically points the frontend at the deployed backend by baking
# NEXT_PUBLIC_API_URL in at build time (via Cloud Build + cloudbuild.yaml).
#
# Usage:  cd frontend && ./deploy.sh
# Deploy the BACKEND first (backend/deploy.sh) — this script reads its URL.
set -euo pipefail

PROJECT_ID="ai-innov-474401"
REGION="asia-southeast1"
SERVICE="procurement-ai"
BACKEND="procurement-ai-backend"

# 1) Find the backend URL (must already be deployed)
API_URL=$(gcloud run services describe "${BACKEND}" --region "${REGION}" --project "${PROJECT_ID}" --format 'value(status.url)' 2>/dev/null || true)
if [ -z "${API_URL}" ]; then
  echo "❌ Backend service '${BACKEND}' not found. Deploy it first: (cd ../backend && ./deploy.sh)"
  exit 1
fi
echo "🔗 Frontend will call backend at: ${API_URL}"

# 2) Ensure the Artifact Registry repo exists (idempotent)
gcloud artifacts repositories describe cloud-run-source-deploy \
  --location "${REGION}" --project "${PROJECT_ID}" >/dev/null 2>&1 || \
gcloud artifacts repositories create cloud-run-source-deploy \
  --repository-format=docker --location "${REGION}" --project "${PROJECT_ID}"

IMAGE="${REGION}-docker.pkg.dev/${PROJECT_ID}/cloud-run-source-deploy/${SERVICE}:latest"

# 3) Build (with the API URL baked in) + deploy via Cloud Build
echo "🚀 Building and deploying frontend -> ${SERVICE} (${REGION})..."
gcloud builds submit \
  --project "${PROJECT_ID}" \
  --config cloudbuild.yaml \
  --substitutions "_API_URL=${API_URL},_REGION=${REGION},_SERVICE=${SERVICE},_IMAGE=${IMAGE}" \
  .

URL=$(gcloud run services describe "${SERVICE}" --region "${REGION}" --project "${PROJECT_ID}" --format 'value(status.url)')
echo "✅ Frontend deployed: ${URL}"
echo "   NOTE: make sure the backend's CORS allows this origin (see server.py)."
