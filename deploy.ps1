# deploy.ps1
# Single-command deploy of the Procurement AI PROTOTYPE to Cloud Run
# (Eliana's demo setup) in project ai-innov-474401 / asia-southeast1.
#
#   Backend  -> procurement-ai-backend   (Firestore proc-ai-staging,
#               GCS proc-ai-staging-files, feedback bank unified on proc-ai-staging)
#   Frontend -> procurement-ai           (https://procurement-ai-rgkvi7273a-as.a.run.app)
#
# Builds from the working tree, so uncommitted + unpushed changes are included.
# Does NOT touch the *-staging services -- those deploy via
# .github/workflows/deploy-staging.yml on push to main (do not push this branch to main).
# No secrets stored here -- TAVILY/GAMMA come from Secret Manager at runtime. Safe to commit.
#
# Usage:
#   .\deploy.ps1                    # backend then frontend
#   .\deploy.ps1 -Service backend
#   .\deploy.ps1 -Service frontend

param(
  [ValidateSet('backend', 'frontend', 'all')]
  [string]$Service = 'all'
)

Set-StrictMode -Version Latest
# 'Continue', not 'Stop': gcloud is a native command that writes progress/info to
# stderr, which under 'Stop' PowerShell turns into a terminating NativeCommandError
# even on success. Real failures are caught explicitly via $LASTEXITCODE + throw below.
$ErrorActionPreference = 'Continue'

# --- Config (no secrets) ---------------------------------------------------------
$PROJECT      = "ai-innov-474401"
$REGION       = "asia-southeast1"
$BACKEND_SVC  = "procurement-ai-backend"
$FRONTEND_SVC = "procurement-ai"
$FIRESTORE_DB = "proc-ai-staging"       # records, knowledge AND feedback (unified)
$GCS_BUCKET   = "proc-ai-staging-files" # uploaded docs + durable RAG index

# --- Helpers ---------------------------------------------------------------------
function Get-BackendUrl {
  $url = gcloud run services describe $BACKEND_SVC --region $REGION --project $PROJECT --format "value(status.url)" 2>$null
  return ($url | Out-String).Trim()
}

# --- Service functions -----------------------------------------------------------
function Deploy-Backend {
  Write-Host "`n=== Backend preflight: Firestore '$FIRESTORE_DB' must exist ===" -ForegroundColor Cyan
  gcloud firestore databases describe --database $FIRESTORE_DB --project $PROJECT 1>$null 2>$null
  if ($LASTEXITCODE -ne 0) {
    throw "Firestore DB '$FIRESTORE_DB' not found in $PROJECT. Create it (Native mode, $REGION) before deploying."
  }

  Write-Host "`n=== Backend: build + deploy -> $BACKEND_SVC ===" -ForegroundColor Cyan
  # Pinned to a single always-on instance on purpose: the legacy /analyze path
  # keeps LangGraph state in an in-process MemorySaver. Uploads + the RAG index
  # are durable in GCS, so raise max-instances only once that state moves too.
  gcloud run deploy $BACKEND_SVC `
    --source ./backend `
    --platform managed `
    --region $REGION `
    --project $PROJECT `
    --allow-unauthenticated `
    --set-env-vars "LLM_PROVIDER=vertex_ai" `
    --set-env-vars "GOOGLE_CLOUD_PROJECT=$PROJECT" `
    --set-env-vars "GOOGLE_CLOUD_LOCATION=$REGION" `
    --set-env-vars "VERTEX_MODEL_NAME=gemini-2.5-flash" `
    --set-env-vars "STATE_STORAGE=memory" `
    --set-env-vars "STORE_BACKEND=firestore" `
    --set-env-vars "FIRESTORE_DATABASE=$FIRESTORE_DB" `
    --set-env-vars "GCS_BUCKET=$GCS_BUCKET" `
    --set-env-vars "FEEDBACK_BANK_ENABLED=true" `
    --set-env-vars "FEEDBACK_BACKEND=firestore" `
    --set-env-vars "FIRESTORE_PROJECT=$PROJECT" `
    --set-env-vars "FEEDBACK_FIRESTORE_DATABASE=$FIRESTORE_DB" `
    --set-env-vars "FIRESTORE_COLLECTION=feedback" `
    --set-env-vars "EMBEDDING_MODEL=text-embedding-004" `
    --set-secrets "TAVILY_API_KEY=TAVILY_API_KEY:latest,GAMMA_API_KEY=GAMMA_API_KEY:latest" `
    --memory 2Gi `
    --cpu 2 `
    --timeout 300 `
    --max-instances 1 `
    --min-instances 1 `
    --concurrency 80
  if ($LASTEXITCODE -ne 0) { throw "Backend deploy failed." }
  Write-Host "Backend deployed: $(Get-BackendUrl)" -ForegroundColor Green
}

function Deploy-Frontend {
  $apiUrl = Get-BackendUrl
  if (-not $apiUrl) {
    throw "Backend service '$BACKEND_SVC' not found. Deploy the backend first: .\deploy.ps1 -Service backend"
  }
  Write-Host "`n=== Frontend will call backend at: $apiUrl ===" -ForegroundColor Cyan

  # Ensure the Artifact Registry repo used by cloudbuild.yaml exists (idempotent).
  # Cloud Run --source deploys auto-create this repo, so it usually already exists.
  gcloud artifacts repositories describe cloud-run-source-deploy --location $REGION --project $PROJECT 2>&1 | Out-Null
  if ($LASTEXITCODE -ne 0) {
    Write-Host "Creating Artifact Registry repo cloud-run-source-deploy..." -ForegroundColor Yellow
    gcloud artifacts repositories create cloud-run-source-deploy `
      --repository-format=docker --location $REGION --project $PROJECT 2>&1 | Out-Null
    if ($LASTEXITCODE -ne 0) { throw "Could not create Artifact Registry repo cloud-run-source-deploy." }
  }

  $image = "$REGION-docker.pkg.dev/$PROJECT/cloud-run-source-deploy/${FRONTEND_SVC}:latest"

  Write-Host "`n=== Frontend: build (bakes NEXT_PUBLIC_API_URL) + deploy -> $FRONTEND_SVC ===" -ForegroundColor Cyan
  gcloud builds submit ./frontend `
    --config frontend/cloudbuild.yaml `
    --project $PROJECT `
    --substitutions "_API_URL=$apiUrl,_REGION=$REGION,_SERVICE=$FRONTEND_SVC,_IMAGE=$image"
  if ($LASTEXITCODE -ne 0) { throw "Frontend build/deploy failed." }

  $furl = gcloud run services describe $FRONTEND_SVC --region $REGION --project $PROJECT --format "value(status.url)"
  Write-Host "Frontend deployed: $($furl.Trim())" -ForegroundColor Green
}

# --- Main ------------------------------------------------------------------------
Write-Host "Project: $PROJECT   Region: $REGION   Target: $Service" -ForegroundColor DarkCyan

switch ($Service) {
  'backend'  { Deploy-Backend }
  'frontend' { Deploy-Frontend }
  'all'      { Deploy-Backend; Deploy-Frontend }   # backend first: frontend bakes in its URL
}

Write-Host "`nDeploy complete ($Service)." -ForegroundColor Green
