"""
FastAPI application — exposes the Countries Agent over HTTP.

Endpoints
---------
GET  /              → Serve the frontend UI
GET  /api/health    → Liveness probe
POST /api/query     → Run the agent and return a structured response
"""

from __future__ import annotations

import logging
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field

from agent.graph import get_graph
from agent.state import initial_state

# ── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger(__name__)

# ── FastAPI app ───────────────────────────────────────────────────────────────
app = FastAPI(
    title="Countries Agent API",
    description="LangGraph-powered AI agent that answers questions about countries.",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

_STATIC_DIR = Path(__file__).parent.parent / "static"


# ── Pydantic schemas ──────────────────────────────────────────────────────────


class QueryRequest(BaseModel):
    query: str = Field(
        ...,
        min_length=3,
        max_length=500,
        description="Natural-language question about a country.",
        examples=["What is the population of Germany?"],
    )


class QueryResponse(BaseModel):
    query: str
    answer: Optional[str]
    country_name: Optional[str]
    requested_fields: List[str]
    steps: List[str]
    error: Optional[str]
    duration_ms: float
    success: bool


class HealthResponse(BaseModel):
    status: str
    version: str


# ── Endpoints ─────────────────────────────────────────────────────────────────


@app.get("/", include_in_schema=False)
async def serve_frontend():
    """Serve the React/HTML frontend."""
    index = _STATIC_DIR / "index.html"
    if index.exists():
        return FileResponse(str(index))
    return JSONResponse({"message": "Countries Agent API is running. See /docs for the API."})


@app.get("/api/health", response_model=HealthResponse, tags=["meta"])
async def health():
    """Liveness probe — returns 200 when the service is up."""
    return HealthResponse(status="ok", version="1.0.0")


@app.post("/api/query", response_model=QueryResponse, tags=["agent"])
async def run_query(body: QueryRequest, request: Request):
    """
    Run the Countries Agent for the given natural-language query.

    The agent executes three LangGraph nodes in sequence:
    1. **identify** — extract country name and requested fields
    2. **fetch**    — call the REST Countries API
    3. **synthesize** — produce a grounded natural-language answer

    Returns the final answer plus a step-by-step trace of the workflow.
    """
    client_ip = request.client.host if request.client else "unknown"
    logger.info("POST /api/query | ip=%s | query=%r", client_ip, body.query)

    t0 = time.perf_counter()

    state = initial_state(body.query)
    graph = get_graph()

    try:
        result = await graph.ainvoke(state)
    except Exception as exc:
        logger.exception("Unhandled error during graph execution")
        raise HTTPException(status_code=500, detail=f"Internal agent error: {exc}") from exc

    duration_ms = (time.perf_counter() - t0) * 1000
    success = result.get("error") is None and result.get("answer") is not None

    logger.info(
        "Query completed | success=%s duration_ms=%.0f answer_len=%s",
        success,
        duration_ms,
        len(result.get("answer") or ""),
    )

    return QueryResponse(
        query=body.query,
        answer=result.get("answer"),
        country_name=result.get("country_name"),
        requested_fields=result.get("requested_fields", []),
        steps=result.get("steps", []),
        error=result.get("error"),
        duration_ms=round(duration_ms, 1),
        success=success,
    )


# ── Global exception handler ──────────────────────────────────────────────────


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.exception("Unhandled exception | path=%s", request.url.path)
    return JSONResponse(
        status_code=500,
        content={"detail": "An unexpected error occurred. Please try again."},
    )
