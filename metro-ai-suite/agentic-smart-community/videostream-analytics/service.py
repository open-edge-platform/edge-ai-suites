"""FastAPI application for videostream-analytics microservice."""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager, contextmanager
from pathlib import Path
from typing import Annotated, Any
from urllib.parse import urlsplit

from fastapi import FastAPI, HTTPException, Request
from fastapi import Path as PathParam
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, field_validator

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
    SecurityConfig,
    expand_user_path,
    resolve_contained_file,
)
from source_worker import SourceManager

logger = logging.getLogger(__name__)

_manager: SourceManager | None = None

# Same shape as the dashboard's `monitorIdSchema`
# (packages/mcp-server/src/dashboard/router.ts). A source_id reaches the
# filesystem via `<data_dir>/<source_id>`, so keeping the two sides identical
# means a monitor id that MCP accepts is exactly one VSA accepts.
SOURCE_ID_PATTERN = r"^[A-Za-z0-9_-]{1,128}$"

_MAX_URL_LEN = 2048
_MAX_PATH_LEN = 4096

# Path-parameter form of the same constraint. Applying it here means a
# traversal attempt like `/sources/..%2F..%2Ftmp` is refused with 422 before it
# can reach the registry lookup.
SourceIdPath = Annotated[str, PathParam(pattern=SOURCE_ID_PATTERN)]


def _reject_control_chars(value: str, field: str) -> str:
    """Reject NUL and other control characters.

    NUL in particular turns into a `ValueError` deep inside `os` calls, and
    control characters corrupt the log lines and the RESTler network log alike.
    """
    if any(ord(ch) < 0x20 or ord(ch) == 0x7F for ch in value):
        raise ValueError(f"{field} must not contain control characters")
    return value


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

    source_id: str = Field(pattern=SOURCE_ID_PATTERN)
    source_url: str = Field(min_length=1, max_length=_MAX_URL_LEN)
    webhook_url: str | None = Field(default=None, max_length=_MAX_URL_LEN)
    data_dir: str | None = Field(default=None, max_length=_MAX_PATH_LEN)
    pipeline: PipelineConfig = Field(default_factory=PipelineConfig)

    @field_validator("source_url")
    @classmethod
    def _check_source_url(cls, v: str) -> str:
        return _reject_control_chars(v.strip(), "source_url")

    @field_validator("webhook_url")
    @classmethod
    def _check_webhook_url(cls, v: str | None) -> str | None:
        """Require a plain http(s) URL — the sink POSTs events to it verbatim.

        Host-level restriction (private ranges only) is deliberately NOT here
        yet; this only rules out non-HTTP schemes and embedded credentials.
        """
        if v is None:
            return None
        v = _reject_control_chars(v.strip(), "webhook_url")
        parts = urlsplit(v)
        if parts.scheme not in ("http", "https"):
            raise ValueError("webhook_url must use the http or https scheme")
        if not parts.hostname:
            raise ValueError("webhook_url must include a host")
        if parts.username or parts.password:
            raise ValueError("webhook_url must not embed credentials")
        return v

    @field_validator("data_dir")
    @classmethod
    def _check_data_dir(cls, v: str | None) -> str | None:
        """Absolute paths only. Containment is enforced in SourceManager.

        Rejecting relative paths here is what turns the reported
        `data_dir: "fuzzstring"` 500 (PermissionError from `os.makedirs`
        relative to the service CWD) into a 422.
        """
        if v is None:
            return None
        v = _reject_control_chars(v.strip(), "data_dir")
        if not v:
            return None
        if not os.path.isabs(os.path.expanduser(v)):
            raise ValueError("data_dir must be an absolute path")
        return v


class UpdatePipelineRequest(BaseModel):
    """`PUT /sources/{id}/pipeline` body — nested form, no flat fallback."""

    model_config = ConfigDict(extra="forbid")

    pipeline: PipelineConfig = Field(default_factory=PipelineConfig)


