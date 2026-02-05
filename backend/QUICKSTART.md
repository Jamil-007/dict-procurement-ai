# Quick Start Guide

## ✅ Your Configuration
- **LLM Provider**: Vertex AI (Google Gemini)
- **Model**: gemini-2.5-flash
- **Project**: ai-innov-474401
- **Region**: asia-southeast1
- **Service Account**: ✅ Found

## Setup Steps

### 1. Create Virtual Environment
```bash
cd backend
python3 -m venv venv
```

### 2. Activate Virtual Environment

**macOS/Linux:**
```bash
source venv/bin/activate
```

**Windows:**
```bash
venv\Scripts\activate
```

You should see `(venv)` appear in your terminal prompt.

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

This will install:
- FastAPI & Uvicorn (web server)
- LangGraph & LangChain (agent orchestration)
- langchain-google-vertexai (Gemini integration)
- PyMuPDF (PDF parsing)
- All other dependencies

### 4. Verify Setup
```bash
python test_setup.py
```

Expected output:
```
✅ All required files present
✅ Environment variables configured
✅ All dependencies installed
✅ LLM Provider: vertex_ai (gemini-2.5-flash)
✅ LLM initialized successfully
```

### 5. Start the Server
```bash
python main.py
```

Or:
```bash
uvicorn server:app --reload --port 8000
```

Server will run at: **http://localhost:8000**

### 6. Test the API

**Health Check:**
```bash
curl http://localhost:8000/health
```

**API Docs:**
Open in browser: http://localhost:8000/docs

## Important Notes

### Model Name Update
You've set `VERTEX_MODEL_NAME=gemini-2.5-flash`. Note that:

- ✅ If available: This will use Gemini 2.5 Flash
- ⚠️ If not available yet: You may need to use `gemini-2.0-flash-exp` instead

If you get a model error, update `.env`:
```env
VERTEX_MODEL_NAME=gemini-2.0-flash-exp
```

### Always Activate venv
Remember to activate the virtual environment every time you work on the backend:
```bash
cd backend
source venv/bin/activate  # macOS/Linux
```

### Deactivate When Done
```bash
deactivate
```

## Troubleshooting

### "command not found: python"
Use `python3` instead:
```bash
python3 main.py
```

### "ModuleNotFoundError"
Make sure:
1. Virtual environment is activated: `source venv/bin/activate`
2. Dependencies are installed: `pip install -r requirements.txt`

### "Model not found" or "Invalid model name"
Update to a stable model in `.env`:
```env
VERTEX_MODEL_NAME=gemini-2.0-flash-exp
```

### Permission Errors
Ensure your service account has the `aiplatform.user` role:
```bash
gcloud projects add-iam-policy-binding ai-innov-474401 \
  --member="serviceAccount:YOUR_SA@ai-innov-474401.iam.gserviceaccount.com" \
  --role="roles/aiplatform.user"
```

## Next Steps

1. ✅ Create venv: `python3 -m venv venv`
2. ✅ Activate: `source venv/bin/activate`
3. ⏳ Install: `pip install -r requirements.txt`
4. ⏳ Verify: `python test_setup.py`
5. ⏳ Run: `python main.py`
6. ⏳ Test: Upload a PDF via the API

## Full Command Sequence

```bash
# Navigate to backend
cd backend

# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Verify setup
python test_setup.py

# Start server
python main.py
```

Then visit http://localhost:8000/docs to see your API!
