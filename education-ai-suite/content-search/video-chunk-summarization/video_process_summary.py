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

Run:
    uvicorn video_process_summary:app --host 0.0.0.0 --port 8001

Env:
    VLM_ENDPOINT=http://localhost:9900/v1/chat/completions
  VLM_TIMEOUT_SECONDS=300
"""

from __future__ import annotations

import base64
import io
import os
import sys
import tempfile
import time
import uuid
from typing import Any, Dict, List, Optional

import requests
from fastapi import FastAPI
from PIL import Image
from pydantic import BaseModel, Field

from frame_sampler import FrameSampler

# Allow importing shared repo modules when running from this subfolder.
_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from content_search_minio.minio_client import MinioStore

# ---------------------------------------------------------------------------
# Settings (override via env vars)
# ---------------------------------------------------------------------------

VLM_ENDPOINT = os.environ.get("VLM_ENDPOINT")
VLM_TIMEOUT_SECONDS = int(os.environ.get("VLM_TIMEOUT_SECONDS", "300"))

DEFAULT_CHUNK_DURATION_S = int(os.environ.get("PREPROCESS_CHUNK_DURATION_S", "30"))
DEFAULT_CHUNK_OVERLAP_S = int(os.environ.get("PREPROCESS_CHUNK_OVERLAP_S", "4"))
DEFAULT_MAX_NUM_FRAMES = int(os.environ.get("PREPROCESS_MAX_NUM_FRAMES", "8"))
DEFAULT_FRAME_WIDTH = int(os.environ.get("PREPROCESS_FRAME_WIDTH", "0"))
DEFAULT_FRAME_HEIGHT = int(os.environ.get("PREPROCESS_FRAME_HEIGHT", "0"))


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

    chunk_duration_s: int = Field(DEFAULT_CHUNK_DURATION_S, ge=1, description="Chunk duration in seconds")
    chunk_overlap_s: int = Field(DEFAULT_CHUNK_OVERLAP_S, ge=0, description="Chunk overlap in seconds")
    max_num_frames: int = Field(DEFAULT_MAX_NUM_FRAMES, ge=1, description="Max sampled frames per chunk")

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


class PreprocessResponse(BaseModel):
    job_id: str
    run_id: str
    asset_id: str
    minio_video_key: str
    summaries: List[ChunkSummaryResult]
    elapsed_seconds: float


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


app = FastAPI(
    title="Video Preprocess Service",
    version="0.2.0",
    description="Decode/chunk/sample a MinIO video, call vlm-openvino-serving, write chunk summaries to MinIO.",
)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/preprocess", response_model=PreprocessResponse)
def submit_preprocess(req: PreprocessRequest) -> PreprocessResponse:
    """Synchronous preprocess: decode/chunk/sample → summarize → write to MinIO → return result."""
    job_id = str(req.job_id) if req.job_id else str(uuid.uuid4())
    t0 = time.time()
    return _process(job_id, req, t0)


def _process(job_id: str, req: PreprocessRequest, t0: float) -> PreprocessResponse:
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
            "VLM endpoint is not configured. Set VLM_ENDPOINT env var or pass 'vlm_endpoint' in the request."
        )

    vlm = VlmClient(
        endpoint=endpoint,
        timeout_seconds=req.vlm_timeout_seconds or VLM_TIMEOUT_SECONDS,
    )

    summaries: List[ChunkSummaryResult] = []

    with tempfile.TemporaryDirectory() as tmpdir:
        local_video = os.path.join(tmpdir, asset_id)
        print(f"[preprocess] Downloading video from MinIO: {req.minio_video_key}")
        store.get_file(req.minio_video_key, local_video)

        chunker = FrameSampler(max_num_frames=1, resolution=frame_resolution)
        chunks = chunker.iter_chunks(local_video, chunk_duration_s=req.chunk_duration_s, chunk_overlap_s=req.chunk_overlap_s)

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
                print(f"[preprocess] Sampled {len(frames_dict.get('frames', []))} frames for {chunk_id}")
                frames = frames_dict.get("frames")
                if frames is None or len(frames) == 0:
                    # still write an empty summary file for traceability
                    summary_text = ""
                else:
                    print(f"[preprocess] Calling VLM for {chunk_id} frames={len(frames)}")
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

            summaries.append(
                ChunkSummaryResult(
                    chunk_id=chunk_id,
                    chunk_index=idx,
                    start_time=float(chunk["start_time"]),
                    end_time=float(chunk["end_time"]),
                    start_frame=int(chunk["start_frame"]),
                    end_frame=int(chunk["end_frame"]),
                    minio_key=summary_key,
                    chunk_metadata_key=chunk_meta_key,
                    summary=summary_text,
                    reused=reused,
                )
            )

        # Completion marker for downstream consumers (e.g., document ingestion).
        # This lets event-driven pipelines know when all chunk summaries are expected to exist.
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
                "chunks": [
                    {
                        "chunk_id": s.chunk_id,
                        "chunk_index": int(s.chunk_index),
                        "summary_minio_key": s.minio_key,
                        "metadata_minio_key": s.chunk_metadata_key,
                        "reused": bool(s.reused),
                    }
                    for s in summaries
                ],
            },
        )
    print(f'[preprocess] Finished video processing + summarization and minio upload, elapsed_s={time.time() - t0:.1f}')
    return PreprocessResponse(
        job_id=job_id,
        run_id=run_id,
        asset_id=asset_id,
        minio_video_key=req.minio_video_key,
        summaries=summaries,
        elapsed_seconds=time.time() - t0,
    )
