from __future__ import annotations

from dataclasses import dataclass

from components.embedding_component import EmbeddingComponent


@dataclass(slots=True)
class RetrievalRecord:
    source: str
    content: str
    score: float | None
    metadata: dict


class ChromaEmbeddingAdapter:
    """Adapts our ``EmbeddingComponent`` to the interface LangChain's Chroma
    wrapper expects (``embed_documents`` / ``embed_query``)."""

    def __init__(self, component: EmbeddingComponent) -> None:
        self.component = component

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return self.component.embed_documents(texts)

    def embed_query(self, text: str) -> list[float]:
        return self.component.embed_query(text)
