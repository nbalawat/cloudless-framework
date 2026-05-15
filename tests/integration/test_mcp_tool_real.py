"""Real-HTTP integration test for `Tool.from_mcp_server`.

Spins up a minimal Starlette app that mimics the MCP `tools/call` JSON-RPC
shape and exercises `Tool.from_mcp_server` against it. Uses real network
sockets so the test catches httpx/uvicorn integration issues.

Note: cloudless's MCP client takes a shortcut — it does NOT do the full
MCP handshake (initialize → tools/list → tools/call). It just POSTs
`tools/call` directly. So we mimic that contract precisely.
"""
from __future__ import annotations

import socket
import threading
import time

import pytest
import uvicorn
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

import cloudless

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


# --------------------------------------------------------------------- #
# Minimal MCP-compatible HTTP server fixture
# --------------------------------------------------------------------- #


def _build_mcp_stub() -> Starlette:
    """A Starlette app that answers tools/call for a fake 'echo' tool."""

    async def handle(request: Request) -> JSONResponse:
        body = await request.json()
        if body.get("method") != "tools/call":
            return JSONResponse({"jsonrpc": "2.0", "id": body.get("id"),
                                  "error": {"code": -32601, "message": "method not found"}})
        params = body.get("params", {})
        name = params.get("name")
        args = params.get("arguments", {})
        if name == "echo":
            return JSONResponse({
                "jsonrpc": "2.0", "id": body.get("id"),
                "result": {"echoed": args.get("message", ""), "args_seen": args},
            })
        if name == "add":
            a = int(args.get("a", 0))
            b = int(args.get("b", 0))
            return JSONResponse({
                "jsonrpc": "2.0", "id": body.get("id"),
                "result": {"sum": a + b},
            })
        return JSONResponse({"jsonrpc": "2.0", "id": body.get("id"),
                              "error": {"code": -32602, "message": f"unknown tool: {name}"}})

    return Starlette(routes=[Route("/", handle, methods=["POST"])])


@pytest.fixture(scope="module")
def mcp_server():
    """Boot the stub server in a background thread."""
    port = _free_port()
    app = _build_mcp_stub()
    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning")
    server = uvicorn.Server(config)
    server_thread = threading.Thread(target=server.run, daemon=True)
    server_thread.start()
    # Wait until the server is responsive (up to 5 seconds)
    import httpx
    deadline = time.time() + 5
    while time.time() < deadline:
        try:
            httpx.post(f"http://127.0.0.1:{port}/",
                       json={"jsonrpc": "2.0", "id": "ping", "method": "ping"}, timeout=0.5)
            break
        except Exception:
            time.sleep(0.1)
    yield f"http://127.0.0.1:{port}/"
    server.should_exit = True
    server_thread.join(timeout=2)


# --------------------------------------------------------------------- #
# Tests
# --------------------------------------------------------------------- #


async def test_from_mcp_server_calls_real_endpoint(mcp_server):
    tool = cloudless.Tool.from_mcp_server(mcp_server, tool_name="echo")
    result = await tool.invoke({"message": "hello"})
    assert result == {"echoed": "hello", "args_seen": {"message": "hello"}}


async def test_from_mcp_server_passes_complex_args(mcp_server):
    tool = cloudless.Tool.from_mcp_server(mcp_server, tool_name="add")
    result = await tool.invoke({"a": 5, "b": 7})
    assert result == {"sum": 12}


async def test_from_mcp_server_raises_on_error_response(mcp_server):
    tool = cloudless.Tool.from_mcp_server(mcp_server, tool_name="nonexistent")
    with pytest.raises(RuntimeError, match="MCP error"):
        await tool.invoke({})


async def test_from_mcp_server_includes_auth_header(mcp_server):
    """If `auth` callback supplies a token, it must travel in Authorization header.

    Verify by spinning a secondary server that records inbound headers.
    """
    import threading as _t

    received: dict[str, str] = {}

    async def handle(request: Request) -> JSONResponse:
        for k, v in request.headers.items():
            received[k.lower()] = v
        body = await request.json()
        return JSONResponse({
            "jsonrpc": "2.0", "id": body.get("id"),
            "result": {"saw_auth": received.get("authorization", "")},
        })

    app = Starlette(routes=[Route("/", handle, methods=["POST"])])
    port = _free_port()
    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning")
    server = uvicorn.Server(config)
    th = _t.Thread(target=server.run, daemon=True)
    th.start()
    import httpx
    deadline = time.time() + 5
    while time.time() < deadline:
        try:
            httpx.post(f"http://127.0.0.1:{port}/",
                       json={"jsonrpc": "2.0", "id": "x", "method": "tools/call",
                             "params": {"name": "x", "arguments": {}}}, timeout=0.5)
            break
        except Exception:
            time.sleep(0.1)

    try:
        tool = cloudless.Tool.from_mcp_server(
            f"http://127.0.0.1:{port}/",
            tool_name="anything",
            auth=lambda: "secret-token-123",
        )
        result = await tool.invoke({})
        assert result["saw_auth"] == "Bearer secret-token-123"
    finally:
        server.should_exit = True
        th.join(timeout=2)
