#!/bin/bash

# Frontend Cloud Run Deployment Script

PROJECT_ID="ai-innov-474401"
REGION="asia-southeast1"
SERVICE_NAME="procurement-ai-frontend"
BACKEND_URL="" # Will be set after backend deployment

echo "🚀 Deploying Frontend to Cloud Run..."

# Check if backend URL is provided
if [ -z "$BACKEND_URL" ]; then
  echo "⚠️  BACKEND_URL not set. Please update this script with your backend URL."
  echo "Example: BACKEND_URL=https://procurement-ai-backend-xxx.run.app"
  exit 1
fi

# Build and deploy
gcloud run deploy $SERVICE_NAME \
  --source . \
  --platform managed \
  --region $REGION \
  --project $PROJECT_ID \
  --allow-unauthenticated \
  --set-env-vars "NEXT_PUBLIC_API_URL=$BACKEND_URL" \
  --memory 512Mi \
  --cpu 1 \
  --timeout 60 \
  --max-instances 10 \
  --min-instances 0 \
  --concurrency 80

echo "✅ Frontend deployed!"
echo "Get the URL with: gcloud run services describe $SERVICE_NAME --region $REGION --format 'value(status.url)'"
