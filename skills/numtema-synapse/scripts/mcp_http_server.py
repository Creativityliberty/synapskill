#!/usr/bin/env python3
"""Nümtema Synapse HTTP/SSE transport: intentionally anonymous, four-tool public facade.

Both POST /mcp and legacy GET /sse + POST /messages share PublicSynapseMCPServer.
The more capable six-tool stdio server is NOT exposed over the network.
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
import uuid
from pathlib import Path
from urllib.parse import urlsplit

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse

SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from mcp_server import (SERVER_NAME, MAX_MESSAGE_BYTES, SERVER_VERSION as MCP_VERSION,
                        TOOLS, parse_message)
from public_mcp_policy import PublicSynapseMCPServer, PUBLIC_TOOL_NAMES

MAX_CALLS = min(max(int(os.getenv('SYNAPSE_MAX_CALLS_PER_MIN', '60')), 1), 1000)
MAX_SSE_CLIENTS = 32
WEB_ASSETS = SCRIPTS_DIR / "web_ui"


def _allowed_origins():
    origins = [o.strip() for o in os.getenv('SYNAPSE_ALLOWED_ORIGINS', '').split(',') if o.strip()]
    for origin in origins:
        parsed = urlsplit(origin)
        if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password or parsed.path or parsed.query or parsed.fragment:
            raise ValueError('SYNAPSE_ALLOWED_ORIGINS requires exact HTTPS origins')
    return tuple(origins)


ALLOWED_ORIGINS = _allowed_origins()
mcp_engine = PublicSynapseMCPServer(max_calls_per_minute=MAX_CALLS)
app = FastAPI(title='Nümtema Synapse MCP PUBLIC', version='0.4.2',
              description='Anonymous planning and validation tools only')
app.mount("/assets", StaticFiles(directory=str(WEB_ASSETS)), name="synapse-assets")
app.add_middleware(CORSMiddleware, allow_origins=list(ALLOWED_ORIGINS),
                   allow_credentials=False, allow_methods=['GET', 'POST'],
                   allow_headers=['Content-Type', 'Accept', 'MCP-Protocol-Version', 'Mcp-Method', 'Mcp-Name'])

# Session identifiers are transport handles, NOT authentication or a grant of permission.
sse_clients: dict[str, asyncio.Queue] = {}


@app.middleware('http')
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers['Cache-Control'] = 'no-store'
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['Referrer-Policy'] = 'no-referrer'
    response.headers['Content-Security-Policy'] = (
        "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; "
        "font-src 'self'; connect-src 'self'; object-src 'none'; base-uri 'none'; "
        "form-action 'none'; frame-ancestors 'none'"
    )
    return response


def _origin_denied(request: Request) -> bool:
    origin = request.headers.get('origin')
    if origin is None:
        return False
    # Browser POST requests include Origin even when they come from this page.
    # Compare exact scheme and authority, using Host because Coolify terminates TLS.
    parsed = urlsplit(origin)
    host = request.headers.get('host', '')
    is_exact_origin = (parsed.scheme in ('https', 'http')
                       and parsed.netloc.lower() == host.lower()
                       and not any((parsed.path, parsed.query, parsed.fragment,
                                    parsed.username, parsed.password)))
    return not (is_exact_origin or origin in ALLOWED_ORIGINS)



async def _read_limited(request: Request) -> bytes | None:
    """Limit consumed body, including when Content-Length is missing or forged."""
    try:
        stated = int(request.headers.get('content-length', '0'))
    except ValueError:
        return None
    if stated > MAX_MESSAGE_BYTES or stated < 0:
        return None
    chunks = []
    length = 0
    async for chunk in request.stream():
        length += len(chunk)
        if length > MAX_MESSAGE_BYTES:
            return None
        chunks.append(chunk)
    return b''.join(chunks)


@app.get('/')
@app.get('/health')
async def health_check():
    return {'status': 'healthy', 'server': SERVER_NAME, 'version': '0.4.2',
            'execution_allowed': False, 'public_tools': len(PUBLIC_TOOL_NAMES),
            'transport': ['http_post', 'sse'],
            'endpoints': {'mcp_post': '/mcp', 'mcp_sse': '/sse', 'messages': '/messages', 'health': '/health'}}


@app.get('/mcp')
async def mcp_browser_view():
    """Static, accessible status and tools page; independent of JSON-RPC POST."""
    return HTMLResponse((WEB_ASSETS / "index.html").read_text(encoding="utf-8"))


@app.post('/mcp')
@app.post('/jsonrpc')
async def handle_mcp_post(request: Request):
    if _origin_denied(request):
        return JSONResponse({'error': 'Origin not allowed'}, status_code=403)
    body = await _read_limited(request)
    if body is None:
        return JSONResponse({'error': 'Request exceeds size limit or invalid Content-Length'}, status_code=413)
    result = parse_message(body, mcp_engine)
    if result is None:
        return Response(status_code=204)
    return JSONResponse(content=result)


@app.get('/sse')
async def sse_endpoint(request: Request):
    if _origin_denied(request):
        return JSONResponse({'error': 'Origin not allowed'}, status_code=403)
    if len(sse_clients) >= MAX_SSE_CLIENTS:
        return JSONResponse({'error': 'Too many SSE clients'}, status_code=429)
    session_id = str(uuid.uuid4())
    queue: asyncio.Queue = asyncio.Queue(maxsize=16)
    sse_clients[session_id] = queue

    async def event_generator():
        yield f'event: endpoint\ndata: /messages?session_id={session_id}\n\n'
        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    data = await asyncio.wait_for(queue.get(), timeout=20.0)
                    yield f'event: message\ndata: {json.dumps(data, ensure_ascii=False)}\n\n'
                except asyncio.TimeoutError:
                    yield ': keepalive\n\n'
        finally:
            sse_clients.pop(session_id, None)

    return StreamingResponse(event_generator(), media_type='text/event-stream',
                             headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'})


@app.post('/messages')
async def handle_sse_messages(request: Request, session_id: str):
    if _origin_denied(request):
        return JSONResponse({'error': 'Origin not allowed'}, status_code=403)
    queue = sse_clients.get(session_id)
    if queue is None:
        return JSONResponse({'error': 'Session not found or expired'}, status_code=404)
    body = await _read_limited(request)
    if body is None:
        return JSONResponse({'error': 'Request exceeds size limit or invalid Content-Length'}, status_code=413)
    result = parse_message(body, mcp_engine)
    if result is not None:
        if queue.full():
            return JSONResponse({'error': 'SSE queue limit reached'}, status_code=429)
        await queue.put(result)
    return Response(status_code=202)


if __name__ == '__main__':
    import uvicorn
    port = int(os.getenv('PORT', '8000'))
    uvicorn.run(app, host='0.0.0.0', port=port, reload=False)
