import logging
import os
import threading

from pipeline import Pipeline
from dto.transcription_dto import TranscriptionRequest
from dto.audiosource import AudioSource
from utils.config_loader import config
from utils.artifacts.path import get_artifact_path
from utils.artifacts.pending_writes import PendingWrites
from utils.session_manager import generate_session_id
from utils import session_state
from components.va.va_pipeline_service import VideoAnalyticsPipelineService, PipelineOptions

logger = logging.getLogger(__name__)


def start_process(request: dict) -> str:
    session_id = generate_session_id()
    stages = request.get("stages", [])
    state = session_state.SessionStateManager.create(session_id, request, stages)
    thread = threading.Thread(target=_run, args=(session_id, request, stages), daemon=True)
    thread.start()
    return session_id


def _run(session_id: str, request: dict, stages: list) -> None:
    session_state.SessionStateManager.update(session_id, state="running")
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
        if va_error:
            raise _OrchestrationError(va_error[0])
        session_state.SessionStateManager.mark_completed(session_id)
    except _OrchestrationError as e:
        session_state.SessionStateManager.mark_failed(session_id, str(e))
    except Exception as e:
        logger.exception(f"[orchestrator] session {session_id} unexpected failure")
        session_state.SessionStateManager.mark_failed(session_id, f"unexpected error: {e}")


def _run_va_safe(session_id: str, request: dict, stages: list, errors: list) -> None:
    try:
        _run_va_if_needed(session_id, request, stages)
    except _OrchestrationError as e:
        errors.append(str(e))
    except Exception as e:
        logger.exception(f"[orchestrator] session {session_id} VA thread failure")
        errors.append(f"unexpected va error: {e}")


def _run_audio_chain(session_id: str, request: dict, stages: list,
                     va_thread=None, va_error=None) -> None:
    pipeline = Pipeline(session_id)

    if "transcribe" in stages:
        session_state.SessionStateManager.set_stage(session_id, "transcribe", "running")
        audio_path = request.get("audio_path")
        if not audio_path:
            raise _OrchestrationError("stage transcribe requires audio_path")
        tr = TranscriptionRequest(audio_filename=audio_path, source_type=AudioSource.AUDIO_FILE)
        _drain(pipeline.run_transcription(tr))
        session_state.SessionStateManager.set_stage(session_id, "transcribe", "done")
        _await_pending_writes()

    if "summarize" in stages:
        session_state.SessionStateManager.set_stage(session_id, "summarize", "running")
        _drain(pipeline.run_summarizer())
        session_state.SessionStateManager.set_stage(session_id, "summarize", "done")
        _await_pending_writes()

    if "mindmap" in stages:
        session_state.SessionStateManager.set_stage(session_id, "mindmap", "running")
        pipeline.run_mindmap()
        session_state.SessionStateManager.set_stage(session_id, "mindmap", "done")

    if "segmentation" in stages:
        _join_va(va_thread, va_error)
        session_state.SessionStateManager.set_stage(session_id, "segmentation", "running")
        pipeline.run_content_segmentation()
        session_state.SessionStateManager.set_stage(session_id, "segmentation", "done")

    if "report" in stages:
        session_state.SessionStateManager.set_stage(session_id, "report", "running")
        _drain(pipeline.run_report_generator())
        session_state.SessionStateManager.set_stage(session_id, "report", "done")


def _join_va(va_thread, va_error) -> None:
    if va_thread is not None:
        va_thread.join()
        if va_error:
            raise _OrchestrationError(va_error[0])


def _run_va_if_needed(session_id: str, request: dict, stages: list) -> None:
    if "va" not in stages:
        return
    video_sources = request.get("video_sources") or {}
    wanted = {k: v for k, v in video_sources.items() if v}
    if not wanted:
        raise _OrchestrationError("stage va requires video_sources")

    session_state.SessionStateManager.set_stage(session_id, "va", "running")

    va_out_dir = get_artifact_path(session_id, "va")
    os.makedirs(va_out_dir, exist_ok=True)

    service = VideoAnalyticsPipelineService()
    service.x_session_id = session_id

    done = threading.Event()
    final_status = {}

    def _on_done(sid):
        final_status.update(service.pipeline_final_status)
        done.set()

    service.on_all_pipelines_done = _on_done

    options = PipelineOptions(
        output_dir=get_artifact_path(session_id, "va"),
        output_rtsp=config.va_pipeline.output_rtsp_url,
        threshold=config.models.va.threshold,
        record=False,
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

    if not done.wait(timeout=3600):
        raise _OrchestrationError("va timed out")

    if not _any_success(final_status, wanted):
        raise _OrchestrationError("all va pipelines failed")

    session_state.SessionStateManager.set_stage(session_id, "va", "done")


def _any_success(final_status: dict, wanted: dict) -> bool:
    for name in wanted:
        if final_status.get(name) == "eos":
            return True
    return False


def _drain(gen) -> None:
    for _ in gen:
        pass


def _await_pending_writes(timeout: float = 30.0) -> None:
    waited = 0.0
    while not PendingWrites.is_idle() and waited < timeout:
        import time
        time.sleep(0.1)
        waited += 0.1


class _OrchestrationError(Exception):
    pass
