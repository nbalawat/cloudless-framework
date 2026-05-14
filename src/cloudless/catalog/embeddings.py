"""cloudless.Embeddings — unified embeddings primitive over Bedrock / Vertex.

M1.5+ ships Bedrock backend (Titan + Cohere). Vertex backend in M2.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class EmbeddingAlias:
    alias: str
    provider: str
    model_id: str
    dimensions: int


# Common Bedrock embedding models (per Bedrock docs)
DEFAULT_EMBEDDING_ALIASES: tuple[EmbeddingAlias, ...] = (
    EmbeddingAlias("titan-v2", "bedrock", "amazon.titan-embed-text-v2:0", 1024),
    EmbeddingAlias("titan-v1", "bedrock", "amazon.titan-embed-text-v1", 1536),
    EmbeddingAlias("cohere-en", "bedrock", "cohere.embed-english-v3", 1024),
    EmbeddingAlias("cohere-multi", "bedrock", "cohere.embed-multilingual-v3", 1024),
)

_BY_ALIAS = {a.alias: a for a in DEFAULT_EMBEDDING_ALIASES}


class EmbeddingsBackend(Protocol):
    async def embed(self, texts: list[str]) -> list[list[float]]: ...


def resolve_embedding(name: str) -> EmbeddingAlias:
    if name in _BY_ALIAS:
        return _BY_ALIAS[name]
    # Plausibly a raw model ID; pass-through with unknown dimensions.
    return EmbeddingAlias(alias=name, provider="bedrock", model_id=name, dimensions=0)


class Embeddings:
    """Unified embeddings primitive.

    Example:
        embed = cloudless.Embeddings(model="titan-v2")
        vectors = await embed.embed(["hello", "world"])
        assert len(vectors) == 2
        assert len(vectors[0]) == 1024
    """

    def __init__(
        self,
        model: str = "titan-v2",
        *,
        region: str = "us-east-1",
        backend: EmbeddingsBackend | None = None,
    ) -> None:
        self.alias = resolve_embedding(model)
        self.region = region
        if backend is not None:
            self._backend = backend
        elif self.alias.provider == "bedrock":
            from cloudless.adapters.aws.embeddings import BedrockEmbeddingsBackend
            self._backend = BedrockEmbeddingsBackend(
                model_id=self.alias.model_id, region=region,
            )
        else:
            raise ValueError(f"Unsupported embeddings provider: {self.alias.provider!r}")

    async def embed(self, texts: list[str]) -> list[list[float]]:
        return await self._backend.embed(texts)
