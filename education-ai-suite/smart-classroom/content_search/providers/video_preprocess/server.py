"""Video Preprocess Service (decode/chunk/sample → summarize → MinIO)
- downloads the video from MinIO to a temp file
- chunks the video by time (FrameSampler.iter_chunks)
- samples frames per chunk (FrameSampler.sample_frames_from_video)
- calls vlm-openvino-serving (/v1/chat/completions) to generate a chunk summary
- uploads chunk summary text files back to MinIO

MinIO output layout (derived artifacts):
  runs/{run_id}/derived/video/{asset_id}/chunksum-v1/summaries/chunk_0001/summary.txt
  runs/{run_id}/derived/video/{asset_id}/chunksum-v1/summaries/chunk_0001/metadata.json
  runs/{run_id}/derived/video/{asset_id}/chunksum-v1/manifest.json
"""

from __future__ import annotations

import base64
import io
import json
import os
import queue as _queue
import tempfile
import threading
import time
import uuid
from typing import Any, Callable, Dict, List, Optional

import requests
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from PIL import Image
from pydantic import BaseModel, Field

from frame_sampler import FrameSampler

from content_search.minio_wrapper.minio_client import MinioStore

from utils.config_loader import config as _svc_config

_pre_cfg   = _svc_config.content_search.video_preprocess
_vlm_cfg   = _svc_config.content_search.vlm
_minio_cfg = _svc_config.content_search.minio
_ingest_cfg = _svc_config.content_search.file_ingest

VLM_ENDPOINT: str = f"http://{_vlm_cfg.host_addr}:{_vlm_cfg.port}/v1/chat/completions"
VLM_TIMEOUT_SECONDS: int = int(_pre_cfg.vlm_timeout_seconds)
DEFAULT_CHUNK_DURATION_S: int = int(_pre_cfg.chunk_duration_s)
DEFAULT_CHUNK_OVERLAP_S: int = int(_pre_cfg.chunk_overlap_s)
DEFAULT_MAX_NUM_FRAMES: int = int(_pre_cfg.max_num_frames)
DEFAULT_FRAME_WIDTH: int = int(_pre_cfg.frame_width)
DEFAULT_FRAME_HEIGHT: int = int(_pre_cfg.frame_height)
if getattr(_vlm_cfg, "ingest_enabled", False):
    INGEST_ENDPOINT: Optional[str] = (
        f"http://{_ingest_cfg.host_addr}:{_ingest_cfg.port}/v1/dataprep/ingest_text"
    )
    INGEST_BUCKET: str = str(_minio_cfg.bucket)
else:
    INGEST_ENDPOINT = None
    INGEST_BUCKET = ""

class PreprocessRequest(BaseModel):
    minio_video_key: str = Field(
        ...,
        description="MinIO object key for the source video (uploaded by Service Manager)",
    )
    job_id: Optional[str] = Field(
        None,
        description="Optional job id from caller (e.g., Service Manager) for correlation/tracing",
    )
    run_id: Optional[str] = Field(
        None,
        description="Run id for namespacing outputs (auto UUID if omitted)"
    )
    asset_id: Optional[str] = Field(
        None,
        description="Asset/video id for output path segment (defaults to filename of minio_video_key)",
    )
    tags: Optional[List[str]] = Field(
        None,
        description="Optional tags to attach to each ingested chunk (forwarded to ingest meta)",
    )

    chunk_duration_s: int = Field(default=DEFAULT_CHUNK_DURATION_S, ge=1, description="Chunk duration in seconds")
    chunk_overlap_s: int = Field(default=DEFAULT_CHUNK_OVERLAP_S, ge=0, description="Chunk overlap in seconds")
    max_num_frames: int = Field(default=DEFAULT_MAX_NUM_FRAMES, ge=1, description="Max sampled frames per chunk")

    prompt: str = Field("Please summarize this video.", description="Prompt used per chunk")
    max_completion_tokens: int = Field(500, ge=1, description="VLM max completion tokens")

    vlm_endpoint: Optional[str] = Field(None, description="Override VLM endpoint URL")
    vlm_timeout_seconds: Optional[int] = Field(None, ge=1, description="Override VLM timeout seconds")

    reuse_existing: bool = Field(
        True,
        description="If true and summary.txt already exists in MinIO, reuse it instead of recomputing",
    )