def validate_source_url(url: str, security: SecurityConfig) -> None:
    """Reject a `source_url` whose scheme is not an allowed stream transport.

    `source_url` ends up as the argument to `ffmpeg -i` and to
    `cv2.VideoCapture(..., CAP_FFMPEG)`. ffmpeg will happily open `file:`,
    `concat:`, `subfile:`, `data:` and friends, mux the result into `data_dir`,
    and the MCP dashboard then serves that directory as mp4 clips — so an
    unrestricted scheme here is an arbitrary-file-read that exfiltrates over a
    supported API. Raises ValueError (-> 400) rather than HTTPException so the
    same check is usable outside the request path.
    """
    scheme = urlsplit(url).scheme.lower()
    if not scheme:
        raise ValueError(
            "source_url must include a scheme "
            f"({'/'.join(_effective_schemes(security))})"
        )
    if scheme not in _effective_schemes(security):
        raise ValueError(f"source_url scheme '{scheme}' is not allowed")


def _effective_schemes(security: SecurityConfig) -> tuple[str, ...]:
    schemes = [s.lower() for s in security.allowed_source_schemes]
    if security.allow_file_source:
        schemes.append("file")
    return tuple(dict.fromkeys(schemes))


def get_manager() -> SourceManager:
    if _manager is None:
        raise RuntimeError("SourceManager not initialized")
    return _manager


@contextmanager
def _guard(operation: str):
    """Turn business-layer failures into deliberate status codes.

    Any 500 produced by user input is an SDL bug, and the business layer raises
    plain `OSError`/`ValueError` for input it cannot honour (`os.makedirs` on an
    unwritable path, a `data_dir` outside the permitted roots, inverted segment
    durations). Those are the caller's fault → 400.

    `ConnectionError` is special-cased even though it is an `OSError` subclass:
    `ContinuousRecorder` raises it when ffmpeg is missing from PATH, which is a
    server-side environment defect, not a bad request → 503.

    The exception message is logged but NOT returned. Messages routinely embed
    absolute server paths (`Permission denied: '/home/.../segments'`), and this
    API has no authentication, so echoing them hands out reconnaissance.
    """
    try:
        yield
    except HTTPException:
        raise
    except ConnectionError as exc:
        logger.error("[%s] dependency unavailable: %s", operation, exc)
        raise HTTPException(
            status_code=503,
            detail={"error": "dependency_unavailable", "operation": operation},
        ) from exc
    except (OSError, ValueError) as exc:
        logger.warning(
            "[%s] rejected: %s: %s", operation, type(exc).__name__, exc
        )
        raise HTTPException(
            status_code=400,
            detail={
                "error": "invalid_request",
                "reason": type(exc).__name__,
                "operation": operation,
            },
        ) from exc


