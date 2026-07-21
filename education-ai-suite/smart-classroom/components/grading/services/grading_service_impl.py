"""Grading service (pure-VLM). Job framework + task lifecycle.

Only task_type "grading.run" is supported. The actual grading is delegated to
run_vlm_grading_pipeline; everything else here (job store, state machine,
pause/resume/cancel via checkpoints, task logging) is grading-method agnostic.
"""
from __future__ import annotations

import json
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path
from threading import Thread
from typing import Any

from services.job_store import JsonJobStore
from services.vlm_grading_pipeline import run_vlm_grading_pipeline


def get_health(language: str) -> dict[str, Any]:
    return {"status": "ok", "service": "grading", "language": language}


_COMPONENT_ROOT = Path(__file__).resolve().parents[1]
_JOB_STORE = JsonJobStore(_COMPONENT_ROOT / "outputs" / "jobs" / "job_store.json")

_ACTIVE_TASK_STATUSES = {"PENDING", "RUNNING", "PAUSING", "PAUSED", "CANCELLING"}
_TERMINAL_TASK_STATUSES = {"COMPLETED", "FAILED", "CANCELLED"}
_SUPPORTED_TASK_TYPES = {"grading.run"}


def _now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _task_logs_dir() -> Path:
    logs_dir = _COMPONENT_ROOT / "outputs" / "jobs" / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    return logs_dir


def _task_log_path(task_id: str, task_type: str) -> Path:
    safe_type = task_type.replace(".", "_")
    return _task_logs_dir() / f"{safe_type}_{task_id}.log"


def _append_task_log(task_id: str, task_type: str, message: str) -> None:
    with _task_log_path(task_id, task_type).open("a", encoding="utf-8") as f:
        f.write(f"[{_now_utc_iso()}] {message}\n")


def _append_task_exception(task_id: str, task_type: str, exc: Exception) -> None:
    _append_task_log(task_id, task_type, f"ERROR: {exc}")
    for line in traceback.format_exc().strip().splitlines():
        _append_task_log(task_id, task_type, line)


# ---------------------------------------------------------------------------
# Rubric / prompt upload
# ---------------------------------------------------------------------------
def _rubrics_upload_dir() -> Path:
    upload_dir = _COMPONENT_ROOT / "rubrics"
    upload_dir.mkdir(parents=True, exist_ok=True)
    return upload_dir