class ChunkSummaryResult(BaseModel):
    chunk_id: str
    chunk_index: int
    start_time: float
    end_time: float
    start_frame: int
    end_frame: int
    minio_key: str
    chunk_metadata_key: str = ""
    summary: str
    reused: bool = False
    total_chunks: int = 0   # total number of chunks in this job (0 = not yet known)
    error: Optional[str] = None  # set if VLM or MinIO write failed for this chunk
    ingest_status: str = "pending"  # pending | ok | failed | skipped


class PreprocessResponse(BaseModel):
    job_id: str
    run_id: str
    asset_id: str
    minio_video_key: str
    elapsed_seconds: float
    total_chunks: int = 0
    succeeded_chunks: int = 0
    failed_chunks: int = 0
    ingest_ok_chunks: int = 0
    ingest_failed_chunks: int = 0


class VlmClient:
    def __init__(self, *, endpoint: str, timeout_seconds: int):
        self._endpoint = str(endpoint)
        self._timeout_seconds = int(timeout_seconds)
        # Do not inherit system proxy settings for local service calls.
        # This avoids corporate proxy interception for 127.0.0.1 endpoints.
        self._session = requests.Session()
        self._session.trust_env = False

    @staticmethod
    def _frame_to_jpeg_data_url(frame) -> str:
        # frame is expected as an RGB numpy array from decord
        img = Image.fromarray(frame)
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=85)
        b64 = base64.b64encode(buf.getvalue()).decode("ascii")
        return f"data:image/jpeg;base64,{b64}"

    def summarize_frames(self, frames, *, prompt: str, max_completion_tokens: int) -> str:
        # Match vlm-openvino-serving schema: ChatRequest uses max_completion_tokens.
        content: list[dict[str, Any]] = [{"type": "text", "text": prompt}]
        for frame in frames:
            content.append({"type": "image_url", "image_url": {"url": self._frame_to_jpeg_data_url(frame)}})

        payload = {
            "messages": [{"role": "user", "content": content}],
            "stream": False,
            "max_completion_tokens": int(max_completion_tokens),
        }

        try:
            resp = self._session.post(
                self._endpoint,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=self._timeout_seconds,
            )
        except requests.RequestException as exc:
            raise RuntimeError(f"VLM request failed: {exc}") from exc

        if resp.status_code != 200:
            raise RuntimeError(f"VLM endpoint returned {resp.status_code}: {resp.text}")
        print(f"Finished VLM summarization, summary_len={len(resp.text)}, elapsed={resp.elapsed.total_seconds():.2f}s")
        data = resp.json()
        try:
            return str(data["choices"][0]["message"]["content"]).strip()
        except Exception as exc:
            raise RuntimeError(f"Unexpected VLM response schema: {data}") from exc


def _ingest_chunk_async(bucket: str, summary_key: str, summary_text: str, meta: Dict[str, Any], result: "ChunkSummaryResult") -> Optional[threading.Thread]:
    """Start ingestion in a background thread and return the thread so the caller can join() it."""
    endpoint = INGEST_ENDPOINT
    if not endpoint:
        result.ingest_status = "skipped"
        return None
    payload = {
        "bucket_name": bucket,
        "file_path": summary_key,
        "text": summary_text,
        "meta": meta,
    }

    def _post() -> None:
        chunk_id = meta.get("chunk_id", summary_key)
        try:
            print(f"[preprocess] Ingesting {chunk_id} -> {endpoint}")
            session = requests.Session()
            session.trust_env = False
            resp = session.post(endpoint, json=payload, timeout=120)
            if resp.status_code == 200:
                print(f"[preprocess] Ingest OK for {chunk_id}")
                result.ingest_status = "ok"
            else:
                msg = f"HTTP {resp.status_code} {resp.text[:200]}"
                print(f"[preprocess] Ingest WARN {chunk_id}: {msg}")
                result.ingest_status = "failed"
        except Exception as exc:
            print(f"[preprocess] Ingest ERROR {chunk_id}: {exc}")
            result.ingest_status = "failed"

    result.ingest_status = "pending"
    t = threading.Thread(target=_post, daemon=True)
    t.start()
    return t


