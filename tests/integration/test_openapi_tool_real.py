"""Real-HTTP integration test for `Tool.from_openapi`.

Spins up a FastAPI server with two operations, fetches its auto-generated
OpenAPI spec, and exercises `Tool.from_openapi` end-to-end through real
sockets.
"""
from __future__ import annotations

import socket
import threading
import time

import pytest
import uvicorn

import cloudless

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


try:
    from pydantic import BaseModel as _BaseModel

    class _GreetBody(_BaseModel):
        name: str

    class _MathBody(_BaseModel):
        a: int
        b: int
except ImportError:
    _GreetBody = None  # type: ignore[assignment]
    _MathBody = None   # type: ignore[assignment]


def _build_fastapi_app():
    """Two operations:

      POST /greet  → JSON body {name} returns {"greeting": f"hi {name}"}
      POST /math/{op} → path param + body {a, b} returns the computed value
    """
    from fastapi import FastAPI

    app = FastAPI()

    @app.post("/greet", operation_id="greet")
    def greet(body: _GreetBody):
        return {"greeting": f"hi {body.name}"}

    @app.post("/math/{op}", operation_id="math")
    def math(op: str, body: _MathBody):
        if op == "add":
            return {"result": body.a + body.b}
        if op == "mul":
            return {"result": body.a * body.b}
        return {"error": f"unknown op {op!r}"}

    return app


@pytest.fixture(scope="module")
def openapi_server():
    pytest.importorskip("fastapi")
    port = _free_port()
    app = _build_fastapi_app()
    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning")
    server = uvicorn.Server(config)
    th = threading.Thread(target=server.run, daemon=True)
    th.start()
    import httpx
    deadline = time.time() + 5
    while time.time() < deadline:
        try:
            r = httpx.get(f"http://127.0.0.1:{port}/openapi.json", timeout=0.5)
            if r.status_code == 200:
                break
        except Exception:
            time.sleep(0.1)
    yield f"http://127.0.0.1:{port}"
    server.should_exit = True
    th.join(timeout=2)


async def test_from_openapi_calls_real_endpoint(openapi_server):
    spec = f"{openapi_server}/openapi.json"
    # FastAPI's auto-generated spec doesn't include a `servers` entry, so we
    # inject one — fetch the spec and pass it as dict
    import httpx
    parsed = httpx.get(spec, timeout=5.0).json()
    parsed["servers"] = [{"url": openapi_server}]

    tool = cloudless.Tool.from_openapi(parsed, operation_id="greet")
    result = await tool.invoke({"name": "alice"})
    assert result == {"greeting": "hi alice"}


async def test_from_openapi_path_param_substitution(openapi_server):
    import httpx
    parsed = httpx.get(f"{openapi_server}/openapi.json", timeout=5.0).json()
    parsed["servers"] = [{"url": openapi_server}]

    tool = cloudless.Tool.from_openapi(parsed, operation_id="math")
    add_result = await tool.invoke({"op": "add", "a": 7, "b": 3})
    mul_result = await tool.invoke({"op": "mul", "a": 4, "b": 5})
    assert add_result == {"result": 10}
    assert mul_result == {"result": 20}


async def test_from_openapi_uses_operationId_for_name(openapi_server):
    import httpx
    parsed = httpx.get(f"{openapi_server}/openapi.json", timeout=5.0).json()
    parsed["servers"] = [{"url": openapi_server}]
    tool = cloudless.Tool.from_openapi(parsed, operation_id="greet")
    assert tool.name == "greet"
    assert tool.metadata.get("source") == "openapi"


async def test_from_openapi_missing_operation_raises(openapi_server):
    import httpx
    parsed = httpx.get(f"{openapi_server}/openapi.json", timeout=5.0).json()
    parsed["servers"] = [{"url": openapi_server}]
    with pytest.raises(ValueError, match="No operation"):
        cloudless.Tool.from_openapi(parsed, operation_id="not-an-operation")
