"""
FastAPI server with routes for procurement analysis.
Implements SSE streaming, human-in-the-loop workflow, and chat.
"""

import asyncio
import json
from typing import AsyncGenerator
from fastapi import FastAPI, UploadFile, HTTPException, File
from fastapi.middleware.cors import CORSMiddleware
from sse_starlette.sse import EventSourceResponse
from models import (
    AnalyzeResponse,
    VerdictData,
    ReviewRequest,
    ReviewResponse,
    ChatRequest,
    ChatResponse,
    ErrorResponse,
)
from utils.storage import save_uploaded_file, generate_thread_id, file_exists, get_file_path
from utils.llm_factory import get_llm, get_llm_info
from graph import graph, create_initial_state, get_state, resume_graph
from prompts import CHAT_PROMPT


app = FastAPI(
    title="Procurement Analysis API",
    description="AI-powered procurement document analysis for Philippine Government Procurement (RA 12009)",
    version="1.0.0"
)

# Configure CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://dict-procurement-ai-5o1j.vercel.app", "https://dict-procurement-ai.vercel.app","http://localhost:3000", "http://localhost:3001"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Store for tracking background tasks
analysis_tasks = {}


@app.get("/health")
async def health_check():
    """Health check endpoint with LLM provider info."""
    llm_info = get_llm_info()
    return {
        "status": "ok",
        "llm_provider": llm_info["provider"],
        "model": llm_info["model"]
    }


@app.post("/analyze", response_model=AnalyzeResponse)
async def analyze_document(file: UploadFile = File(...)):
    """
    Upload PDF and initiate analysis.

    Args:
        file: PDF file upload

    Returns:
        thread_id and status for tracking analysis
    """
    # Validate file type
    if not file.filename.endswith('.pdf'):
        raise HTTPException(status_code=400, detail="Only PDF files are supported")

    try:
        # Generate unique thread ID
        thread_id = generate_thread_id()

        # Save uploaded file
        file_content = await file.read()
        pdf_path = await save_uploaded_file(file_content, thread_id)

        # Create initial state
        initial_state = create_initial_state(thread_id, pdf_path)

        # Start graph execution in background
        config = {"configurable": {"thread_id": thread_id}}
        asyncio.create_task(run_graph_async(initial_state, config, thread_id))

        return AnalyzeResponse(thread_id=thread_id, status="processing")

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")


async def run_graph_async(initial_state, config, thread_id):
    """Run graph execution asynchronously with streaming."""
    def stream_graph():
        """Execute graph in sync context with streaming."""
        result_state = initial_state
        try:
            for chunk in graph.stream(initial_state, config, stream_mode="updates"):
                # Each chunk contains node updates
                if chunk:
                    # Update result state
                    for node_name, node_state in chunk.items():
                        result_state = {**result_state, **node_state}

                    # Store updated state so SSE can pick it up
                    analysis_tasks[thread_id] = {"status": "running", "state": result_state}

            return result_state
        except Exception as e:
            raise e

    try:
        analysis_tasks[thread_id] = {"status": "running", "state": initial_state}

        # Run streaming in thread pool
        result = await asyncio.to_thread(stream_graph)

        analysis_tasks[thread_id] = {"status": "interrupted", "state": result}

    except Exception as e:
        analysis_tasks[thread_id] = {
            "status": "error",
            "error": str(e),
            "state": initial_state
        }


