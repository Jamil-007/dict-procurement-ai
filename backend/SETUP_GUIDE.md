# Backend Setup Guide

Step-by-step guide to get the procurement analysis backend running.

## Prerequisites

- Python 3.10 or higher
- pip (Python package manager)
- Anthropic API key (for development) or Google Cloud account (for production)

## Step 1: Install Dependencies

Navigate to the backend directory and install required packages:

```bash
cd backend
pip install -r requirements.txt
```

This will install:
- FastAPI (web framework)
- LangGraph (multi-agent orchestration)
- LangChain (LLM abstraction)
- PyMuPDF (PDF parsing)
- Pydantic (data validation)
- SSE-Starlette (server-sent events)
- And other dependencies

## Step 2: Configure Environment

Create your `.env` file from the example:

```bash
cp .env.example .env
```

### Option A: Use Anthropic (Recommended for Development)

Edit `.env` and set:

```env
LLM_PROVIDER=anthropic
ANTHROPIC_API_KEY=sk-ant-your-actual-api-key-here
```

To get an Anthropic API key:
1. Go to https://console.anthropic.com/
2. Sign up or log in
3. Navigate to API Keys
4. Create a new key

### Option B: Use Vertex AI (For Production)

Edit `.env` and set:

```env
LLM_PROVIDER=vertex_ai
GOOGLE_CLOUD_PROJECT=your-gcp-project-id
GOOGLE_CLOUD_LOCATION=us-central1
GOOGLE_APPLICATION_CREDENTIALS=./service-account-key.json
```

See README.md for detailed Vertex AI setup instructions.

### Optional: Add Tavily for Market Research

For enhanced market price analysis:

```env
TAVILY_API_KEY=tvly-your-api-key-here
```

Get a Tavily API key at: https://tavily.com/

## Step 3: Verify Setup

Run the setup verification script:

```bash
python test_setup.py
```

This will check:
- ✅ All required files exist
- ✅ Environment variables are configured
- ✅ Dependencies are installed
- ✅ LLM provider can be initialized

If all checks pass, you're ready to start the server!

## Step 4: Start the Server

### Method 1: Using main.py

```bash
python main.py
```

### Method 2: Using uvicorn directly

```bash
uvicorn server:app --reload --port 8000
```

The server will start on `http://localhost:8000`

## Step 5: Test the API

### Check Health

```bash
curl http://localhost:8000/health
```

Expected response:
```json
{
  "status": "ok",
  "llm_provider": "anthropic",
  "model": "claude-3-5-sonnet-20241022"
}
```

### View API Documentation

Open in browser:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

### Test File Upload

```bash
curl -X POST http://localhost:8000/analyze \
  -F "file=@your-sample.pdf" \
  -v
```

Expected response:
```json
{
  "thread_id": "123e4567-e89b-12d3-a456-426614174000",
  "status": "processing"
}
```

### Stream Analysis Progress

Open in browser or use curl:
```bash
curl -N http://localhost:8000/stream/{thread_id}
```

You'll see events like:
```
event: thinking_log
data: {"id":"...","agent":"PDF Parser","message":"Reading PDF structure...","timestamp":...,"status":"active"}

event: thinking_log
data: {"id":"...","agent":"Specification Validator","message":"Checking specification compliance...","timestamp":...,"status":"active"}

event: verdict
data: {"status":"PASS","title":"Compliant Procurement","confidence":85,"findings":[...]}

event: complete
data: {"status":"awaiting_review"}
```

## Troubleshooting

### Import Errors

If you see `ModuleNotFoundError`, ensure all dependencies are installed:
```bash
pip install -r requirements.txt --upgrade
```

### LLM Provider Errors

**"ANTHROPIC_API_KEY must be set"**
- Check your `.env` file has the correct API key
- Make sure there are no quotes around the key
- Verify the key is valid at https://console.anthropic.com/

**"GOOGLE_CLOUD_PROJECT must be set"**
- Switch to Anthropic for development: `LLM_PROVIDER=anthropic`
- Or follow Vertex AI setup in README.md

### Port Already in Use

If port 8000 is taken, use a different port:
```bash
uvicorn server:app --reload --port 8001
```

Update frontend to connect to the new port.

### PDF Upload Fails

**"Only PDF files are supported"**
- Ensure file has .pdf extension
- Check file is valid PDF format

**"Analysis failed"**
- Check server logs for detailed error
- Verify uploads/ directory is writable
- Ensure sufficient disk space

### Analysis Timeout

If analysis takes too long:
- Check your API key is valid and has credits
- Increase timeout in `server.py` (max_wait_time)
- Check network connectivity

## Next Steps

### Connect Frontend

Update frontend to point to your backend:

```typescript
// frontend/lib/api.ts
const API_URL = 'http://localhost:8000';
```

### Test with Real Documents

1. Prepare a sample procurement PDF
2. Upload via `/analyze` endpoint
3. Watch the SSE stream for progress
4. Review the verdict
5. Test the chat endpoint

### Deploy to Production

1. Switch to Vertex AI for better performance
2. Use PostgreSQL checkpointer instead of memory
3. Set up proper logging and monitoring
4. Configure production CORS origins
5. Use environment-specific .env files

## File Structure Reference

```
backend/
├── main.py              # Entry point
├── server.py            # API routes
├── graph.py             # LangGraph workflow
├── agents.py            # 8 agent implementations
├── prompts.py           # System prompts
├── models.py            # Pydantic schemas
├── config.py            # Settings
├── requirements.txt     # Dependencies
├── .env                 # Your configuration
├── .env.example         # Template
├── utils/
│   ├── llm_factory.py   # LLM abstraction
│   ├── pdf_parser.py    # PDF extraction
│   ├── storage.py       # File handling
│   └── gamma_client.py  # Gamma API (mock)
└── uploads/             # PDF storage (auto-created)
```

## Support

For issues:
1. Check this guide and README.md
2. Run `python test_setup.py` for diagnostics
3. Check server logs for errors
4. Verify API key is valid and has credits

## Success!

If everything is working:
- ✅ Server running on http://localhost:8000
- ✅ Health check returns OK
- ✅ Can upload PDFs
- ✅ SSE stream shows agent activity
- ✅ Verdict data is returned

You're ready to integrate with the frontend!
