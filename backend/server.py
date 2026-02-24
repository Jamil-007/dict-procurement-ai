"""
FastAPI server with routes for procurement analysis.
Implements SSE streaming, human-in-the-loop workflow, and chat.
"""

import asyncio
import json
import time
import uuid
from typing import Any, AsyncGenerator, List
from fastapi import FastAPI, UploadFile, HTTPException, File, Request
from fastapi.middleware.cors import CORSMiddleware
from sse_starlette.sse import EventSourceResponse
from models import (
    AnalyzeResponse,
    ReviewRequest,
    ReviewResponse,
    ChatRequest,
    ChatResponse,
)
from utils.storage import save_uploaded_files, generate_thread_id, file_exists
from utils.llm_factory import get_llm, get_llm_info
from graph import graph, create_initial_state
from prompts import CHAT_PROMPT
from config import settings


app = FastAPI(
    title="Procurement Analysis API",
    description="AI-powered procurement document analysis for Philippine Government Procurement (RA 12009)",
    version="1.0.0",
)

# Configure CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://dict-procurement-ai-5o1j.vercel.app",
        "https://dict-procurement-ai.vercel.app",
        "http://localhost:3000",
        "http://localhost:3001",
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)

# Store for tracking background tasks
analysis_tasks = {}


def _extract_text_from_chunk_content(content: Any) -> str:
    """Normalize provider-specific chunk content into plain text."""
    if content is None:
        return ""

    if isinstance(content, str):
        return content

    if isinstance(content, list):
        return "".join(_extract_text_from_chunk_content(item) for item in content)

    if isinstance(content, dict):
        text = content.get("text")
        if isinstance(text, str):
            return text

        nested_content = content.get("content")
        if nested_content is not None:
            return _extract_text_from_chunk_content(nested_content)

        return ""

    return str(content)


def _extract_text_from_stream_chunk(chunk: Any) -> str:
    """Extract text from LangChain stream chunk payloads."""
    if chunk is None:
        return ""

    content = getattr(chunk, "content", chunk)
    return _extract_text_from_chunk_content(content)


def _build_chat_prompt(thread_id: str, query: str) -> str:
    """Validate chat state and build prompt for chat endpoints."""
    if not file_exists(thread_id):
        raise HTTPException(status_code=404, detail="Analysis session not found")

    config = {"configurable": {"thread_id": thread_id}}
    state_snapshot = graph.get_state(config)

    if not state_snapshot or not state_snapshot.values:
        raise HTTPException(status_code=404, detail="State not found")

    state = state_snapshot.values
    parsed_text = state.get("parsed_text", "")
    compiled_report = state.get("compiled_report", "")

    if not parsed_text:
        raise HTTPException(status_code=400, detail="Document not yet analyzed")

    return CHAT_PROMPT.format(
        parsed_text=parsed_text[: settings.CHAT_PARSED_TEXT_LIMIT],
        compiled_report=compiled_report,
        query=query,
    )


@app.get("/health")
async def health_check():
    """Health check endpoint with LLM provider info."""
    llm_info = get_llm_info()
    return {
        "status": "ok",
        "llm_provider": llm_info["provider"],
        "model": llm_info["model"],
    }


