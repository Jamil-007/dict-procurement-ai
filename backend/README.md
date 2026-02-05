# Procurement Analysis Backend

AI-powered procurement document analysis system using FastAPI, LangGraph, and multi-agent architecture.

## Features

- **Multi-Agent Analysis**: 6 specialized agents analyze procurement documents in parallel
- **Human-in-the-Loop**: Interrupt workflow for human review before generating reports
- **Real-Time Streaming**: Server-Sent Events for live progress updates
- **Philippine Law Focus**: Specialized in RA 12009 compliance
- **Flexible LLM**: Support for both Vertex AI (Gemini) and Anthropic (Claude)

## Quick Start

### 1. Install Dependencies

```bash
cd backend
pip install -r requirements.txt
```

### 2. Configure Environment

Copy the example environment file and configure your settings:

```bash
cp .env.example .env
```

Edit `.env` with your API keys:

```env
# Use Anthropic for development
LLM_PROVIDER=anthropic
ANTHROPIC_API_KEY=your-anthropic-api-key-here

# Optional: Tavily for market research
TAVILY_API_KEY=your-tavily-api-key-here
```

### 3. Run the Server

```bash
python main.py
```

Or using uvicorn directly:

```bash
uvicorn server:app --reload --port 8000
```

The API will be available at `http://localhost:8000`

## API Documentation

Once running, visit:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

## API Endpoints

### POST /analyze
Upload PDF and start analysis.

**Request**: `multipart/form-data` with PDF file

**Response**:
```json
{
  "thread_id": "uuid-string",
  "status": "processing"
}
```

### GET /stream/{thread_id}
Server-Sent Events stream for real-time progress.

**Events**:
- `thinking_log`: Agent activity updates
- `verdict`: Final analysis results
- `complete`: Analysis finished
- `error`: Error occurred

### POST /review
Human decision after analysis.

**Request**:
```json
{
  "thread_id": "uuid-string",
  "action": "generate_gamma" | "chat_only"
}
```

**Response**:
```json
{
  "status": "complete",
  "gamma_link": "https://gamma.app/..." // if action was generate_gamma
}
```

### POST /chat
Chat about the analyzed document.

**Request**:
```json
{
  "thread_id": "uuid-string",
  "query": "What are the main findings?"
}
```

**Response**:
```json
{
  "response": "Based on the analysis..."
}
```

### GET /health
Health check and LLM provider info.

**Response**:
```json
{
  "status": "ok",
  "llm_provider": "anthropic",
  "model": "claude-3-5-sonnet-20241022"
}
```

## Architecture

### Multi-Agent Pipeline

1. **PDF Parser** - Extract text from PDF
2. **Parallel Analysis** (6 agents):
   - Specification Validator
   - Lifecycle Cost Analyzer
   - Market Researcher (with Tavily)
   - Sustainability Analyst
   - Domestic Preference Checker
   - Modality Advisor
3. **Report Compiler** - Aggregate findings
4. **[INTERRUPT]** - Human review
5. **Gamma Generator** - Optional presentation

### State Management

LangGraph manages state with in-memory checkpointing:
- Each session has unique `thread_id`
- State persists during analysis
- Human-in-the-loop interrupt points
- Resumable execution after decisions

## Configuration

### LLM Providers

**Anthropic (Development)**:
```env
LLM_PROVIDER=anthropic
ANTHROPIC_API_KEY=sk-ant-...
```

**Vertex AI (Production)**:
```env
LLM_PROVIDER=vertex_ai
GOOGLE_CLOUD_PROJECT=your-project-id
GOOGLE_CLOUD_LOCATION=us-central1
GOOGLE_APPLICATION_CREDENTIALS=./service-account-key.json
```

### Tavily (Market Research)

```env
TAVILY_API_KEY=tvly-...
```

Without Tavily, market analysis uses document content only.

### Gamma (Presentations)

```env
GAMMA_API_KEY=your-gamma-key
```

Currently mocked - returns placeholder URLs.

## Development

### Project Structure

```
backend/
├── main.py              # Entry point
├── server.py            # FastAPI routes
├── graph.py             # LangGraph workflow
├── agents.py            # Agent implementations
├── prompts.py           # System prompts
├── models.py            # Pydantic models
├── config.py            # Configuration
├── utils/
│   ├── llm_factory.py   # LLM provider abstraction
│   ├── pdf_parser.py    # PDF extraction
│   ├── storage.py       # File handling
│   └── gamma_client.py  # Gamma API (mock)
└── uploads/             # PDF storage
```

### Testing

```bash
# Health check
curl http://localhost:8000/health

# Upload PDF
curl -X POST http://localhost:8000/analyze \
  -F "file=@sample.pdf"

# Stream progress (in browser or with curl)
curl http://localhost:8000/stream/{thread_id}
```

### Adding New Agents

1. Define prompt in `prompts.py`
2. Implement agent function in `agents.py`
3. Add node to graph in `graph.py`
4. Update state schema if needed

## Philippine Procurement Law (RA 12009)

All agents are specialized in:
- Specification compliance
- Competitive procurement principles
- Domestic preference (Section 79)
- Lifecycle costing
- Procurement modalities
- Green procurement

## Error Handling

- Invalid PDFs return 400 errors
- Missing sessions return 404 errors
- LLM failures gracefully fallback
- Analysis errors included in findings

## Deployment

### Docker (Coming Soon)

```dockerfile
FROM python:3.11
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Environment Variables for Production

- Use PostgreSQL for state persistence
- Configure proper CORS origins
- Set appropriate timeouts
- Enable logging and monitoring

## Troubleshooting

### "LLM_PROVIDER not configured"
Set `LLM_PROVIDER=anthropic` in `.env` and add your API key.

### "No such file or directory: uploads/"
The directory is created automatically, but check file permissions.

### "Analysis timeout"
Increase `max_wait_time` in `server.py` stream endpoint.

### "Memory usage too high"
Switch from `MemorySaver()` to SQLite or PostgreSQL checkpointer.

## License

Internal use only - DICT Procurement AI System
