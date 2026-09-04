"""Optional local embedding boundary. The production dependency is loaded on demand."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

INSTALL_HINT = "pip install 'agent-memory-core[vector]'"


class Embedder(Protocol):
    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]: ...

    def embed_query(self, text: str) -> list[float]: ...


class FastEmbedder:
    def __init__(self, model: str):
        try:
            from fastembed import TextEmbedding
        except ImportError as error:
            raise RuntimeError(
                "Vector capability is enabled but optional embedding dependency is unavailable; "
                f"install it with: {INSTALL_HINT}"
            ) from error
        self._backend = TextEmbedding(model_name=model)

    def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        return [item.tolist() for item in self._backend.embed(list(texts))]

    def embed_query(self, text: str) -> list[float]:
        return self.embed_documents([text])[0]


def create_embedder(model: str) -> Embedder:
    return FastEmbedder(model)
