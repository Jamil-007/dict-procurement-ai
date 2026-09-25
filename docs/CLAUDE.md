# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is an AI-powered procurement document analysis system for Philippine Government Procurement (RA 12009). The application uses a multi-agent LangGraph pipeline to analyze procurement documents and provide compliance recommendations.

**Monorepo Structure:**
- `/backend` - Python FastAPI server with LangGraph agents
- `/frontend` - Next.js 14 TypeScript application

## Development Commands

### Backend (Python/FastAPI)

```bash
cd backend

# Setup virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env
# Edit .env with required API keys (ANTHROPIC_API_KEY or Vertex AI credentials)

# Run development server
uvicorn server:app --reload --port 8000

# Run with specific host
uvicorn server:app --reload --host 0.0.0.0 --port 8000
```

### Frontend (Next.js)

```bash
cd frontend

# Install dependencies
npm install

# Configure environment
cp .env.local.example .env.local
# Set NEXT_PUBLIC_API_URL to backend URL (default: http://localhost:8000)

# Run development server
npm run dev

# Build for production
npm run build

# Run production build
npm run start

# Lint code
npm run lint
```

## Architecture

### Backend: Multi-Agent LangGraph Pipeline

The backend implements a sophisticated multi-agent workflow using LangGraph:

**Entry Point:** `server.py`
- FastAPI application with SSE (Server-Sent Events) streaming
- CORS configured for frontend communication
- Key endpoints: `/analyze` (SSE), `/review`, `/chat`

**Agent Pipeline:** `graph.py` + `agents.py`

The workflow follows this pattern:
1. **PDF Parser** - Extracts text from uploaded procurement documents
2. **6 Parallel Analysis Agents** (fan-out):
   - Specification Validator
   - LCCA (Life Cycle Cost Analysis) Analyzer
   - Market Researcher
   - Sustainability Analyst
   - Domestic Preference Checker (Tatak Pinoy)
   - Modality Advisor (Compliance)
3. **Report Compiler** - Aggregates all analysis results (fan-in)
4. **Human-in-the-Loop** - Waits for user decision via `/review` endpoint
5. **Gamma Generator** - Optionally creates presentation slides

**State Management:**
- Uses LangGraph's `StateGraph` with `MemorySaver` for checkpointing
- State persists across human-in-the-loop interruptions
- Thread-based state tracking with `thread_id`

**LLM Configuration:** `config.py` + `utils/llm_factory.py`
- Supports both Vertex AI (Gemini) and Anthropic (Claude)
- Provider determined by `LLM_PROVIDER` environment variable
- Default models: `gemini-2.0-flash-exp` or `claude-3-5-sonnet-20241022`

**Prompts:** `prompts.py`
- All agent system prompts are centralized here
- Each agent has a detailed prompt with domain expertise

### Frontend: Next.js with Real-Time Updates

**Main Application:** `app/page.tsx`
- Client-side rendered page using custom hook `useProcurementAnalysis`
- Manages file upload, SSE connections, and user interactions

**State Hook:** `hooks/use-procurement-analysis.tsx`
- Centralized state management for entire analysis workflow
- Handles SSE connections for real-time agent updates
- Manages thinking logs, verdict data, chat messages

**Component Architecture:** `components/procurement/`
- `chat-layout.tsx` - Split view container
- `input-area.tsx` - File upload and message input
- `thinking-widget.tsx` - Real-time agent activity display
- `message-list.tsx` - Chat message history
- `report-preview.tsx` - Analysis verdict and findings display
- `verdict-card.tsx` - Pass/Fail verdict UI
- `file-upload.tsx` - File selection component

**Styling:**
- Tailwind CSS with custom configuration
- Radix UI components (`@radix-ui/*`)
- Framer Motion for animations
- `next-themes` for dark mode support

### Data Flow

1. User uploads PDF via frontend
2. Frontend calls `/analyze` endpoint with SSE connection
3. Backend runs LangGraph pipeline, streaming thinking logs via SSE
4. Parallel agents analyze document concurrently
5. Compiler agent synthesizes final verdict
6. Graph interrupts at human-in-the-loop node
7. User reviews verdict, chooses action via `/review` endpoint
8. Optionally generates Gamma presentation or enters chat mode
9. Chat mode uses `/chat` endpoint with document context

### API Models

All request/response models defined in `backend/models.py`:
- `AnalyzeResponse` - Initial analysis response with thread_id
- `VerdictData` - Final analysis verdict (PASS/FAIL, findings, confidence)
- `ReviewRequest` - User decision (generate_gamma or chat_only)
- `ChatRequest/ChatResponse` - Chat interaction models
- `ThinkingLog` - Real-time agent activity logs

## Key Technical Patterns

### SSE Streaming
Backend uses `sse-starlette` to stream real-time updates. Frontend connects via `EventSource` and handles these event types:
- `thinking` - Agent activity logs
- `verdict` - Final analysis result
- `complete` - Analysis finished
- `error` - Error occurred

### State Persistence
- Backend uses in-memory state by default (`STATE_STORAGE=memory`)
- Can be configured for SQLite or Postgres
- State keyed by `thread_id` (UUID4)
- File uploads stored in `backend/uploads/` directory

### LangGraph Human-in-the-Loop
Graph execution pauses after `report_compiler` using LangGraph's interrupt mechanism. Resume via:
```python
resume_graph(thread_id, user_decision)
```

### Parallel Agent Execution
LangGraph automatically parallelizes the 6 analysis agents using fan-out/fan-in pattern. Results merged using custom reducers in `AgentState`:
- `merge_analysis_results` - Deep merges analysis dictionaries
- `append_thinking_logs` - Concatenates logs from parallel execution

## Environment Configuration

### Required Backend Variables
- `LLM_PROVIDER` - "anthropic" or "vertex_ai"
- `ANTHROPIC_API_KEY` - For Claude models
- `TAVILY_API_KEY` - For market research agent

### Optional Backend Variables
- `GAMMA_API_KEY` - For presentation generation
- `GOOGLE_CLOUD_PROJECT` / `GOOGLE_CLOUD_LOCATION` / `GOOGLE_APPLICATION_CREDENTIALS` - For Vertex AI

### Frontend Variables
- `NEXT_PUBLIC_API_URL` - Backend API URL (default: http://localhost:8000)

## File Upload Handling

Currently supports single file upload. Issue #2 tracks adding multiple file upload support.

Upload flow:
1. File validated on frontend (PDF only)
2. Sent via multipart/form-data to `/analyze`
3. Backend saves to `uploads/{thread_id}/{filename}`
4. PDF parsed using PyMuPDF (`utils/pdf_parser.py`)