@app.post("/analyze", response_model=AnalyzeResponse)
async def analyze_document(files: List[UploadFile] = File(...)):
    """
    Upload PDF and initiate analysis.

    Args:
        files: PDF file uploads

    Returns:
        thread_id and status for tracking analysis
    """
    if not files:
        raise HTTPException(status_code=400, detail="At least one PDF file is required")

    if len(files) > 3:
        raise HTTPException(status_code=400, detail="Maximum of 3 PDF files allowed")

    for uploaded_file in files:
        if not uploaded_file.filename or not uploaded_file.filename.lower().endswith(
            ".pdf"
        ):
            raise HTTPException(status_code=400, detail="Only PDF files are supported")

        # Validate content type
        content_type = uploaded_file.content_type or ""
        if content_type and not content_type.startswith("application/pdf"):
            raise HTTPException(status_code=400, detail="Invalid file content type")

    try:
        # Generate unique thread ID
        thread_id = generate_thread_id()

        # Save uploaded files
        file_payloads = []
        for uploaded_file in files:
            file_content = await uploaded_file.read()
            file_payloads.append((uploaded_file.filename, file_content))
        pdf_paths = await save_uploaded_files(file_payloads, thread_id)

        # Create initial state
        initial_state = create_initial_state(thread_id, pdf_paths)

        # Start graph execution in background
        config = {"configurable": {"thread_id": thread_id}}
        asyncio.create_task(run_graph_async(initial_state, config, thread_id))

        return AnalyzeResponse(thread_id=thread_id, status="processing")

    except ValueError as e:
        # ValueError from storage validation - sanitize error message
        error_msg = str(e)
        # Don't expose file paths
        if "path" in error_msg.lower() or "/" in error_msg or "\\" in error_msg:
            error_msg = "Invalid file format or size"
        raise HTTPException(status_code=400, detail=error_msg)
    except Exception as e:
        # Log the actual error but return generic message
        print(f"Analysis error: {str(e)}")
        raise HTTPException(
            status_code=500, detail="Analysis failed. Please try again."
        )


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
                    analysis_tasks[thread_id] = {
                        "status": "running",
                        "state": result_state,
                    }

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
            "state": initial_state,
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
                    "data": json.dumps({"error": "Analysis timeout"}),
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
                            yield {"event": "thinking_log", "data": json.dumps(log)}
                            # Small delay between logs to allow UI to render each state
                            await asyncio.sleep(0.1)
                        last_log_index = len(thinking_logs)

                    # Check if analysis is complete (reached interrupt or end)
                    if state.get("compiled_report"):
                        # Stream verdict
                        try:
                            verdict = json.loads(state["compiled_report"])
                            yield {"event": "verdict", "data": json.dumps(verdict)}

                            # Analysis complete, waiting for review
                            yield {
                                "event": "complete",
                                "data": json.dumps({"status": "awaiting_review"}),
                            }
                            break

                        except json.JSONDecodeError:
                            yield {
                                "event": "error",
                                "data": json.dumps({"error": "Invalid verdict format"}),
                            }
                            break

                # Check background task status
                task_info = analysis_tasks.get(thread_id, {})
                if task_info.get("status") == "error":
                    yield {
                        "event": "error",
                        "data": json.dumps(
                            {"error": task_info.get("error", "Unknown error")}
                        ),
                    }
                    break

            except Exception as e:
                yield {"event": "error", "data": json.dumps({"error": str(e)})}
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
        generate_gamma = request.action == "generate_gamma"

        # Resume graph execution
        config = {"configurable": {"thread_id": request.thread_id}}

        # Update state with decision
        state = graph.get_state(config)
        if not state:
            raise HTTPException(status_code=404, detail="State not found")

        updated_state = state.values.copy()
        updated_state["generate_gamma"] = generate_gamma

        # Continue graph execution
        result = await asyncio.to_thread(lambda: graph.invoke(updated_state, config))

        if generate_gamma and result.get("gamma_link"):
            return ReviewResponse(status="complete", gamma_link=result["gamma_link"])
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
    try:
        # Validate and sanitize query
        query = request.query.strip()
        if not query:
            raise HTTPException(status_code=400, detail="Query cannot be empty")

        prompt = _build_chat_prompt(request.thread_id, query)
        llm = get_llm()
        response = await asyncio.to_thread(lambda: llm.invoke(prompt))
        answer = response.content if hasattr(response, "content") else str(response)

        return ChatResponse(response=answer)

    except HTTPException:
        raise
    except Exception as e:
        # Don't expose internal error details
        print(f"Chat error: {str(e)}")
        raise HTTPException(status_code=500, detail="Chat request failed")


@app.post("/chat/stream")
async def stream_chat_about_document(chat_request: ChatRequest, http_request: Request):
    """
    Stream chat response chunks for progressive UI rendering.
    """
    try:
        # Validate and sanitize query
        query = chat_request.query.strip()
        if not query:
            raise HTTPException(status_code=400, detail="Query cannot be empty")

        prompt = _build_chat_prompt(chat_request.thread_id, query)
    except HTTPException:
        raise
    except Exception as e:
        print(f"Chat stream error: {str(e)}")
        raise HTTPException(status_code=500, detail="Chat request failed")

    async def event_generator() -> AsyncGenerator[dict, None]:
        message_id = str(uuid.uuid4())
        timestamp_ms = int(time.time() * 1000)
        full_response_parts: List[str] = []

        try:
            llm = get_llm()

            yield {
                "event": "chat_start",
                "data": json.dumps(
                    {
                        "message_id": message_id,
                        "timestamp": timestamp_ms,
                    }
                ),
            }

            async for chunk in llm.astream(prompt):
                if await http_request.is_disconnected():
                    break

                delta = _extract_text_from_stream_chunk(chunk)
                if not delta:
                    continue

                full_response_parts.append(delta)
                yield {
                    "event": "chat_delta",
                    "data": json.dumps(
                        {
                            "message_id": message_id,
                            "delta": delta,
                        }
                    ),
                }

            if not await http_request.is_disconnected():
                final_response = "".join(full_response_parts)
                yield {
                    "event": "chat_complete",
                    "data": json.dumps(
                        {
                            "message_id": message_id,
                            "response": final_response,
                            "timestamp": int(time.time() * 1000),
                        }
                    ),
                }

        except Exception as e:
            yield {
                "event": "error",
                "data": json.dumps(
                    {
                        "message_id": message_id if message_id else None,
                        "error": str(e),
                    }
                ),
            }

    return EventSourceResponse(event_generator())


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
        "thinking_logs_count": len(state.get("thinking_logs", [])),
    }
