import logging
import os
import threading

from pipeline import Pipeline
from dto.transcription_dto import TranscriptionRequest
from dto.audiosource import AudioSource
from utils.config_loader import config
from utils.storage_manager import StorageManager
from utils.session_manager import generate_session_id
from utils import session_store
from utils.session_paths import SessionPaths
from utils.session_log import session_log_handler, bind_session
from utils.stage_tracker import stage_tracker
from utils.va_completion import wait_for_va_completion
from components.va.va_pipeline_service import VideoAnalyticsPipelineService, PipelineOptions

logger = logging.getLogger(__name__)


class _OrchestrationError(Exception):
    pass


class _Cancelled(Exception):
    pass


class _ConcurrencyLimit(_OrchestrationError):
    pass


# Number of /sessions/process that may run simultaneously in this process.
# Deliberately small and not exposed to clients; serves as a safety valve so a
# flood of concurrent requests cannot exhaust GPU/CPU/memory.
_MAX_CONCURRENT_SESSIONS = 2


class _RunningTask:
    """Handle for one in-flight session's background work (A1 registry)."""

    def __init__(self, thread, cancel_event):
        self.thread = thread
        self.cancel_event = cancel_event
        self.va_service = None


_RUNNING: dict[str, _RunningTask] = {}
_RUNNING_LOCK = threading.Lock()


def running_session_ids() -> list:
    with _RUNNING_LOCK:
        return list(_RUNNING.keys())


def request_cancel(session_id: str) -> bool:
    """Set cancel flag and tear down VA subprocesses if any. Returns True if a
    running task was found."""
    with _RUNNING_LOCK:
        task = _RUNNING.get(session_id)
        if task is None:
            return False
        task.cancel_event.set()
        va = task.va_service
    if va is not None:
        try:
            va.stop_all_pipelines(timeout=5.0)
        except Exception as e:
            logger.error(f"[orchestrator] cancel: failed to stop VA for {session_id}: {e}", exc_info=True)
    return True


def _now_iso() -> str:
    from utils.session_store import _now_iso as _store_now
    return _store_now()


def _va_output_dir(session_id: str) -> str:
    return str(SessionPaths.va_dir(session_id))


def start_process(request: dict) -> str:
    session_id = generate_session_id()
    stages = request.get("stages", [])
    cancel_event = threading.Event()
    thread = threading.Thread(target=_run, args=(session_id, request, stages), daemon=True)
    with _RUNNING_LOCK:
        if len(_RUNNING) >= _MAX_CONCURRENT_SESSIONS:
            raise _ConcurrencyLimit("too many concurrent sessions")
        _RUNNING[session_id] = _RunningTask(thread, cancel_event)
    try:
        thread.start()
    except RuntimeError:
        with _RUNNING_LOCK:
            _RUNNING.pop(session_id, None)
        raise
    session_store.SessionStore.create(session_id, request, stages)
    return session_id


def _run(session_id: str, request: dict, stages: list) -> None:
    with session_log_handler(session_id):
        try:
            _run_inner(session_id, request, stages)
        finally:
            with _RUNNING_LOCK:
                _RUNNING.pop(session_id, None)


def _run_inner(session_id: str, request: dict, stages: list) -> None:
    session_store.SessionStore.update(session_id, state="running")
    _touch_heartbeat(session_id)
    va_error = []
    va_thread = None
    try:
        if "va" in stages:
            va_thread = threading.Thread(
                target=_run_va_safe,
                args=(session_id, request, stages, va_error),
                daemon=True,
            )
            va_thread.start()
        _run_audio_chain(session_id, request, stages, va_thread, va_error)
        _join_va(va_thread, va_error)
        session_store.SessionStore.mark_completed(session_id)
    except _Cancelled:
        session_store.SessionStore.mark_cancelled(session_id)
    except _OrchestrationError as e:
        session_store.SessionStore.mark_failed(session_id, str(e))
    except Exception as e:
        logger.exception(f"[orchestrator] session {session_id} unexpected failure")
        session_store.SessionStore.mark_failed(session_id, f"unexpected error: {e}")
    finally:
        if va_thread is not None:
            va_thread.join()


