#!/bin/bash
# Deploy the Procurement AI backend (FastAPI + agents/) to Cloud Run.
# One service serves every agent: analysis/review, knowledge hub, doc_generation,
# and the feedback bank.
#
# Usage:  cd backend && ./deploy.sh
#
# This is the single source of truth for the backend's deployed configuration.
# (Older split scripts deploy-backend.sh / deploy-backend-simple.sh were removed;
# their configs are reconciled here.)
set -euo pipefail

PROJECT_ID="ai-innov-474401"
REGION="asia-southeast1"
SERVICE_NAME="procurement-ai-backend"

# --- Databases -------------------------------------------------------------
# Records / Knowledge Hub live in their own Firestore Native DB; the feedback
# bank lives in a SEPARATE one so the two subsystems never share data.
RECORDS_DB="procurement-agent-db"   # STORE_BACKEND=firestore reads FIRESTORE_DATABASE (see config.py)
FEEDBACK_DB="proc-feedback-bank"    # feedback bank reads FEEDBACK_FIRESTORE_DATABASE

# --- Uploaded document storage --------------------------------------------
# Empty = files stay on the container's local disk (wiped on redeploy, and not
# shared across instances — which is why this service runs a single instance).
# To persist uploaded files, create/keep the bucket AND grant the runtime
# service account roles/storage.objectAdmin on it, then set:
#   GCS_BUCKET="ai-procurement"
GCS_BUCKET=""

# --- Preflight: fail early, with a fix, instead of deploying a broken service.
# A missing DB lets the service start and then 500 on every request that touches
# storage — which looks like an app bug. Catch it here.
for DB in "$RECORDS_DB" "$FEEDBACK_DB"; do
  if ! gcloud firestore databases describe --database="$DB" \
       --project="$PROJECT_ID" >/dev/null 2>&1; then
    echo "❌ Firestore database '$DB' does not exist in $PROJECT_ID ($REGION)."
    echo "   Create it (Native mode, $REGION) before deploying:"
    echo "     gcloud firestore databases create --database=$DB \\"
    echo "       --location=$REGION --type=firestore-native --project=$PROJECT_ID"
    echo "   The feedback bank DB also needs a vector index on 'embedding' (COSINE)."
    echo "   See System Overview.md §10 and HANDOVER.md."
    exit 1
  fi
done

# Build the env-var list. GCS_BUCKET only included when set (empty = local disk).
ENV_VARS="LLM_PROVIDER=vertex_ai"
ENV_VARS="${ENV_VARS},GOOGLE_CLOUD_PROJECT=${PROJECT_ID}"
ENV_VARS="${ENV_VARS},GOOGLE_CLOUD_LOCATION=${REGION}"
ENV_VARS="${ENV_VARS},VERTEX_MODEL_NAME=gemini-2.5-flash"
ENV_VARS="${ENV_VARS},STATE_STORAGE=memory"
# Records / Knowledge Hub persistence
ENV_VARS="${ENV_VARS},STORE_BACKEND=firestore"
ENV_VARS="${ENV_VARS},FIRESTORE_DATABASE=${RECORDS_DB}"
# Feedback bank
ENV_VARS="${ENV_VARS},FEEDBACK_BANK_ENABLED=true"
ENV_VARS="${ENV_VARS},FEEDBACK_BACKEND=firestore"
ENV_VARS="${ENV_VARS},FIRESTORE_PROJECT=${PROJECT_ID}"
ENV_VARS="${ENV_VARS},FEEDBACK_FIRESTORE_DATABASE=${FEEDBACK_DB}"
ENV_VARS="${ENV_VARS},FIRESTORE_COLLECTION=feedback"
ENV_VARS="${ENV_VARS},EMBEDDING_MODEL=text-embedding-004"
if [ -n "${GCS_BUCKET}" ]; then
  ENV_VARS="${ENV_VARS},GCS_BUCKET=${GCS_BUCKET}"
fi

echo "🚀 Deploying backend -> ${SERVICE_NAME} (${REGION})..."

# Pinned to a single always-on instance ON PURPOSE. The ProcAI analyst (legacy
# /analyze) path keeps LangGraph state in an in-process MemorySaver, and uploaded
# files sit on local disk unless GCS_BUCKET is set — so a second instance would
# serve 404s for threads/files it never saw. Raise max-instances only once BOTH
# that state and uploads live in Firestore/GCS.
gcloud run deploy "${SERVICE_NAME}" \
  --source . \
  --project "${PROJECT_ID}" \
  --region "${REGION}" \
  --platform managed \
  --allow-unauthenticated \
  --set-env-vars "${ENV_VARS}" \
  --set-secrets "TAVILY_API_KEY=TAVILY_API_KEY:latest,GAMMA_API_KEY=GAMMA_API_KEY:latest" \
  --memory 2Gi \
  --cpu 2 \
  --timeout 300 \
  --min-instances 1 \
  --max-instances 1 \
  --concurrency 80

URL=$(gcloud run services describe "${SERVICE_NAME}" --region "${REGION}" --project "${PROJECT_ID}" --format 'value(status.url)')
echo "✅ Backend deployed: ${URL}"
echo "   Deploy the frontend next (frontend/deploy.sh) — it reads this URL automatically."
