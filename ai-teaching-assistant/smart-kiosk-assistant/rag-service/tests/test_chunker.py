"""Smoke tests for the chunking pipeline.

These exercise the real ``SemanticChunker`` path with the LLM marker splitter
stubbed out so the recursive fallback runs deterministically. They verify
that:

* chunks come back with content
* chunks respect ``max_chunk_chars`` within reasonable slack
* markdown heading paths are preserved on chunk metadata
* the contextual heading prefix is prepended to chunk text
"""
from __future__ import annotations

from components.chunker_component import SemanticChunker


class _FakeEmbeddings:
    """Minimal embedder for the semantic merger. Returns a deterministic
    2-D vector so cosine similarity is computable without loading a model."""

    def embed_documents(self, texts):
        return [[1.0, float(i + 1)] for i, _ in enumerate(texts)]

    def embed_query(self, text):
        return [1.0, 1.0]


def _fake_llm(prompt: str, max_new_tokens=None, temperature=None) -> str:
    """LLM stub: an empty string forces the marker splitter to fail and the
    deterministic recursive fallback to take over. Keeps the test independent
    of any model export."""
    return ""


def _patch_chunk_cfg(monkeypatch, **kwargs):
    for key, value in kwargs.items():
        monkeypatch.setattr(
            f"components.chunker_component.config.chunking.{key}", value
        )


def test_chunker_produces_chunks_within_cap(monkeypatch):
    _patch_chunk_cfg(
        monkeypatch,
        max_chunk_chars=200,
        min_chunk_chars=40,
        overlap_chars=0,
        llm_min_passage_chars=200,
        save_chunks_debug=None,
    )

    text = "Sentence one. " * 60
    chunker = SemanticChunker(_FakeEmbeddings(), _fake_llm)
    chunks = chunker.chunk_text(text)

    assert chunks
    assert all(chunk.text for chunk in chunks)
    # Some slack for overlap / atomic-block snapping, but no chunk should
    # blow far past the cap.
    assert all(len(chunk.text) <= 400 for chunk in chunks)


def test_chunker_preserves_heading_and_prefix(monkeypatch):
    _patch_chunk_cfg(
        monkeypatch,
        max_chunk_chars=400,
        min_chunk_chars=40,
        overlap_chars=0,
        llm_min_passage_chars=400,
        save_chunks_debug=None,
    )

    text = (
        "# Acme Store\n\n"
        "## Hours\n\n"
        "We are open from 9am to 9pm every day. Holiday hours vary.\n"
    )
    chunker = SemanticChunker(_FakeEmbeddings(), _fake_llm)
    chunks = chunker.chunk_text(text, source_hint="acme.md")

    assert chunks
    sections = [c.metadata.get("section") for c in chunks if c.metadata]
    assert any(s and "Hours" in s for s in sections), sections
    assert any(c.text.startswith("[Context:") for c in chunks), [c.text[:60] for c in chunks]
