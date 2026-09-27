#!/bin/bash
# Deploy the Procurement AI backend (FastAPI + agents/) to Cloud Run.
# Serves all agents in one service: doc_generation, feedback, analysis.
#
# Usage:  cd backend && ./deploy.sh
# Prereqs (already set up): Firestore DB "proc-feedback-bank" + vector index,
# Secret Manager secrets TAVILY_API_KEY and GAMMA_API_KEY, and the Cloud Run
# service account with roles/datastore.user + roles/aiplatform.user.
set -euo pipefail

PROJECT_ID="ai-innov-474401"
REGION="asia-southeast1"
SERVICE_NAME="procurement-ai-backend"

echo "🚀 Deploying backend -> ${SERVICE_NAME} (${REGION})..."

gcloud run deploy "${SERVICE_NAME}" \
  --source . \
  --project "${PROJECT_ID}" \
  --region "${REGION}" \
  --platform managed \
  --allow-unauthenticated \
  --set-env-vars "LLM_PROVIDER=vertex_ai,GOOGLE_CLOUD_PROJECT=${PROJECT_ID},GOOGLE_CLOUD_LOCATION=${REGION},VERTEX_MODEL_NAME=gemini-2.5-flash,STATE_STORAGE=memory,FEEDBACK_BANK_ENABLED=true,FEEDBACK_BACKEND=firestore,FIRESTORE_PROJECT=${PROJECT_ID},FEEDBACK_FIRESTORE_DATABASE=proc-feedback-bank,FIRESTORE_COLLECTION=feedback,EMBEDDING_MODEL=text-embedding-004" \
  --set-secrets "TAVILY_API_KEY=TAVILY_API_KEY:latest,GAMMA_API_KEY=GAMMA_API_KEY:latest" \
  --memory 2Gi \
  --cpu 2 \
  --timeout 300 \
  --max-instances 10 \
  --min-instances 0 \
  --concurrency 80

URL=$(gcloud run services describe "${SERVICE_NAME}" --region "${REGION}" --project "${PROJECT_ID}" --format 'value(status.url)')
echo "✅ Backend deployed: ${URL}"
echo "   Deploy the frontend next (frontend/deploy.sh) — it reads this URL automatically."