def _touch_heartbeat(session_id: str) -> None:
    session_store.SessionStore.update(session_id, last_heartbeat=_now_iso())


def _check_cancel(session_id: str) -> None:
    with _RUNNING_LOCK:
        task = _RUNNING.get(session_id)
    if task is not None and task.cancel_event.is_set():
        raise _Cancelled("session cancelled")


def _run_va_safe(session_id: str, request: dict, stages: list, errors: list) -> None:
    bind_session(session_id)
    try:
        _run_va_if_needed(session_id, request, stages)
    except _Cancelled as e:
        errors.append(e)
    except _OrchestrationError as e:
        errors.append(str(e))
    except Exception as e:
        logger.exception(f"[orchestrator] session {session_id} VA thread failure")
        errors.append(f"unexpected va error: {e}")


def _run_audio_chain(session_id: str, request: dict, stages: list,
                     va_thread=None, va_error=None) -> None:
    pipeline = Pipeline(session_id)

    if "transcribe" in stages:
        _check_cancel(session_id)
        session_store.SessionStore.set_stage(session_id, "transcribe", "running")
        audio_path = request.get("audio_path")
        if not audio_path:
            raise _OrchestrationError("stage transcribe requires audio_path")
        tr = TranscriptionRequest(audio_filename=audio_path, source_type=AudioSource.AUDIO_FILE)
        _touch_heartbeat(session_id)
        with stage_tracker(session_id, "transcribe"):
            _drain(pipeline.run_transcription(tr))
        session_store.SessionStore.set_stage(session_id, "transcribe", "done")
        _await_pending_writes()

    if "summarize" in stages:
        _check_cancel(session_id)
        session_store.SessionStore.set_stage(session_id, "summarize", "running")
        _touch_heartbeat(session_id)
        with stage_tracker(session_id, "summarize"):
            _drain(pipeline.run_summarizer())
        session_store.SessionStore.set_stage(session_id, "summarize", "done")
        _await_pending_writes()

    if "mindmap" in stages:
        _check_cancel(session_id)
        session_store.SessionStore.set_stage(session_id, "mindmap", "running")
        _touch_heartbeat(session_id)
        with stage_tracker(session_id, "mindmap"):
            pipeline.run_mindmap()
        session_store.SessionStore.set_stage(session_id, "mindmap", "done")

    if "segmentation" in stages:
        _join_va(va_thread, va_error)
        _check_cancel(session_id)
        session_store.SessionStore.set_stage(session_id, "segmentation", "running")
        _touch_heartbeat(session_id)
        with stage_tracker(session_id, "segmentation"):
            pipeline.run_content_segmentation()
        session_store.SessionStore.set_stage(session_id, "segmentation", "done")

    if "report" in stages:
        _check_cancel(session_id)
        session_store.SessionStore.set_stage(session_id, "report", "running")
        _touch_heartbeat(session_id)
        with stage_tracker(session_id, "report"):
            _drain(pipeline.run_report_generator())
        session_store.SessionStore.set_stage(session_id, "report", "done")


def _join_va(va_thread, va_error) -> None:
    if va_thread is not None:
        va_thread.join()
        if va_error:
            first = va_error[0]
            if isinstance(first, _Cancelled):
                raise _Cancelled(str(first))
            raise _OrchestrationError(first)