def _available_devices() -> list[str]:
    """Best-effort list of OpenVINO inference devices; ``["CPU"]`` on failure."""
    try:
        import openvino as ov

        return list(ov.Core().available_devices) or ["CPU"]
    except Exception:
        return ["CPU"]


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
        description="Smart Community video stream analytics microservice",
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
        # pydantic v2 puts the live exception object in `ctx["error"]` for any
        # error raised by a `field_validator`/`model_validator`, and `url` is a
        # docs link. Neither is JSON-serializable/useful — passing the raw list
        # to JSONResponse turns a 422 into a 500 inside the encoder. `msg`
        # already carries the validator's text.
        safe_errors = [
            {k: v for k, v in e.items() if k not in ("ctx", "url")} for e in errors
        ]
        return JSONResponse(
            status_code=422,
            content={
                "detail": jsonable_encoder(safe_errors),
                "unknown_fields": unknown_fields,
                "hint": (
                    "request body must match the nested-pipeline schema "
                    "(source_id/source_url/webhook_url/data_dir/pipeline.{motion,segment,prefilter,recording,health})"
                ),
            },
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        """Log the traceback, return a body with nothing server-side in it.

        Anything reaching here is a genuine defect (the deliberate 400/503
        cases go through `_guard`), so it must be loud in the log and opaque on
        the wire.
        """
        logger.exception(
            "unhandled error on %s %s", request.method, request.url.path
        )
        return JSONResponse(
            status_code=500, content={"error": "internal_error"}
        )

    # --- Endpoints ---
    #
    # Every endpoint that touches SourceManager is declared `def`, NOT
    # `async def`. The manager is synchronous and blocking: `StreamPipeline.stop`
    # (rtsp_monitor.py) and `ContinuousRecorder.stop` (continuous_recorder.py)
    # each `join(timeout=10)` a worker thread that may be parked in
    # `cap.read()`/ffmpeg. Under `async def` those 10-20 seconds run ON the
    # event loop, so one DELETE stalls *every* concurrent request — the origin
    # of the fuzz run's timeout findings. A plain `def` makes FastAPI dispatch
    # the call to its threadpool, keeping the loop free.
    #
    # This is why SourceManager is internally locked: with `def` endpoints the
    # requests genuinely run in parallel.

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok", "service": "videostream-analytics"}

    @app.get("/capabilities/prefilter")
    async def prefilter_capabilities() -> dict[str, Any]:
        """Advertise the prefilter model's selectable ``target_classes``.

        The valid class set is whatever the deployed OpenVINO model embeds in
        its ``rt_info`` labels, so it can only be known at runtime. When
        ``labels_source`` is not ``embedded`` the returned ``class_names`` are
        an untrustworthy COCO fallback and callers should confirm names rather
        than treat the list as authoritative.
        """
        pf = config.defaults.prefilter
        if not pf.model_path or not Path(pf.model_path).exists():
            return {
                "enabled": pf.enabled,
                "model_path": pf.model_path,
                "class_names": [],
                "labels_source": "unavailable",
                "available_devices": _available_devices(),
            }
        from stream_monitor.pipeline.prefilter_yolo import read_model_labels

        class_names, labels_source = read_model_labels(pf.model_path)
        return {
            "enabled": pf.enabled,
            "model_path": pf.model_path,
            "class_names": class_names,
            "labels_source": labels_source,
            "available_devices": _available_devices(),
        }

    def _model_roots() -> list[str]:
        """Directories a request-supplied ``model_path`` may live under.

        The deployment's own model directory, plus any explicit escape hatch.
        Derived from ``defaults.prefilter.model_path`` rather than from
        ``MODEL_DIR``: that variable is host-side only (docker-compose uses it
        for the read-only bind mount and never puts it in the container
        environment), and the container sets ``HOME=/tmp``, so a ``~/models``
        fallback here would resolve to the wrong directory entirely. The
        configured model path is already absolute and container-valid.
        """
        roots = []
        if config.defaults.prefilter.model_path:
            roots.append(os.path.dirname(config.defaults.prefilter.model_path))
        roots.extend(config.security.allowed_model_roots)
        return [r for r in roots if r]

    def validate_model_path(prefilter: PrefilterConfig | None) -> str:
        """Confine a request-supplied ``prefilter.model_path`` to a model root.

        Returns the resolved path (``""`` when the request omitted it and the
        deployment default should be inherited — trusted config, deliberately
        not re-checked), and also writes it back onto ``prefilter`` so the
        running pipeline (rtsp_monitor._init_prefilter) loads the resolved path
        rather than the raw request string.

        Callers must pass the RETURN VALUE on to `_validate_target_classes`
        instead of letting it re-read ``prefilter.model_path``. The write-back
        alone is not enough: taint is tracked on the `prefilter` object, so
        reading the attribute off it again re-derives the unvalidated value and
        `py/path-injection` still reports `Path(model_path)`. Only the returned
        string carries the containment check on its data flow.

        Raises ValueError (-> 400 via `_guard`), matching `validate_source_url`.
        """
        if not prefilter or not prefilter.model_path:
            return ""
        resolved = resolve_contained_file(
            _model_roots(), expand_user_path(prefilter.model_path), "model"
        )
        prefilter.model_path = resolved
        return resolved

    def _validate_target_classes(
        prefilter: PrefilterConfig | None, model_path: str
    ) -> None:
        """Reject ``target_classes`` not in the model's embedded label set.

        Only hard-fails when labels are trustworthy (``embedded``); a
        ``fallback_coco``/``unavailable`` label set is a guess, so we let the
        request through rather than block on an untrusted list.

        ``model_path`` is the confined, resolved path returned by
        `validate_model_path` — empty when the request omitted it, in which case
        the trusted deployment default applies. It is passed in rather than read
        back off ``prefilter`` on purpose; see `validate_model_path`.
        """
        if not prefilter or not prefilter.enabled or not prefilter.target_classes:
            return
        model_path = model_path or config.defaults.prefilter.model_path
        if not model_path:
            return
        try:
            model_exists = Path(model_path).exists()
        except OSError:
            # `exists()` only swallows ENOENT/ENOTDIR/ELOOP; an un-stat-able
            # path (ENAMETOOLONG, EACCES, …) propagates. Request-supplied paths
            # no longer reach this — `validate_model_path` rejects them with a
            # 400 first — but the *configured* default is not containment-
            # checked, so a mistyped config.yaml can still land here. Such a
            # path cannot name a readable model either, so treat it exactly
            # like a missing one: labels unavailable, skip the check rather
            # than crash.
            model_exists = False
        if not model_exists:
            return
        from stream_monitor.pipeline.prefilter_yolo import read_model_labels

        class_names, labels_source = read_model_labels(model_path)
        if labels_source != "embedded":
            return
        unknown = [c for c in prefilter.target_classes if c not in class_names]
        if unknown:
            raise HTTPException(
                status_code=422,
                detail={
                    "error": "unknown target_classes",
                    "unknown": unknown,
                    "class_names": class_names,
                },
            )

    @app.get("/sources")
    def list_sources() -> list[dict[str, Any]]:
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
    def get_source(source_id: SourceIdPath) -> dict[str, Any]:
        return _source_status(source_id)

    @app.get("/sources/{source_id}/status")
    def get_source_status(source_id: SourceIdPath) -> dict[str, Any]:
        """MCP's `analyticsSourceExists` calls this path."""
        return _source_status(source_id)

    @app.post("/register_source")
    def register_source(req: RegisterSourceRequest) -> dict[str, Any]:
        mgr = get_manager()
        with _guard("register_source"):
            validate_source_url(req.source_url, config.security)
            model_path = validate_model_path(req.pipeline.prefilter)
            _validate_target_classes(req.pipeline.prefilter, model_path)
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
        with _guard("register_source"):
            result = mgr.register_source(source)
        if result["status"] == "registration_in_progress":
            # Another request is mid-build for this id. Refusing beats queueing:
            # the loser would hold a threadpool worker through a 20s teardown.
            raise HTTPException(
                status_code=409,
                detail={
                    "error": "registration_in_progress",
                    "source_id": req.source_id,
                },
            )
        return result

    @app.post("/sources/{source_id}/stop")
    def stop_source(source_id: SourceIdPath) -> dict[str, Any]:
        mgr = get_manager()
        with _guard("stop_source"):
            result = mgr.unregister_source(source_id)
        if result["status"] == "not_found":
            raise HTTPException(status_code=404, detail=f"Source not found: {source_id}")
        return result

    @app.post("/sources/{source_id}/restart")
    def restart_source(source_id: SourceIdPath) -> dict[str, Any]:
        mgr = get_manager()
        with _guard("restart_source"):
            result = mgr.restart_source(source_id)
        if result["status"] == "not_found":
            raise HTTPException(status_code=404, detail=f"Source not found: {source_id}")
        return result

    @app.post("/sources/{source_id}/pause")
    def pause_source(source_id: SourceIdPath) -> dict[str, Any]:
        mgr = get_manager()
        with _guard("pause_source"):
            result = mgr.pause_source(source_id)
        if result["status"] == "not_found":
            raise HTTPException(status_code=404, detail=f"Source not found: {source_id}")
        return result

    @app.post("/sources/{source_id}/resume")
    def resume_source(source_id: SourceIdPath) -> dict[str, Any]:
        mgr = get_manager()
        with _guard("resume_source"):
            result = mgr.resume_source(source_id)
        if result["status"] == "not_found":
            raise HTTPException(status_code=404, detail=f"Source not found: {source_id}")
        return result

    @app.post("/sources/{source_id}/keepalive")
    def keepalive_source(source_id: SourceIdPath) -> dict[str, Any]:
        """MCP server pings this every ~30s while monitor is online.

        Body is ignored (may be empty). Watchdog auto-pauses the source if no
        keepalive arrives within `pipeline.keepalive.timeout_seconds`.
        """
        mgr = get_manager()
        result = mgr.keepalive_source(source_id)
        if result["status"] == "not_found":
            raise HTTPException(status_code=404, detail=f"Source not found: {source_id}")
        return result

    @app.put("/sources/{source_id}/pipeline")
    def update_pipeline(
        source_id: SourceIdPath, req: UpdatePipelineRequest
    ) -> dict[str, Any]:
        mgr = get_manager()
        with _guard("update_pipeline"):
            model_path = validate_model_path(req.pipeline.prefilter)
            _validate_target_classes(req.pipeline.prefilter, model_path)
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
    def delete_source(source_id: SourceIdPath) -> dict[str, Any]:
        mgr = get_manager()
        with _guard("delete_source"):
            result = mgr.unregister_source(source_id)
        if result["status"] == "not_found":
            raise HTTPException(status_code=404, detail=f"Source not found: {source_id}")
        return result

    return app
