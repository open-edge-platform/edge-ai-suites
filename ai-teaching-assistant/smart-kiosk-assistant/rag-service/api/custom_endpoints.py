from __future__ import annotations

import io
import json
import os
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import JSONResponse, StreamingResponse
from docx import Document as DocxDocument
from pypdf import PdfReader

from dto.query_dto import (
    BatchIngestResponse,
    ContextRequest,
    FileIngestResult,
    IngestResponse,
    QueryRequest,
)
from pipeline import get_shared_pipeline
from utils.config_loader import config
from utils.latency_store import llm_latency, retrieval_latency

router = APIRouter()

_MAX_UPLOAD_BYTES = 10 * 1024 * 1024  # 10 MB
_MAX_INGEST_TOKENS = int(os.getenv("RAG_MAX_INGEST_TOKENS", "25000"))
_ALLOWED_INGEST_SUFFIXES = {".txt", ".md", ".docx", ".pdf"}


def _extract_text_from_file(filename: str, raw: bytes) -> str:
    suffix = Path(filename).suffix.lower()

    if suffix in {".txt", ".md"}:
        try:
            return raw.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise HTTPException(status_code=422, detail="Context file must be UTF-8 encoded") from exc

    if suffix == ".docx":
        try:
            doc = DocxDocument(io.BytesIO(raw))
            return "\n".join(p.text for p in doc.paragraphs)
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(status_code=422, detail="Unable to parse .docx file") from exc

    if suffix == ".pdf":
        try:
            reader = PdfReader(io.BytesIO(raw))
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(status_code=422, detail="Unable to parse .pdf file") from exc

        if getattr(reader, "is_encrypted", False):
            try:
                # Empty password works for some PDFs with trivial protection.
                reader.decrypt("")
            except Exception:  # noqa: BLE001
                pass
            if getattr(reader, "is_encrypted", False):
                raise HTTPException(status_code=422, detail="Encrypted PDFs are not supported")

        page_texts: list[str] = []
        for page in reader.pages:
            page_texts.append(page.extract_text() or "")
        return "\n".join(page_texts)

    raise HTTPException(
        status_code=415,
        detail="Only .txt, .md, .docx and .pdf files are supported",
    )


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


async def _ingest_single_file(pipeline, file: UploadFile) -> FileIngestResult:
    """Ingest one uploaded file, returning a per-file result (never raises)."""
    filename = file.filename or "upload"
    try:
        suffix = Path(filename).suffix.lower()
        if suffix not in _ALLOWED_INGEST_SUFFIXES:
            raise HTTPException(
                status_code=415,
                detail="Only .txt, .md, .docx and .pdf files are supported",
            )

        raw = await file.read()
        if len(raw) > _MAX_UPLOAD_BYTES:
            raise HTTPException(
                status_code=413,
                detail=f"File too large. Maximum allowed size is {_MAX_UPLOAD_BYTES // (1024 * 1024)} MB",
            )
        text = _extract_text_from_file(filename, raw)
        if not text.strip():
            raise HTTPException(status_code=422, detail="No extractable text found in file")

        _validate_token_budget(pipeline, text)
        added = pipeline.ingest_text(text, source=filename)
        return FileIngestResult(source=filename, chunks_added=added, status="ok")
    except HTTPException as exc:
        return FileIngestResult(source=filename, status="failed", detail=str(exc.detail))


@router.post("/api/v1/context/file", response_model=BatchIngestResponse)
async def ingest_context_file(
    files: list[UploadFile] = File(...),
) -> BatchIngestResponse:
    """Ingest one or more documents. Each file is processed independently so a
    single bad file does not fail the whole batch. All ingested documents share
    one collection, so queries are answered across every context."""
    pipeline = get_shared_pipeline()
    results = [await _ingest_single_file(pipeline, file) for file in files]
    succeeded = [r for r in results if r.status == "ok"]
    return BatchIngestResponse(
        total_chunks_added=sum(r.chunks_added for r in results),
        files_processed=len(results),
        files_succeeded=len(succeeded),
        files_failed=len(results) - len(succeeded),
        results=results,
    )


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