def _run_va_if_needed(session_id: str, request: dict, stages: list) -> None:
    if "va" not in stages:
        return
    video_sources = request.get("video_sources") or {}
    wanted = {k: v for k, v in video_sources.items() if v}
    if not wanted:
        raise _OrchestrationError("stage va requires video_sources")

    session_store.SessionStore.set_stage(session_id, "va", "running")

    with stage_tracker(session_id, "va"):
        va_out_dir = _va_output_dir(session_id)
        os.makedirs(va_out_dir, exist_ok=True)

        service = VideoAnalyticsPipelineService()
        service.x_session_id = session_id
        with _RUNNING_LOCK:
            task = _RUNNING.get(session_id)
            if task is not None:
                task.va_service = service

        done = threading.Event()
        final_status = {}

        def _on_done(sid):
            final_status.update(service.pipeline_final_status)
            done.set()

        service.on_all_pipelines_done = _on_done

        options = PipelineOptions(
            output_dir=va_out_dir,
            output_rtsp=config.va_pipeline.output_rtsp_url,
            threshold=config.models.va.threshold,
            record=False,
            output_stream=False,
        )

        launched = 0
        failures = []
        for name, source in wanted.items():
            try:
                ok = service.launch_pipeline(name, source, options)
            except Exception as e:
                failures.append(f"{name}: {e}")
                logger.warning(f"[orchestrator] VA pipeline {name} launch raised: {e}")
                continue
            if not ok:
                failures.append(f"{name}: launch returned false")
                logger.warning(f"[orchestrator] VA pipeline {name} failed to launch")
            else:
                launched += 1

        if launched == 0:
            raise _OrchestrationError(f"all va pipelines failed to launch: {'; '.join(failures)}")

        _start_board_ocr_if_enabled(session_id, wanted)

        timeout = getattr(config.va_pipeline, "completion_timeout_sec", 3600)
        need_cleanup = True
        try:
            _check_cancel(session_id)
            if not wait_for_va_completion(service, wanted, done, final_status, timeout):
                raise _OrchestrationError("va timed out")
            _check_cancel(session_id)

            if not _any_success(final_status, wanted):
                raise _OrchestrationError("all va pipelines failed")
            need_cleanup = False
        finally:
            if need_cleanup:
                _teardown_va(session_id, service)
                _stop_board_ocr_if_enabled(session_id, final_status)

        session_store.SessionStore.set_stage(session_id, "va", "done")


def _teardown_va(session_id: str, service) -> None:
    """Best-effort tear down of VA subprocesses on timeout/cancel. Cross-platform
    via service.stop_all_pipelines()."""
    try:
        service.stop_all_pipelines(timeout=5.0)
    except Exception as e:
        logger.error(f"[orchestrator] failed to tear down VA for {session_id}: {e}", exc_info=True)


def _board_ocr_enabled() -> bool:
    features = getattr(config, "features", None)
    bo = getattr(features, "board_ocr", None) if features else None
    return bool(getattr(bo, "enabled", False)) if bo else False


def _start_board_ocr_if_enabled(session_id: str, wanted: dict) -> None:
    content_source = wanted.get("content")
    if not content_source or not _board_ocr_enabled():
        return
    try:
        from components.board_ocr.board_ocr_pipeline import start_board_ocr
        start_board_ocr(session_id, content_source)
        logger.info(f"[orchestrator] board OCR started for session {session_id}")
    except Exception as e:
        logger.error(f"[orchestrator] failed to start board OCR: {e}", exc_info=True)


def _stop_board_ocr_if_enabled(session_id: str, final_status: dict) -> None:
    if not _board_ocr_enabled():
        return
    # Leave board OCR running if the content pipeline failed (it reads the source
    # directly); otherwise stop it. Mirrors the UI behavior.
    if final_status.get("content") == "failed":
        logger.info("[orchestrator] content pipeline failed; leaving board OCR running")
        return
    try:
        from components.board_ocr.board_ocr_pipeline import stop_board_ocr
        stop_board_ocr(session_id)
        logger.info(f"[orchestrator] board OCR stopped for session {session_id}")
    except Exception as e:
        logger.error(f"[orchestrator] failed to stop board OCR: {e}", exc_info=True)


def _any_success(final_status: dict, wanted: dict) -> bool:
    for name in wanted:
        if final_status.get(name) == "eos":
            return True
    return False


def _drain(gen) -> None:
    for _ in gen:
        pass


def _await_pending_writes(timeout: float = 30.0) -> None:
    StorageManager.wait_idle(timeout)
