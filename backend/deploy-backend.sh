#!/bin/bash

# Backend Cloud Run Deployment Script

PROJECT_ID="ai-innov-474401"
REGION="asia-southeast1"
SERVICE_NAME="procurement-ai-backend"
FIRESTORE_DB="proc-ai-staging"
BUCKET="proc-ai-staging-files"

set -e

# Preflight. Without these the service starts cleanly and then fails on every
# request that touches storage, which looks like an application bug.
#
#   1. The database must exist. Create it as Native mode in $REGION. Pointing
#      at (default) or procurement-agent-db is writing into another team's data.
#   2. The runtime service account needs roles/datastore.user on the project and
#      roles/storage.objectAdmin on gs://$BUCKET.
if ! gcloud firestore databases describe --database="$FIRESTORE_DB" \
     --project="$PROJECT_ID" >/dev/null 2>&1; then
  echo "❌ Firestore database '$FIRESTORE_DB' does not exist in $PROJECT_ID."
  echo "   Create it (Native mode, $REGION) before deploying, or records will"
  echo "   fail to save. See System Overview.md §10."
  exit 1
fi

echo "🚀 Deploying Backend to Cloud Run..."

# Pinned to a single always-on instance on purpose. The ProcAI analyst path
# keeps its LangGraph state in an in-process MemorySaver and its uploads on the
# container's local disk, so a second instance serves 404s for threads it has
# never seen. Raise max-instances only once that state lives in Firestore/GCS.
#
# Build and deploy
gcloud run deploy $SERVICE_NAME \
  --source . \
  --platform managed \
  --region $REGION \
  --project $PROJECT_ID \
  --allow-unauthenticated \
  --set-env-vars "LLM_PROVIDER=vertex_ai" \
  --set-env-vars "GOOGLE_CLOUD_PROJECT=$PROJECT_ID" \
  --set-env-vars "GOOGLE_CLOUD_LOCATION=$REGION" \
  --set-env-vars "VERTEX_MODEL_NAME=gemini-2.5-flash" \
  --set-env-vars "STATE_STORAGE=memory" \
  --set-env-vars "STORE_BACKEND=firestore" \
  --set-env-vars "FIRESTORE_DATABASE=$FIRESTORE_DB" \
  --set-env-vars "GCS_BUCKET=$BUCKET" \
  --set-secrets "TAVILY_API_KEY=TAVILY_API_KEY:latest" \
  --set-secrets "GAMMA_API_KEY=GAMMA_API_KEY:latest" \
  --memory 2Gi \
  --cpu 2 \
  --timeout 300 \
  --max-instances 1 \
  --min-instances 1 \
  --concurrency 80

echo "✅ Backend deployed!"
echo "Get the URL with: gcloud run services describe $SERVICE_NAME --region $REGION --format 'value(status.url)'"
