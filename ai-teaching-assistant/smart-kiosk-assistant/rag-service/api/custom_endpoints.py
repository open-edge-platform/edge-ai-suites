from __future__ import annotations

import json
import os
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import JSONResponse, StreamingResponse

from dto.query_dto import ContextRequest, IngestResponse, QueryRequest
from pipeline import get_shared_pipeline
from utils.config_loader import config
from utils.latency_store import llm_latency, retrieval_latency

router = APIRouter()

_MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10 MB
_MAX_INGEST_TOKENS = int(os.getenv("RAG_MAX_INGEST_TOKENS", "25000"))
_ALLOWED_INGEST_SUFFIXES = {".txt", ".md"}


def _validate_token_budget(pipeline, text: str) -> None:
    """Reject ingest requests that exceed the configured token budget."""
    token_count = pipeline.count_tokens(text)
    if token_count > _MAX_INGEST_TOKENS:
        raise HTTPException(
            status_code=413,
            detail=(
                f"Content too large: {token_count} tokens (limit is "
                f"{_MAX_INGEST_TOKENS}). Please shorten the document and try again."
            ),
        )


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/api/v1/model-info")
def model_info():
    stats = get_shared_pipeline().get_stats()
    embedding_cfg = config.models.embedding
    reranker_cfg = getattr(config.retrieval, "reranker", None)
    reranker_info: dict | None = None
    if reranker_cfg is not None and getattr(reranker_cfg, "enabled", True):
        reranker_info = {
            "hf_id": getattr(reranker_cfg, "hf_id", None),
            "device": str(getattr(reranker_cfg, "device", "CPU")).upper(),
            "backend": getattr(reranker_cfg, "backend", None),
            "weight_format": getattr(reranker_cfg, "weight_format", None),
        }
    return JSONResponse(content={
        **stats,
        "llm_device": str(getattr(config.models.llm, "device", "CPU")).upper(),
        "llm_weight_format": getattr(config.models.llm, "weight_format", None),
        "embedding_device": str(getattr(embedding_cfg, "device", "CPU")).upper(),
        "embedding_backend": getattr(embedding_cfg, "backend", None),
        "embedding_weight_format": getattr(embedding_cfg, "weight_format", None),
        "reranker": reranker_info,
        "top_k": int(getattr(config.retrieval, "top_k", 3)),
        "fetch_k": int(getattr(config.retrieval, "fetch_k", 5)),
    })


@router.get("/api/v1/performance")
def rag_performance():
    return JSONResponse(content={
        "latency": {
            "retrieval": retrieval_latency.stats(),
            "llm": llm_latency.stats(),
        }
    })


@router.post("/api/v1/context", response_model=IngestResponse)
def ingest_context(request: ContextRequest) -> IngestResponse:
    pipeline = get_shared_pipeline()
    _validate_token_budget(pipeline, request.text)
    added = pipeline.ingest_text(request.text, source=request.source, metadata=request.metadata)
    return IngestResponse(chunks_added=added, source=request.source)


@router.post("/api/v1/context/file", response_model=IngestResponse)
async def ingest_context_file(file: UploadFile = File(...)) -> IngestResponse:
    filename = file.filename or "upload"
    suffix = Path(filename).suffix.lower()
    if suffix not in _ALLOWED_INGEST_SUFFIXES:
        raise HTTPException(
            status_code=415,
            detail="Only .txt and .md files are supported",
        )

    raw = await file.read()
    if len(raw) > _MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Maximum allowed size is {_MAX_UPLOAD_BYTES // (1024 * 1024)} MB",
        )
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise HTTPException(status_code=422, detail="Context file must be UTF-8 encoded") from exc

    pipeline = get_shared_pipeline()
    _validate_token_budget(pipeline, text)
    added = pipeline.ingest_text(text, source=filename)
    return IngestResponse(chunks_added=added, source=filename)


@router.get("/api/v1/context/stats")
def context_stats():
    return JSONResponse(content=get_shared_pipeline().get_stats(), status_code=200)


@router.delete("/api/v1/context")
def clear_context():
    get_shared_pipeline().clear_context()
    return JSONResponse(content={"status": "cleared"}, status_code=200)


@router.post("/api/v1/query")
def query_context(request: QueryRequest) -> StreamingResponse:
    pipeline = get_shared_pipeline()
    history_pairs: list[tuple[str, str]] | None = (
        [(turn.role, turn.content) for turn in request.history] if request.history else None
    )
    prompt, sources = pipeline.plan_answer(
        request.transcription,
        context_text=request.context_text,
        top_k=request.top_k,
        history=history_pairs,
    )

    def _sse_generator():
        answer_tokens: list[str] = []
        try:
            for token in pipeline.stream_from_prompt(prompt):
                answer_tokens.append(token)
                yield f"data: {json.dumps({'token': token}, ensure_ascii=False)}\n\n"
        except Exception as exc:  # noqa: BLE001
            yield f"data: {json.dumps({'error': str(exc)}, ensure_ascii=False)}\n\n"
        finally:
            if request.include_performance_metrics or request.include_llm_metrics:
                metrics_payload: dict[str, object] = {"event": "metrics"}
                if request.include_performance_metrics:
                    metrics_payload["performance_metrics"] = {
                        "retrieval": retrieval_latency.stats(),
                        "llm": llm_latency.stats(),
                    }
                if request.include_llm_metrics:
                    metrics_payload["llm_metrics"] = llm_latency.stats()
                yield f"data: {json.dumps(metrics_payload, ensure_ascii=False)}\n\n"

            if request.include_sources and sources:
                payload = {
                    "event": "sources",
                    "sources": pipeline.source_payloads(sources),
                    "answer": "".join(answer_tokens).strip(),
                }
                yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"

    return StreamingResponse(
        _sse_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
