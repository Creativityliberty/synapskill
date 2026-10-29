#!/usr/bin/env python3
"""HTTP / SSE server wrapper for Nümtema Synapse MCP.

Exposes JSON-RPC 2.0 endpoint for MCP over HTTP POST, plus health check and SSE compatibility.
Safe by default with configurable opt-in execution via SYNAPSE_ALLOW_EXECUTE.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

# Add scripts directory to path
SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from fastapi import FastAPI, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from mcp_server import SynapseMCPServer, parse_message, SERVER_NAME, SERVER_VERSION

# Configuration via environment variables
ALLOW_EXECUTE = os.getenv("SYNAPSE_ALLOW_EXECUTE", "true").lower() in ("1", "true", "yes")
STATE_DB = Path(os.getenv("SYNAPSE_STATE_DB", "state/receipts.sqlite")) if os.getenv("SYNAPSE_STATE_DB") else None
LESSONS_DB = Path(os.getenv("SYNAPSE_LESSONS_DB", "state/lessons.sqlite")) if os.getenv("SYNAPSE_LESSONS_DB") else None
MAX_CALLS = int(os.getenv("SYNAPSE_MAX_CALLS_PER_MIN", "300"))

# Ensure state directory exists if sqlite db is used
if STATE_DB and STATE_DB.parent:
    STATE_DB.parent.mkdir(parents=True, exist_ok=True)
if LESSONS_DB and LESSONS_DB.parent:
    LESSONS_DB.parent.mkdir(parents=True, exist_ok=True)

mcp_engine = SynapseMCPServer(
    allow_execute=ALLOW_EXECUTE,
    state_db=STATE_DB,
    lessons_db=LESSONS_DB,
    max_calls_per_minute=MAX_CALLS
)

app = FastAPI(
    title="Nümtema Synapse MCP Server",
    description="HTTP endpoint for Synapse Cognitive OS MCP tools",
    version=SERVER_VERSION
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "server": SERVER_NAME,
        "version": SERVER_VERSION,
        "execution_allowed": ALLOW_EXECUTE
    }


@app.post("/mcp")
@app.post("/jsonrpc")
async def handle_mcp_post(request: Request):
    """MCP JSON-RPC 2.0 HTTP transport endpoint."""
    body = await request.body()
    result = parse_message(body, mcp_engine)
    if result is None:
        # JSON-RPC Notification (no response needed)
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    return JSONResponse(content=result)


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run("mcp_http_server:app", host="0.0.0.0", port=port, reload=False)
