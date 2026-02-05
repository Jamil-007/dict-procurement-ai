#!/bin/bash

# Backend Cloud Run Deployment Script (Using env.yaml)

PROJECT_ID="ai-innov-474401"
REGION="asia-southeast1"
SERVICE_NAME="procurement-ai-backend"

echo "🚀 Deploying Backend to Cloud Run (with env.yaml)..."

# Build and deploy
gcloud run deploy $SERVICE_NAME \
  --source . \
  --platform managed \
  --region $REGION \
  --project $PROJECT_ID \
  --allow-unauthenticated \
  --env-vars-file env.yaml \
  --memory 2Gi \
  --cpu 2 \
  --timeout 300 \
  --max-instances 10 \
  --min-instances 0 \
  --concurrency 80

echo "✅ Backend deployed!"
echo "Get the URL with: gcloud run services describe $SERVICE_NAME --region $REGION --format 'value(status.url)'"
