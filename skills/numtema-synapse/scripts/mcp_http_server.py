#!/usr/bin/env python3
"""HTTP / SSE server wrapper for Nümtema Synapse MCP.

Exposes:
- GET / and GET /health : Status and diagnostic JSON
- GET /mcp : Browser-friendly info page showing server status and tools
- POST /mcp & POST /jsonrpc : Standard MCP JSON-RPC 2.0 endpoint
- GET /sse : Server-Sent Events stream for remote MCP SSE clients (Claude, Cursor, etc.)
- POST /messages : Inbound messages endpoint for SSE sessions
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
import uuid
from pathlib import Path
from typing import Dict

# Add scripts directory to path
SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from fastapi import FastAPI, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse

from mcp_server import SynapseMCPServer, parse_message, SERVER_NAME, SERVER_VERSION, TOOLS

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

# Registry of active SSE client queues
sse_clients: Dict[str, asyncio.Queue] = {}


@app.get("/")
@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "server": SERVER_NAME,
        "version": SERVER_VERSION,
        "execution_allowed": ALLOW_EXECUTE,
        "transport": ["http_post", "sse"],
        "endpoints": {
            "mcp_post": "/mcp",
            "mcp_sse": "/sse",
            "messages": "/messages",
            "health": "/health"
        }
    }


@app.get("/mcp")
async def mcp_browser_view():
    """Browser landing page when someone visits /mcp via GET."""
    tools_html = "".join(
        f"<li><strong>{t['name']}</strong> ({t['title']})<br><small style='color:#666;'>{t['description']}</small></li>"
        for t in TOOLS
    )
    html_content = f"""
    <!DOCTYPE html>
    <html lang="fr">
    <head>
        <meta charset="utf-8">
        <title>{SERVER_NAME}</title>
        <style>
            body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; max-width: 750px; margin: 40px auto; padding: 20px; line-height: 1.6; background: #0b0f19; color: #f1f5f9; }}
            .card {{ background: #161e2e; border: 1px solid #2d3748; border-radius: 10px; padding: 24px; margin-bottom: 20px; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.5); }}
            h1 {{ margin-top: 0; color: #38bdf8; }}
            .badge {{ display: inline-block; padding: 4px 10px; border-radius: 9999px; font-size: 12px; font-weight: bold; background: #059669; color: white; }}
            ul {{ padding-left: 20px; }}
            li {{ margin-bottom: 12px; }}
            code {{ background: #0f172a; padding: 3px 6px; border-radius: 4px; font-size: 13px; color: #f43f5e; }}
        </style>
    </head>
    <body>
        <div class="card">
            <span class="badge">EN LIGNE & OPÉRATIONNEL</span>
            <h1>{SERVER_NAME} v{SERVER_VERSION}</h1>
            <p>Ce serveur MCP est opérationnel et prêt à recevoir des requêtes JSON-RPC 2.0.</p>
            <p><strong>Note :</strong> Dans un navigateur web, la page s'affiche en <code>GET</code>. Les clients MCP (Claude Desktop, Cursor, n8n, etc.) envoient des requêtes <code>POST</code>.</p>
        </div>
        <div class="card">
            <h3>Configuration client MCP :</h3>
            <p><strong>URL SSE :</strong> <code>https://synapse.coolify.dallico.com/sse</code></p>
            <p><strong>URL HTTP POST directe :</strong> <code>https://synapse.coolify.dallico.com/mcp</code></p>
        </div>
        <div class="card">
            <h3>Outils disponibles ({len(TOOLS)}) :</h3>
            <ul>{tools_html}</ul>
        </div>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)


@app.post("/mcp")
@app.post("/jsonrpc")
async def handle_mcp_post(request: Request):
    """MCP JSON-RPC 2.0 direct HTTP POST endpoint."""
    body = await request.body()
    result = parse_message(body, mcp_engine)
    if result is None:
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    return JSONResponse(content=result)


# --- MCP Server-Sent Events (SSE) Transport ---

@app.get("/sse")
async def sse_endpoint(request: Request):
    """SSE transport endpoint for MCP clients like Claude Desktop / Cursor."""
    session_id = str(uuid.uuid4())
    queue: asyncio.Queue = asyncio.Queue()
    sse_clients[session_id] = queue

    async def event_generator():
        # First send the endpoint event with the URI where client must send POST messages
        endpoint_uri = f"/messages?session_id={session_id}"
        yield f"event: endpoint\ndata: {endpoint_uri}\n\n"
        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    data = await asyncio.wait_for(queue.get(), timeout=20.0)
                    yield f"event: message\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"
                except asyncio.TimeoutError:
                    # Keep-alive comment
                    yield ": keepalive\n\n"
        finally:
            sse_clients.pop(session_id, None)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


@app.post("/messages")
async def handle_sse_messages(request: Request, session_id: str):
    """Client POST endpoint for sending messages to an active SSE session."""
    queue = sse_clients.get(session_id)
    if not queue:
        return JSONResponse(
            status_code=status.HTTP_404_NOT_FOUND,
            content={"error": "Session not found or expired"}
        )
    body = await request.body()
    result = parse_message(body, mcp_engine)
    if result is not None:
        await queue.put(result)
    return Response(status_code=status.HTTP_202_ACCEPTED)


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run("mcp_http_server:app", host="0.0.0.0", port=port, reload=False)
