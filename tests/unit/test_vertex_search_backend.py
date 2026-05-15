"""Unit tests for VertexSearchBackend wiring (stub-tested).

Real Vertex Search requires a pre-provisioned Discovery Engine datastore.
The wiring is what's under test here; the live integration test is
gated by user-side provisioning (similar to Bedrock KB).
"""
from __future__ import annotations

import pytest


pytestmark = [pytest.mark.asyncio]


class _FakeDoc:
    def __init__(self, id_, title="", uri=""):
        self.id = id_
        self.name = f"projects/x/locations/global/dataStores/y/documents/{id_}"
        self.derived_struct_data = {"title": title, "uri": uri}


class _FakeResult:
    def __init__(self, doc):
        self.document = doc


class _FakeSearchPage:
    def __init__(self, results):
        self.results = results


class _FakeSearchClient:
    def __init__(self, results=None):
        self._results = results or []
        self.calls = []

    def search(self, *, request):
        self.calls.append(request)
        return _FakeSearchPage(self._results)


async def test_vertex_search_search_returns_matches():
    from cloudless.adapters.gcp.vector_store import VertexSearchBackend

    docs = [
        _FakeDoc("doc-1", title="Paris is the capital of France"),
        _FakeDoc("doc-2", title="Tokyo is the capital of Japan"),
    ]
    client = _FakeSearchClient([_FakeResult(d) for d in docs])
    backend = VertexSearchBackend(
        datastore_id="projects/p/locations/global/collections/default_collection/dataStores/ds",
        client=client,
    )
    results = await backend.search(query="capital", top_k=2)
    assert len(results) == 2
    assert results[0].id == "doc-1"
    assert "Paris" in results[0].text


async def test_vertex_search_upsert_raises():
    from cloudless.adapters.gcp.vector_store import VertexSearchBackend
    backend = VertexSearchBackend(
        datastore_id="projects/p/locations/global/collections/default_collection/dataStores/ds",
        client=_FakeSearchClient(),
    )
    with pytest.raises(NotImplementedError, match="read-only"):
        await backend.upsert([{"id": "x", "text": "hello"}])


async def test_vector_store_factory_wires_vertex_search(monkeypatch):
    """If the discoveryengine SDK is installed, construction should succeed.

    The CI environment may not have google-cloud-discoveryengine installed;
    skip cleanly if so — the wiring is what we're testing, not the SDK."""
    try:
        import google.cloud.discoveryengine_v1  # noqa: F401
    except ImportError:
        pytest.skip("google-cloud-discoveryengine not installed")
    import cloudless
    vs = cloudless.VectorStore(
        backend="vertex-search",
        datastore_id="projects/p/locations/global/collections/default_collection/dataStores/ds",
    )
    assert vs._backend.__class__.__name__ == "VertexSearchBackend"


async def test_vector_store_factory_rejects_vertex_search_without_datastore_id():
    import cloudless
    with pytest.raises(ValueError, match="datastore_id"):
        cloudless.VectorStore(backend="vertex-search")
