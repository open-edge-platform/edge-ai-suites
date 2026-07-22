"""FastAPI application for videostream-analytics microservice."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from shared.config import (
    AppConfig,
    SourceConfig,
    MotionConfig,
    SegmentConfig,
    StaticConfig,
    PrefilterConfig,
    RecordingConfig,
    RoiConfig,
    HealthConfig,
    KeepaliveConfig,
)
from source_worker import SourceManager

logger = logging.getLogger(__name__)

_manager: SourceManager | None = None


# --- Request Models (module-level for FastAPI schema resolution) ---


class PipelineConfig(BaseModel):
    """Nested pipeline configuration sent by MCP server.

    All sub-blocks optional — per-source defaults fill the gaps.
    """

    model_config = ConfigDict(extra="forbid")

    motion: MotionConfig | None = None
    segment: SegmentConfig | None = None
    static: StaticConfig | None = None
    prefilter: PrefilterConfig | None = None
    roi: RoiConfig | None = None
    recording: RecordingConfig | None = None
    health: HealthConfig | None = None
    keepalive: KeepaliveConfig | None = None


class RegisterSourceRequest(BaseModel):
    """`POST /register_source` body — must match MCP `analyticsRegister` exactly.

    Hard cutover from the old flat schema: `rtsp_url`, top-level `motion/...`,
    and `use_case` are no longer accepted. `extra="forbid"` makes drift fail
    loudly with 422 instead of silently dropping fields.
    """

    model_config = ConfigDict(extra="forbid")

    source_id: str
    source_url: str
    webhook_url: str | None = None
    data_dir: str | None = None
    pipeline: PipelineConfig = Field(default_factory=PipelineConfig)


class UnregisterSourceRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_id: str


class UpdatePipelineRequest(BaseModel):
    """`PUT /sources/{id}/pipeline` body — nested form, no flat fallback."""

    model_config = ConfigDict(extra="forbid")

    pipeline: PipelineConfig = Field(default_factory=PipelineConfig)


def get_manager() -> SourceManager:
    if _manager is None:
        raise RuntimeError("SourceManager not initialized")
    return _manager


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _manager
    config: AppConfig = app.state.config
    _manager = SourceManager(config)
    logger.info("videostream-analytics started on :%d", config.server.port)
    yield
    _manager.stop_all()
    logger.info("videostream-analytics shut down")


def create_app(config: AppConfig) -> FastAPI:
    app = FastAPI(
        title="videostream-analytics",
        version="0.1.0",
        description="Smart Building video stream analytics microservice",
        lifespan=lifespan,
    )
    app.state.config = config

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ):
        """Surface pydantic ValidationError as 422 with the offending fields."""
        errors = exc.errors()
        unknown_fields = [
            ".".join(str(p) for p in e.get("loc", []) if p != "body")
            for e in errors
            if e.get("type") == "extra_forbidden"
        ]
        return JSONResponse(
            status_code=422,
            content={
                "detail": errors,
                "unknown_fields": unknown_fields,
                "hint": (
                    "request body must match the nested-pipeline schema "
                    "(source_id/source_url/webhook_url/data_dir/pipeline.{motion,segment,prefilter,recording,health})"
                ),
            },
        )

    # --- Endpoints ---

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok", "service": "videostream-analytics"}

    @app.get("/sources")
    async def list_sources() -> list[dict[str, Any]]:
        """Return a bare array — MCP `monitor-ctl.ts` indexes by `s.source_id`."""
        mgr = get_manager()
        return mgr.get_sources()

    def _source_status(source_id: str) -> dict[str, Any]:
        mgr = get_manager()
        status = mgr.get_source_status(source_id)
        if status is None:
            raise HTTPException(status_code=404, detail=f"Source not found: {source_id}")
        return status

    @app.get("/sources/{source_id}")
    async def get_source(source_id: str) -> dict[str, Any]:
        return _source_status(source_id)

    @app.get("/sources/{source_id}/status")
    async def get_source_status(source_id: str) -> dict[str, Any]:
        """MCP's `analyticsSourceExists` calls this path."""
        return _source_status(source_id)

    @app.post("/register_source")
    async def register_source(req: RegisterSourceRequest) -> dict[str, Any]:
        mgr = get_manager()
        source = SourceConfig(
            source_id=req.source_id,
            source_url=req.source_url,
            webhook_url=req.webhook_url,
            data_dir=req.data_dir,
            motion=req.pipeline.motion,
            segment=req.pipeline.segment,
            static=req.pipeline.static,
            prefilter=req.pipeline.prefilter,
            roi=req.pipeline.roi,
            recording=req.pipeline.recording,
            health=req.pipeline.health,
            keepalive=req.pipeline.keepalive,
        )
        return mgr.register_source(source)

    @app.delete("/unregister_source")
    async def unregister_source(req: UnregisterSourceRequest) -> dict[str, Any]:
        mgr = get_manager()
        result = mgr.unregister_source(req.source_id)
        if result["status"] == "not_found":
            raise HTTPException(
                status_code=404, detail=f"Source not found: {req.source_id}"
            )
        return result

    @app.post("/sources/{source_id}/stop")
    async def stop_source(source_id: str) -> dict[str, Any]:
        mgr = get_manager()
        result = mgr.unregister_source(source_id)
        if result["status"] == "not_found":
            raise HTTPException(status_code=404, detail=f"Source not found: {source_id}")
        return result

    @app.post("/sources/{source_id}/restart")
    async def restart_source(source_id: str) -> dict[str, Any]:
        mgr = get_manager()
        status = mgr.get_source_status(source_id)
        if status is None:
            raise HTTPException(status_code=404, detail=f"Source not found: {source_id}")
        bundle = mgr._bundles.get(source_id)
        if bundle is None:
            raise HTTPException(status_code=404, detail=f"Source not found: {source_id}")
        bundle.pipeline.stop()
        bundle.pipeline.start()
        if bundle.recorder is not None:
            bundle.recorder.stop()
            bundle.recorder.start()
        return {"status": "restarted", "source_id": source_id}

    @app.post("/sources/{source_id}/pause")
    async def pause_source(source_id: str) -> dict[str, Any]:
        mgr = get_manager()
        result = mgr.pause_source(source_id)
        if result["status"] == "not_found":
            raise HTTPException(status_code=404, detail=f"Source not found: {source_id}")
        return result

    @app.post("/sources/{source_id}/resume")
    async def resume_source(source_id: str) -> dict[str, Any]:
        mgr = get_manager()
        result = mgr.resume_source(source_id)
        if result["status"] == "not_found":
            raise HTTPException(status_code=404, detail=f"Source not found: {source_id}")
        return result

    @app.post("/sources/{source_id}/keepalive")
    async def keepalive_source(source_id: str) -> dict[str, Any]:
        """Phase 8: MCP server pings this every ~30s while monitor is online.

        Body is ignored (may be empty). Watchdog auto-pauses the source if no
        keepalive arrives within `pipeline.keepalive.timeout_seconds`.
        """
        mgr = get_manager()
        result = mgr.keepalive_source(source_id)
        if result["status"] == "not_found":
            raise HTTPException(status_code=404, detail=f"Source not found: {source_id}")
        return result

    @app.put("/sources/{source_id}/pipeline")
    async def update_pipeline(source_id: str, req: UpdatePipelineRequest) -> dict[str, Any]:
        mgr = get_manager()
        result = mgr.update_pipeline_config(
            source_id=source_id,
            motion=req.pipeline.motion,
            segment=req.pipeline.segment,
            prefilter=req.pipeline.prefilter,
            roi=req.pipeline.roi,
            recording=req.pipeline.recording,
            health=req.pipeline.health,
        )
        if result["status"] == "not_found":
            raise HTTPException(status_code=404, detail=f"Source not found: {source_id}")
        return result

    @app.delete("/sources/{source_id}")
    async def delete_source(source_id: str) -> dict[str, Any]:
        mgr = get_manager()
        result = mgr.unregister_source(source_id)
        if result["status"] == "not_found":
            raise HTTPException(status_code=404, detail=f"Source not found: {source_id}")
        return result

    return app
