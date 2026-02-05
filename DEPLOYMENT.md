# Cloud Run Deployment Guide

This guide explains how to deploy the Procurement AI application to Google Cloud Run with separate backend and frontend services.

## Architecture

```
┌─────────────────┐         ┌─────────────────┐
│  Frontend       │────────▶│  Backend        │
│  (Next.js)      │         │  (FastAPI)      │
│  Cloud Run      │         │  Cloud Run      │
└─────────────────┘         └─────────────────┘
        │                           │
        │                           │
        ▼                           ▼
    Users                   Vertex AI, Tavily, Gamma
```

## Prerequisites

1. **Google Cloud Project** (already have: `ai-innov-474401`)
2. **gcloud CLI** installed and authenticated
3. **Docker** installed locally (for testing)
4. **APIs Enabled**:
   ```bash
   gcloud services enable run.googleapis.com
   gcloud services enable cloudbuild.googleapis.com
   gcloud services enable secretmanager.googleapis.com
   ```

## Step 1: Store Secrets in Secret Manager

```bash
# Store Tavily API Key
echo -n "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" | \
  gcloud secrets create TAVILY_API_KEY --data-file=-

# Store Gamma API Key
echo -n "sk-gamma-hflkS65h5JJG9DdnjwJaMonFYPyOXxBQanAfWdbg4" | \
  gcloud secrets create GAMMA_API_KEY --data-file=-
```

## Step 2: Deploy Backend

```bash
cd backend

# Make the deploy script executable
chmod +x deploy-backend.sh

# Deploy
./deploy-backend.sh
```

**Or manually:**

```bash
gcloud run deploy procurement-ai-backend \
  --source . \
  --platform managed \
  --region asia-southeast1 \
  --project ai-innov-474401 \
  --allow-unauthenticated \
  --set-env-vars "LLM_PROVIDER=vertex_ai" \
  --set-env-vars "GOOGLE_CLOUD_PROJECT=ai-innov-474401" \
  --set-env-vars "GOOGLE_CLOUD_LOCATION=asia-southeast1" \
  --set-env-vars "VERTEX_MODEL_NAME=gemini-2.5-flash" \
  --set-secrets "TAVILY_API_KEY=TAVILY_API_KEY:latest" \
  --set-secrets "GAMMA_API_KEY=GAMMA_API_KEY:latest" \
  --memory 2Gi \
  --cpu 2 \
  --timeout 300 \
  --max-instances 10
```

**Get the backend URL:**

```bash
gcloud run services describe procurement-ai-backend \
  --region asia-southeast1 \
  --format 'value(status.url)'
```

Save this URL - you'll need it for the frontend!

## Step 3: Deploy Frontend

1. **Update the deploy script** with your backend URL:

```bash
cd frontend

# Edit deploy-frontend.sh and set BACKEND_URL
nano deploy-frontend.sh
# BACKEND_URL="https://procurement-ai-backend-xxx-as.a.run.app"
```

2. **Deploy:**

```bash
chmod +x deploy-frontend.sh
./deploy-frontend.sh
```

**Or manually:**

```bash
gcloud run deploy procurement-ai-frontend \
  --source . \
  --platform managed \
  --region asia-southeast1 \
  --project ai-innov-474401 \
  --allow-unauthenticated \
  --set-env-vars "NEXT_PUBLIC_API_URL=https://YOUR-BACKEND-URL" \
  --memory 512Mi \
  --cpu 1 \
  --timeout 60 \
  --max-instances 10
```

## Step 4: Configure CORS

Update `backend/server.py` to allow your frontend domain:

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "https://procurement-ai-frontend-xxx-as.a.run.app"  # Add your frontend URL
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

Redeploy backend after updating CORS.

## Step 5: Test the Deployment

1. Visit your frontend URL
2. Upload a PDF
3. Check that analysis works
4. Test Gamma report generation

## Monitoring & Logs

**View logs:**

```bash
# Backend logs
gcloud run services logs read procurement-ai-backend --region asia-southeast1

# Frontend logs
gcloud run services logs read procurement-ai-frontend --region asia-southeast1
```

**Monitor metrics:**

```bash
# Go to Cloud Console
https://console.cloud.google.com/run?project=ai-innov-474401
```

## Cost Optimization

### Current Configuration:

**Backend:**
- Memory: 2GB
- CPU: 2
- Min instances: 0 (scales to zero)
- Max instances: 10

**Frontend:**
- Memory: 512MB
- CPU: 1
- Min instances: 0 (scales to zero)
- Max instances: 10

### Estimated Costs (Light Usage):
- **Idle (no traffic)**: $0/month (scales to zero)
- **~1000 requests/day**: ~$5-10/month
- **~10,000 requests/day**: ~$30-50/month

## Troubleshooting

### Backend won't start:
```bash
# Check logs
gcloud run services logs read procurement-ai-backend --region asia-southeast1 --limit 50

# Common issues:
# - Missing secrets → Check Secret Manager
# - Timeout → Increase timeout in deploy script
# - Memory → Increase memory allocation
```

### Frontend can't reach backend:
```bash
# Check environment variables
gcloud run services describe procurement-ai-frontend --region asia-southeast1

# Verify NEXT_PUBLIC_API_URL is set correctly
# Update CORS in backend to allow frontend domain
```

### SSE (Server-Sent Events) not working:
- Cloud Run supports SSE with timeout up to 300s
- Increase timeout if needed: `--timeout 300`

## Alternative: Frontend on Vercel

If you want better performance for the frontend:

1. **Deploy backend to Cloud Run** (as above)
2. **Deploy frontend to Vercel**:
   ```bash
   cd frontend
   vercel --prod
   ```
3. **Set environment variable on Vercel**:
   ```
   NEXT_PUBLIC_API_URL=https://your-backend-url.run.app
   ```

Benefits:
- Better CDN/edge performance
- Faster cold starts
- Free for most usage

## Update Deployment

```bash
# Backend update
cd backend
./deploy-backend.sh

# Frontend update
cd frontend
./deploy-frontend.sh
```

## Rollback

```bash
# List revisions
gcloud run revisions list --service procurement-ai-backend --region asia-southeast1

# Rollback to previous revision
gcloud run services update-traffic procurement-ai-backend \
  --to-revisions REVISION_NAME=100 \
  --region asia-southeast1
```

## Production Checklist

- [ ] Secrets stored in Secret Manager (not in env vars)
- [ ] CORS configured with production domains
- [ ] Service account with minimal permissions
- [ ] Cloud Logging enabled
- [ ] Cloud Monitoring alerts set up
- [ ] Budget alerts configured
- [ ] Custom domain configured (optional)
- [ ] SSL certificate (automatic with Cloud Run)

## Custom Domain (Optional)

```bash
# Map custom domain
gcloud run domain-mappings create \
  --service procurement-ai-frontend \
  --domain your-domain.com \
  --region asia-southeast1
```

## Support

For issues:
1. Check Cloud Run logs
2. Verify environment variables
3. Test locally with Docker first
4. Check Cloud Run quotas and limits
