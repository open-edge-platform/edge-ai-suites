from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ContextRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=5_000_000)  # 5 MB hard cap
    source: str = Field("api", max_length=256)
    metadata: dict[str, Any] | None = None


class ChatTurn(BaseModel):
    role: str = Field(..., pattern="^(user|assistant)$")
    content: str = Field(..., min_length=1, max_length=10_000)


class QueryRequest(BaseModel):
    transcription: str = Field(..., min_length=1, max_length=10_000)
    context_text: str | None = Field(default=None, max_length=10_000)
    top_k: int | None = Field(default=None, ge=1, le=20)
    include_sources: bool = False
    include_performance_metrics: bool = False
    include_llm_metrics: bool = False
    # Recent conversation turns prior to `transcription`, oldest-first. Used so
    # follow-ups like 'are you sure?' resolve against the last exchange. The
    # pipeline trims/drops oldest turns when the context budget is tight.
    history: list[ChatTurn] | None = None


class IngestResponse(BaseModel):
    chunks_added: int
    source: str


class FileIngestResult(BaseModel):
    source: str
    chunks_added: int = 0
    status: str = "ok"
    detail: str | None = None


class BatchIngestResponse(BaseModel):
    total_chunks_added: int
    files_processed: int
    files_succeeded: int
    files_failed: int
    results: list[FileIngestResult]


class ChatMessage(BaseModel):
    role: str
    content: str | list[dict[str, Any]]


class ChatCompletionRequest(BaseModel):
    model: str = Field(default="smart-kiosk-rag")
    messages: list[ChatMessage] = Field(default_factory=list, min_length=1)
    stream: bool = False
    temperature: float | None = Field(default=None, ge=0.0, le=2.0)
    max_tokens: int | None = Field(default=None, ge=1, le=4096)
