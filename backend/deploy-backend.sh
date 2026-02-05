#!/bin/bash

# Backend Cloud Run Deployment Script

PROJECT_ID="ai-innov-474401"
REGION="asia-southeast1"
SERVICE_NAME="procurement-ai-backend"

echo "🚀 Deploying Backend to Cloud Run..."

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
  --set-secrets "TAVILY_API_KEY=TAVILY_API_KEY:latest" \
  --set-secrets "GAMMA_API_KEY=GAMMA_API_KEY:latest" \
  --memory 2Gi \
  --cpu 2 \
  --timeout 300 \
  --max-instances 10 \
  --min-instances 0 \
  --concurrency 80

echo "✅ Backend deployed!"
echo "Get the URL with: gcloud run services describe $SERVICE_NAME --region $REGION --format 'value(status.url)'"