app = FastAPI(
    title="Video Preprocess Service",
    version="0.2.0",
    description="Decode/chunk/sample a MinIO video, call vlm-openvino-serving, write chunk summaries to MinIO.",
)

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/preprocess")
def submit_preprocess(req: PreprocessRequest) -> StreamingResponse:
    """Preprocess a video: decode/chunk/sample → summarize → ingest → write to MinIO.

    Streams NDJSON lines so the caller gets progress as each chunk completes.

    Each chunk line: {"type": "chunk", "chunk_id": "chunk_0001", "chunk_index": 1,
                      "start_time": 0.0, "end_time": 30.0, "reused": false,
                      "ingest_status": "ok", "error": null}
    Final line:      {"type": "done", "job_id": "...", "total_chunks": 3, ...}
    Error line:      {"type": "error", "message": "..."}
    """
    job_id = str(req.job_id) if req.job_id else str(uuid.uuid4())
    t0 = time.time()
    print(f"[preprocess] Request received: job_id={job_id} key={req.minio_video_key}")

    q: _queue.Queue = _queue.Queue()

    def on_chunk(result: ChunkSummaryResult) -> None:
        q.put(("chunk", result))

    def run() -> None:
        try:
            resp = _process(job_id, req, t0, on_chunk=on_chunk)
            q.put(("done", resp))
        except Exception as exc:
            import traceback as _tb
            _tb.print_exc()
            q.put(("error", f"{type(exc).__name__}: {exc}"))

    threading.Thread(target=run, daemon=True).start()

    def generate():
        while True:
            kind, data = q.get()
            if kind == "chunk":
                r: ChunkSummaryResult = data
                yield json.dumps({
                    "type": "chunk", "chunk_id": r.chunk_id,
                    "chunk_index": r.chunk_index, "total_chunks": r.total_chunks,
                    "start_time": r.start_time, "end_time": r.end_time,
                    "reused": r.reused, "ingest_status": r.ingest_status, "error": r.error,
                }) + "\n"
            elif kind == "done":
                resp: PreprocessResponse = data
                yield json.dumps({
                    "type": "done", "job_id": resp.job_id, "run_id": resp.run_id,
                    "asset_id": resp.asset_id,
                    "total_chunks": resp.total_chunks, "succeeded_chunks": resp.succeeded_chunks,
                    "failed_chunks": resp.failed_chunks, "ingest_ok_chunks": resp.ingest_ok_chunks,
                    "ingest_failed_chunks": resp.ingest_failed_chunks,
                    "elapsed_seconds": resp.elapsed_seconds,
                }) + "\n"
                break
            elif kind == "error":
                yield json.dumps({"type": "error", "message": data}) + "\n"
                break

    return StreamingResponse(generate(), media_type="application/x-ndjson")


