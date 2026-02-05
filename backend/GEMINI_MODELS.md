# Gemini Model Selection Guide

## Current Configuration
✅ **Provider**: Vertex AI
✅ **Project**: ai-innov-474401
✅ **Location**: asia-southeast1
✅ **Model**: gemini-2.0-flash-exp (default)

## Available Gemini Models

### Gemini 2.0 Flash (Recommended for Development)
- **Model Name**: `gemini-2.0-flash-exp`
- **Speed**: Fastest (2x faster than 1.5)
- **Cost**: Lowest
- **Use Case**: Development, testing, high-volume analysis
- **Best For**: This procurement analysis system

### Gemini 1.5 Pro
- **Model Name**: `gemini-1.5-pro-002`
- **Speed**: Slower but more capable
- **Cost**: Higher
- **Use Case**: Complex reasoning, detailed analysis
- **Best For**: When you need maximum accuracy

### Gemini 1.5 Flash
- **Model Name**: `gemini-1.5-flash-002`
- **Speed**: Balanced
- **Cost**: Medium
- **Use Case**: Production workloads
- **Best For**: Balanced performance/cost

## How to Change Models

Edit your `.env` file:

```env
# For fastest processing (recommended)
VERTEX_MODEL_NAME=gemini-2.0-flash-exp

# For best quality
VERTEX_MODEL_NAME=gemini-1.5-pro-002

# For balanced performance
VERTEX_MODEL_NAME=gemini-1.5-flash-002
```

## Current Setup

Your `.env` is configured with:
```env
LLM_PROVIDER=vertex_ai
GOOGLE_CLOUD_PROJECT=ai-innov-474401
GOOGLE_CLOUD_LOCATION=asia-southeast1
GOOGLE_APPLICATION_CREDENTIALS=./service-account-key.json
VERTEX_MODEL_NAME=gemini-2.0-flash-exp
```

## Verify Your Setup

Run the verification script:
```bash
python test_setup.py
```

Expected output:
```
✅ LLM Provider: vertex_ai (gemini-2.0-flash-exp)
✅ LLM initialized successfully
```

## Cost Estimates (Philippines Region)

| Model | Input (per 1M tokens) | Output (per 1M tokens) |
|-------|----------------------|------------------------|
| Gemini 2.0 Flash | ~$0.075 | ~$0.30 |
| Gemini 1.5 Flash | ~$0.075 | ~$0.30 |
| Gemini 1.5 Pro | ~$1.25 | ~$5.00 |

**Estimated cost per analysis**:
- With Flash: $0.01 - $0.05 per document
- With Pro: $0.10 - $0.50 per document

## Troubleshooting

### "Failed to initialize LLM"
Check that:
1. Service account key exists: `ls service-account-key.json`
2. API is enabled: `gcloud services enable aiplatform.googleapis.com`
3. Location is correct: `asia-southeast1` is supported

### "Model not found"
The model name must exactly match:
- ✅ `gemini-2.0-flash-exp`
- ❌ `gemini-2.5-flash-002` (doesn't exist yet)
- ❌ `gemini-flash-2.0` (wrong format)

### Permission Errors
Ensure your service account has the role:
```bash
gcloud projects add-iam-policy-binding ai-innov-474401 \
  --member="serviceAccount:YOUR_SERVICE_ACCOUNT@ai-innov-474401.iam.gserviceaccount.com" \
  --role="roles/aiplatform.user"
```

## Recommendations

### For Development
Use **Gemini 2.0 Flash** (`gemini-2.0-flash-exp`):
- Fastest iteration
- Lowest cost
- Great quality for procurement analysis

### For Production
Start with **Gemini 1.5 Flash** (`gemini-1.5-flash-002`):
- More stable than experimental models
- Good balance of speed and quality
- Production-ready

### For Critical Analysis
Use **Gemini 1.5 Pro** (`gemini-1.5-pro-002`):
- Maximum accuracy
- Better at complex reasoning
- Worth the cost for important decisions

## Next Steps

1. Verify setup: `python test_setup.py`
2. Start server: `python main.py`
3. Test health: `curl http://localhost:8000/health`
4. Upload a test PDF and see Gemini in action!