@app.get("/stream/{thread_id}")
async def stream_analysis(thread_id: str):
    """
    Stream analysis progress via Server-Sent Events.

    Args:
        thread_id: Analysis session identifier

    Returns:
        SSE stream with thinking logs and verdict
    """
    if not file_exists(thread_id):
        raise HTTPException(status_code=404, detail="Analysis session not found")

    async def event_generator() -> AsyncGenerator[str, None]:
        """Generate SSE events for analysis progress."""
        last_log_index = 0
        max_wait_time = 300  # 5 minutes timeout
        start_time = asyncio.get_event_loop().time()

        while True:
            # Check timeout
            if asyncio.get_event_loop().time() - start_time > max_wait_time:
                yield {
                    "event": "error",
                    "data": json.dumps({"error": "Analysis timeout"})
                }
                break

            # Get current state
            config = {"configurable": {"thread_id": thread_id}}
            try:
                state_snapshot = graph.get_state(config)

                if state_snapshot and state_snapshot.values:
                    state = state_snapshot.values
                    thinking_logs = state.get("thinking_logs", [])

                    # Stream new thinking logs with slight delay for UI rendering
                    if len(thinking_logs) > last_log_index:
                        for log in thinking_logs[last_log_index:]:
                            yield {
                                "event": "thinking_log",
                                "data": json.dumps(log)
                            }
                            # Small delay between logs to allow UI to render each state
                            await asyncio.sleep(0.1)
                        last_log_index = len(thinking_logs)

                    # Check if analysis is complete (reached interrupt or end)
                    if state.get("compiled_report"):
                        # Stream verdict
                        try:
                            verdict = json.loads(state["compiled_report"])
                            yield {
                                "event": "verdict",
                                "data": json.dumps(verdict)
                            }

                            # Analysis complete, waiting for review
                            yield {
                                "event": "complete",
                                "data": json.dumps({"status": "awaiting_review"})
                            }
                            break

                        except json.JSONDecodeError:
                            yield {
                                "event": "error",
                                "data": json.dumps({"error": "Invalid verdict format"})
                            }
                            break

                # Check background task status
                task_info = analysis_tasks.get(thread_id, {})
                if task_info.get("status") == "error":
                    yield {
                        "event": "error",
                        "data": json.dumps({"error": task_info.get("error", "Unknown error")})
                    }
                    break

            except Exception as e:
                yield {
                    "event": "error",
                    "data": json.dumps({"error": str(e)})
                }
                break

            # Wait before next poll
            await asyncio.sleep(0.5)

    return EventSourceResponse(event_generator())


@app.post("/review", response_model=ReviewResponse)
async def review_decision(request: ReviewRequest):
    """
    Human-in-the-loop decision: generate Gamma or chat only.

    Args:
        request: Review decision with thread_id and action

    Returns:
        Status and optional Gamma link
    """
    if not file_exists(request.thread_id):
        raise HTTPException(status_code=404, detail="Analysis session not found")

    try:
        generate_gamma = (request.action == "generate_gamma")

        # Resume graph execution
        config = {"configurable": {"thread_id": request.thread_id}}

        # Update state with decision
        state = graph.get_state(config)
        if not state:
            raise HTTPException(status_code=404, detail="State not found")

        updated_state = state.values.copy()
        updated_state["generate_gamma"] = generate_gamma

        # Continue graph execution
        result = await asyncio.to_thread(
            lambda: graph.invoke(updated_state, config)
        )

        if generate_gamma and result.get("gamma_link"):
            return ReviewResponse(
                status="complete",
                gamma_link=result["gamma_link"]
            )
        else:
            return ReviewResponse(status="complete", gamma_link=None)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Review failed: {str(e)}")


@app.post("/chat", response_model=ChatResponse)
async def chat_about_document(request: ChatRequest):
    """
    Chat about the analyzed document using full context.

    Args:
        request: Chat query with thread_id

    Returns:
        AI response based on document and analysis
    """
    if not file_exists(request.thread_id):
        raise HTTPException(status_code=404, detail="Analysis session not found")

    try:
        # Retrieve state
        config = {"configurable": {"thread_id": request.thread_id}}
        state_snapshot = graph.get_state(config)

        if not state_snapshot or not state_snapshot.values:
            raise HTTPException(status_code=404, detail="State not found")

        state = state_snapshot.values

        # Build context from parsed text and compiled report
        parsed_text = state.get("parsed_text", "")
        compiled_report = state.get("compiled_report", "")

        if not parsed_text:
            raise HTTPException(status_code=400, detail="Document not yet analyzed")

        # Get LLM and invoke with context
        llm = get_llm()
        prompt = CHAT_PROMPT.format(
            parsed_text=parsed_text[:50000],  # Limit context size
            compiled_report=compiled_report,
            query=request.query
        )

        response = await asyncio.to_thread(lambda: llm.invoke(prompt))
        answer = response.content if hasattr(response, 'content') else str(response)

        return ChatResponse(response=answer)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Chat failed: {str(e)}")


@app.get("/status/{thread_id}")
async def get_analysis_status(thread_id: str):
    """
    Get current status of an analysis session.

    Args:
        thread_id: Analysis session identifier

    Returns:
        Current status and available data
    """
    if not file_exists(thread_id):
        raise HTTPException(status_code=404, detail="Analysis session not found")

    config = {"configurable": {"thread_id": thread_id}}
    state_snapshot = graph.get_state(config)

    if not state_snapshot or not state_snapshot.values:
        return {"status": "not_started", "thread_id": thread_id}

    state = state_snapshot.values

    return {
        "thread_id": thread_id,
        "status": "complete" if state.get("compiled_report") else "processing",
        "has_verdict": bool(state.get("compiled_report")),
        "has_gamma": bool(state.get("gamma_link")),
        "thinking_logs_count": len(state.get("thinking_logs", []))
    }