def _process(job_id: str, req: PreprocessRequest, t0: float,
             on_chunk: Optional[Callable[["ChunkSummaryResult"], None]] = None) -> PreprocessResponse:
    run_id = req.run_id or str(uuid.uuid4())
    asset_id = req.asset_id or req.minio_video_key.rsplit("/", 1)[-1]
    frame_resolution = [DEFAULT_FRAME_WIDTH, DEFAULT_FRAME_HEIGHT] if DEFAULT_FRAME_WIDTH > 0 and DEFAULT_FRAME_HEIGHT > 0 else []

    def _summary_params_for_reuse() -> Dict[str, Any]:
        # Params that materially affect the generated summary.
        return {
            "chunk_duration_s": int(req.chunk_duration_s),
            "chunk_overlap_s": int(req.chunk_overlap_s),
            "max_num_frames": int(req.max_num_frames),
            "frame_resolution": frame_resolution,
            "prompt": str(req.prompt),
            "max_completion_tokens": int(req.max_completion_tokens),
        }

    store = MinioStore.from_config()
    store.ensure_bucket()

    endpoint = req.vlm_endpoint or VLM_ENDPOINT
    if not endpoint:
        raise ValueError(
            "VLM endpoint is not configured. Provide service args or pass 'vlm_endpoint' in the request."
        )

    vlm = VlmClient(
        endpoint=endpoint,
        timeout_seconds=req.vlm_timeout_seconds or VLM_TIMEOUT_SECONDS,
    )

    summaries: List[ChunkSummaryResult] = []
    ingest_threads: List[threading.Thread] = []

    with tempfile.TemporaryDirectory() as tmpdir:
        local_video = os.path.join(tmpdir, asset_id)
        print(f"[preprocess] Downloading video from MinIO: {req.minio_video_key}")
        store.get_file(req.minio_video_key, local_video)

        chunker = FrameSampler(max_num_frames=1, resolution=frame_resolution)
        chunks = list(chunker.iter_chunks(local_video, chunk_duration_s=req.chunk_duration_s, chunk_overlap_s=req.chunk_overlap_s))
        total_chunks_count = len(chunks)

        sampler = FrameSampler(max_num_frames=req.max_num_frames, resolution=frame_resolution, deduplicate=False)

        for idx, chunk in enumerate(chunks, start=1):
            chunk_id = f"chunk_{idx:04d}"
            summary_key = store.build_derived_object_key(
                run_id,
                "video",
                asset_id,
                f"chunksum-v1/summaries/{chunk_id}/summary.txt",
            )
            chunk_meta_key = store.build_derived_object_key(
                run_id,
                "video",
                asset_id,
                f"chunksum-v1/summaries/{chunk_id}/metadata.json",
            )

            # Placeholder result; fields updated below
            chunk_result = ChunkSummaryResult(
                chunk_id=chunk_id,
                chunk_index=idx,
                total_chunks=total_chunks_count,
                start_time=float(chunk["start_time"]),
                end_time=float(chunk["end_time"]),
                start_frame=int(chunk["start_frame"]),
                end_frame=int(chunk["end_frame"]),
                minio_key=summary_key,
                chunk_metadata_key=chunk_meta_key,
                summary="",
            )
            summaries.append(chunk_result)

            reuse_params = _summary_params_for_reuse()
            can_reuse = False
            if req.reuse_existing and store.object_exists(summary_key):
                try:
                    old_meta = store.get_json(chunk_meta_key)
                    old_params = old_meta.get("summary_params") if isinstance(old_meta, dict) else None
                    if isinstance(old_params, dict) and old_params == reuse_params:
                        can_reuse = True
                except Exception:
                    can_reuse = False

            # --- VLM summarization + MinIO write (per-chunk error isolation) ---
            try:
                if can_reuse:
                    summary_text = store.get_bytes(summary_key).decode("utf-8", errors="replace")
                    reused = True
                else:
                    frames_dict = sampler.sample_frames_from_video(
                        local_video,
                        [],
                        start_frame=chunk.get("start_frame"),
                        end_frame=chunk.get("end_frame"),
                    )
                    print(f"[preprocess] Sampled {len(frames_dict.get('frames', []))} frames for {chunk_id} ({idx}/{total_chunks_count})")
                    frames = frames_dict.get("frames")
                    if frames is None or len(frames) == 0:
                        summary_text = ""
                    else:
                        print(f"[preprocess] Calling VLM for {chunk_id} ({idx}/{total_chunks_count}) frames={len(frames)}")
                        summary_text = vlm.summarize_frames(
                            frames,
                            prompt=req.prompt,
                            max_completion_tokens=req.max_completion_tokens,
                        )
                    store.put_bytes(
                        summary_key,
                        (summary_text or "").encode("utf-8"),
                        content_type="text/plain; charset=utf-8",
                    )
                    reused = False

                chunk_result.summary = summary_text
                chunk_result.reused = reused

            except Exception as exc:
                import traceback as _tb
                err_msg = f"{type(exc).__name__}: {exc}"
                print(f"[preprocess] ERROR processing {chunk_id}: {err_msg}")
                _tb.print_exc()
                chunk_result.error = err_msg
                chunk_result.ingest_status = "skipped"
                # Still write metadata.json to record the failure in MinIO
                try:
                    store.put_json(
                        chunk_meta_key,
                        {
                            "chunk_id": chunk_id,
                            "chunk_index": idx,
                            "start_time": float(chunk["start_time"]),
                            "end_time": float(chunk["end_time"]),
                            "start_frame": int(chunk["start_frame"]),
                            "end_frame": int(chunk["end_frame"]),
                            "summary_params": reuse_params,
                            "reused": False,
                            "error": err_msg,
                        },
                    )
                except Exception:
                    pass
                continue  # skip ingest for this chunk

            # --- Async ingest (runs in background, collected for join at end) ---
            t = _ingest_chunk_async(
                store._bucket,
                summary_key,
                summary_text=summary_text,
                meta={
                    "tags": req.tags,
                    "chunk_id": chunk_id,
                    "chunk_index": idx,
                    "asset_id": asset_id,
                    "run_id": run_id,
                    "minio_video_key": req.minio_video_key,
                    "start_time": float(chunk["start_time"]),
                    "end_time": float(chunk["end_time"]),
                    "start_frame": int(chunk["start_frame"]),
                    "end_frame": int(chunk["end_frame"]),
                    "summary_minio_key": summary_key,
                    "reused": reused,
                },
                result=chunk_result,
            )
            if t is not None:
                ingest_threads.append(t)

            if on_chunk is not None:
                on_chunk(chunk_result)

            # metadata.json: keeps summary_params for reuse_existing logic
            store.put_json(
                chunk_meta_key,
                {
                    "chunk_id": chunk_id,
                    "chunk_index": idx,
                    "start_time": float(chunk["start_time"]),
                    "end_time": float(chunk["end_time"]),
                    "start_frame": int(chunk["start_frame"]),
                    "end_frame": int(chunk["end_frame"]),
                    "summary_params": reuse_params,
                    "reused": reused,
                },
            )

        # --- Final manifest (written after all chunks; ingest threads still running in background) ---
        manifest_key = store.build_derived_object_key(
            run_id,
            "video",
            asset_id,
            "chunksum-v1/manifest.json",
        )
        store.put_json(
            manifest_key,
            {
                "schema": "chunksum-manifest-v1",
                "job_id": job_id,
                "run_id": run_id,
                "asset_id": asset_id,
                "minio_video_key": req.minio_video_key,
                "created_at_epoch_s": time.time(),
                "params": {
                    "chunk_duration_s": int(req.chunk_duration_s),
                    "chunk_overlap_s": int(req.chunk_overlap_s),
                    "max_num_frames": int(req.max_num_frames),
                    "frame_resolution": frame_resolution,
                    "prompt": str(req.prompt),
                    "max_completion_tokens": int(req.max_completion_tokens),
                    "vlm_endpoint": str(req.vlm_endpoint or VLM_ENDPOINT),
                    "vlm_timeout_seconds": int(req.vlm_timeout_seconds or VLM_TIMEOUT_SECONDS),
                    "reuse_existing": bool(req.reuse_existing),
                },
                "chunk_count": len(summaries),
                "succeeded_chunks": sum(1 for s in summaries if s.error is None),
                "failed_chunks": sum(1 for s in summaries if s.error is not None),
                "chunks": [
                    {
                        "chunk_id": s.chunk_id,
                        "chunk_index": int(s.chunk_index),
                        "summary_minio_key": s.minio_key,
                        "metadata_minio_key": s.chunk_metadata_key,
                        "reused": bool(s.reused),
                        "ingest_status": s.ingest_status,
                        **({"error": s.error} if s.error else {}),
                    }
                    for s in summaries
                ],
            },
        )

    # Wait for all ingest threads to finish before computing final counts and returning
    if ingest_threads:
        print(f"[preprocess] Waiting for {len(ingest_threads)} ingest thread(s) to complete...")
        for t in ingest_threads:
            t.join()

    succeeded = sum(1 for s in summaries if s.error is None)
    failed = len(summaries) - succeeded
    ingest_ok = sum(1 for s in summaries if s.ingest_status == "ok")
    ingest_failed = sum(1 for s in summaries if s.ingest_status == "failed")
    elapsed = time.time() - t0
    print(
        f"[preprocess] Done: {succeeded}/{len(summaries)} chunks summarized, "
        f"{ingest_ok} ingested, {ingest_failed} ingest-failed, elapsed_s={elapsed:.1f}"
    )
    return PreprocessResponse(
        job_id=job_id,
        run_id=run_id,
        asset_id=asset_id,
        minio_video_key=req.minio_video_key,
        elapsed_seconds=elapsed,
        total_chunks=len(summaries),
        succeeded_chunks=succeeded,
        failed_chunks=failed,
        ingest_ok_chunks=ingest_ok,
        ingest_failed_chunks=ingest_failed,
    )