def save_uploaded_rubric(filename: str, content: bytes) -> dict[str, Any]:
    """Persist an uploaded grading prompt / rubric file into rubrics/.

    Accepts .txt (static grading prompt) or .json (rubric); .json is validated.
    """
    if not content:
        raise ValueError("uploaded file is empty")
    name = Path(str(filename or "")).name.strip()
    if not name:
        raise ValueError("filename is required")
    suffix = name.lower().rsplit(".", 1)[-1] if "." in name else ""
    if suffix not in {"txt", "json"}:
        raise ValueError("rubric file must be a .txt or .json file")
    if suffix == "json":
        try:
            json.loads(content.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError(f"uploaded .json is not valid JSON: {exc}") from exc

    dest = _rubrics_upload_dir() / name
    dest.write_bytes(content)
    return {
        "status": "ok",
        "filename": name,
        "rubric_path": str(dest),
        "size_bytes": len(content),
    }


# ---------------------------------------------------------------------------
# Task control (pause / resume / cancel) via checkpoints
# ---------------------------------------------------------------------------
def _handle_task_control_checkpoint(task_id: str, checkpoint_step: str) -> bool:
    task = _JOB_STORE.get_job(task_id)
    task_type = str(task.get("task_type", "grading.run"))
    action = task.get("control_action")

    if action == "cancel":
        _append_task_log(task_id, task_type, f"checkpoint={checkpoint_step} action=cancel applied")
        _JOB_STORE.set_control_action(task_id, None)
        _JOB_STORE.update_job(
            task_id, status="CANCELLED", current_step="cancelled",
            checkpoint_step=checkpoint_step, progress=100, error_message=None, result=None,
        )
        return True

    if action == "pause":
        _append_task_log(task_id, task_type, f"checkpoint={checkpoint_step} action=pause applied")
        _JOB_STORE.set_control_action(task_id, None)
        _JOB_STORE.update_job(
            task_id, status="PAUSED", current_step=f"paused:{checkpoint_step}",
            checkpoint_step=checkpoint_step,
        )
        while True:
            latest = _JOB_STORE.get_job(task_id)
            latest_status = latest.get("status")
            latest_action = latest.get("control_action")
            if latest_action == "cancel":
                _append_task_log(task_id, task_type, f"paused checkpoint={checkpoint_step} action=cancel applied")
                _JOB_STORE.set_control_action(task_id, None)
                _JOB_STORE.update_job(
                    task_id, status="CANCELLED", current_step="cancelled",
                    checkpoint_step=checkpoint_step, progress=100, error_message=None, result=None,
                )
                return True
            if latest_status == "RUNNING":
                _append_task_log(task_id, task_type, f"resumed from checkpoint={checkpoint_step}")
                _JOB_STORE.update_job(task_id, current_step=f"resumed:{checkpoint_step}")
                return False
            if latest_status in _TERMINAL_TASK_STATUSES:
                return True
            time.sleep(0.2)

    return False


# ---------------------------------------------------------------------------
# Task worker + creation
# ---------------------------------------------------------------------------
def _run_grading_task(task_id: str, request_payload: dict[str, Any]) -> None:
    _append_task_log(task_id, "grading.run", "task started")
    try:
        def _progress(step: str, progress: int) -> None:
            _append_task_log(task_id, "grading.run", f"progress step={step} value={progress}")
            _JOB_STORE.update_job(task_id, status="RUNNING", current_step=step, progress=progress)

        pipeline_result = run_vlm_grading_pipeline(
            task_id=task_id,
            request_payload=request_payload,
            update_progress=_progress,
            check_checkpoint=lambda cp: _handle_task_control_checkpoint(task_id, cp),
            log_event=lambda message: _append_task_log(task_id, "grading.run", message),
        )

        if pipeline_result.get("stopped"):
            _append_task_log(task_id, "grading.run", "task stopped at checkpoint")
            return

        _JOB_STORE.update_job(
            task_id, status="COMPLETED", current_step="completed", progress=100,
            result={
                "result_path": str(pipeline_result["result_path"]),
                "summary": pipeline_result["summary"],
                "log_path": str(_task_log_path(task_id, "grading.run")),
            },
            error_message=None,
        )
        _append_task_log(task_id, "grading.run", "task completed")
    except Exception as exc:
        _append_task_exception(task_id, "grading.run", exc)
        _JOB_STORE.update_job(
            task_id, status="FAILED", current_step="failed", progress=100, error_message=str(exc),
        )


def _build_submission_key(paper_path: str, student_id: str | None) -> str:
    if student_id and str(student_id).strip():
        return str(student_id).strip()
    return Path(str(paper_path)).resolve().parent.name


def _config_force_regrade() -> bool:
    """Read grading.force_regrade from the component config.yaml (default False)."""
    try:
        import yaml

        raw = yaml.safe_load((_COMPONENT_ROOT / "config.yaml").read_text(encoding="utf-8")) or {}
        return bool(((raw.get("grading") or {}).get("force_regrade", False)))
    except Exception:
        return False


def _should_reuse_existing_task(existing: dict[str, Any]) -> bool:
    if _config_force_regrade():
        return False
    return str(existing.get("status", "")) in _ACTIVE_TASK_STATUSES


def create_grading_task(
    paper_path: str,
    rubric_path: str | None = None,
    student_id: str | None = None,
    exam_id: str | None = None,
    options: dict[str, Any] | None = None,
) -> dict[str, Any]:
    submission_key = _build_submission_key(paper_path, student_id)
    options_obj = options if isinstance(options, dict) else {}

    existing = _JOB_STORE.find_latest_job(
        task_type="grading.run", request_field="submission_key", request_value=submission_key,
    )
    if existing is not None and _should_reuse_existing_task(existing):
        return existing

    payload = {
        "paper_path": paper_path,
        "rubric_path": rubric_path,
        "student_id": student_id,
        "exam_id": exam_id,
        "submission_key": submission_key,
        "options": options_obj,
    }
    task = _JOB_STORE.create_job(task_type="grading.run", request_payload=payload)
    log_path = _task_log_path(task["job_id"], "grading.run")
    log_path.write_text("", encoding="utf-8")
    task = _JOB_STORE.update_job(task["job_id"], log_path=str(log_path))
    _append_task_log(task["job_id"], "grading.run", "task created")

    worker = Thread(target=_run_grading_task, args=(task["job_id"], payload), daemon=True)
    worker.start()
    return task


# ---------------------------------------------------------------------------
# Generic dispatch used by the API routes
# ---------------------------------------------------------------------------
def create_task(task_type: str, payload: dict[str, Any]) -> dict[str, Any]:
    if task_type not in _SUPPORTED_TASK_TYPES:
        raise ValueError(f"unsupported task_type: {task_type}")
    if not isinstance(payload, dict):
        raise ValueError("payload must be an object")
    if not payload.get("paper_path"):
        raise ValueError("grading.run payload requires paper_path")
    # Minimal API: only paper_path / rubric_path / exam_id. rubric_path is
    # optional (pipeline falls back to config default_prompt_path); student_id
    # is derived from the paper's folder name; dpi/answer_key/force_regrade all
    # live in config.yaml, so no options come from the API.
    paper_path = str(payload.get("paper_path", ""))
    return create_grading_task(
        paper_path=paper_path,
        rubric_path=payload.get("rubric_path"),
        student_id=_build_submission_key(paper_path, None),
        exam_id=payload.get("exam_id"),
        options={},
    )


def get_task_status(task_id: str) -> dict[str, Any]:
    return _JOB_STORE.get_job(task_id)


def get_task_result(task_id: str) -> dict[str, Any]:
    task = get_task_status(task_id)
    status = task.get("status")
    if status != "COMPLETED":
        raise RuntimeError(f"task not completed, current status: {status}")
    result = task.get("result")
    if not isinstance(result, dict):
        raise RuntimeError("task completed but result is missing")
    return {"task_id": task_id, "task_type": str(task.get("task_type", "")), "status": status, "result": result}


def request_task_pause(task_id: str) -> dict[str, Any]:
    task = get_task_status(task_id)
    status = task.get("status")
    if status in {"RUNNING", "PENDING"}:
        _JOB_STORE.set_control_action(task_id, "pause")
        return _JOB_STORE.update_job(task_id, status="PAUSING", current_step="pause_requested")
    if status in {"PAUSING", "PAUSED"}:
        return _JOB_STORE.get_job(task_id)
    raise RuntimeError(f"pause not allowed in current status: {status}")


def request_task_resume(task_id: str) -> dict[str, Any]:
    task = get_task_status(task_id)
    status = task.get("status")
    if status == "PAUSED":
        _JOB_STORE.set_control_action(task_id, None)
        return _JOB_STORE.update_job(task_id, status="RUNNING", current_step="resume_requested")
    if status == "RUNNING":
        return _JOB_STORE.get_job(task_id)
    if status == "PAUSING":
        raise RuntimeError("task is pausing, retry resume after it reaches PAUSED")
    raise RuntimeError(f"resume not allowed in current status: {status}")


def request_task_cancel(task_id: str) -> dict[str, Any]:
    task = get_task_status(task_id)
    status = task.get("status")
    if status in {"RUNNING", "PAUSING", "PAUSED", "PENDING"}:
        _JOB_STORE.set_control_action(task_id, "cancel")
        return _JOB_STORE.update_job(task_id, status="CANCELLING", current_step="cancel_requested")
    if status in _TERMINAL_TASK_STATUSES or status == "CANCELLING":
        return _JOB_STORE.get_job(task_id)
    raise RuntimeError(f"cancel not allowed in current status: {status}")
