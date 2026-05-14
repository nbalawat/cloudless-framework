"""Unit tests for cloudless.Tool — local construction + invocation."""
from __future__ import annotations

import pytest

import cloudless
from cloudless.catalog.tools import Tool


class TestFromFunction:
    async def test_decorator_no_args(self):
        @cloudless.tool
        def add(a: int, b: int) -> int:
            "Return a + b."
            return a + b

        assert isinstance(add, Tool)
        assert add.name == "add"
        assert "Return a + b." in add.description
        assert add.parameters["required"] == ["a", "b"]
        assert (await add.invoke({"a": 2, "b": 3})) == 5

    async def test_decorator_with_overrides(self):
        @cloudless.tool(name="sum2", description="Custom desc.")
        def add(a: int, b: int) -> int:
            return a + b
        assert add.name == "sum2"
        assert add.description == "Custom desc."

    async def test_signature_to_schema_handles_types(self):
        @cloudless.tool
        def show(name: str, age: int, alive: bool = True) -> dict:
            return {"n": name, "a": age, "ok": alive}

        props = show.parameters["properties"]
        assert props["name"]["type"] == "string"
        assert props["age"]["type"] == "integer"
        assert props["alive"]["type"] == "boolean"
        # Only required params (no default) in `required`
        assert sorted(show.parameters["required"]) == ["age", "name"]

    async def test_async_function_supported(self):
        @cloudless.tool
        async def afn(x: int) -> int:
            return x * 2
        assert (await afn.invoke({"x": 21})) == 42


class TestPublicSurface:
    def test_top_level_imports(self):
        assert cloudless.Tool is Tool
        assert cloudless.tool is not None
