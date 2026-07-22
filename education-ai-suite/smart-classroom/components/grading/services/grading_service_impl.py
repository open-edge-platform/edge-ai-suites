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


def _dump_summary(summary: dict[str, Any]) -> str:
    """Pretty-print the summary but collapse each question record onto one line."""
    import re

    text = json.dumps(summary, ensure_ascii=False, indent=2)

    def _collapse(match: "re.Match[str]") -> str:
        body = match.group(2)
        fields = [ln.strip() for ln in body.splitlines() if ln.strip()]
        inline = "{" + " ".join(fields).rstrip(",") + "}"
        return f'{match.group(1)}: {inline}'

    # Match `"<digits>": { ... }` blocks (the per-question records) and inline them.
    pattern = re.compile(r'("\d+")\s*:\s*\{\n((?:[ \t]+"(?:catalog|type|score|max_score)".*\n?)+?)[ \t]*\}')
    return pattern.sub(_collapse, text)


def _update_summary(task_id: str, student_id: str, child_job_id: str) -> None:
    """Fold a just-graded student's result into outputs/<exam_id>/summary.json.

    Reads the child job's grading_result.json (result_path), then read-modify-writes
    the exam-level summary.json living one directory above the student's folder.
    Best-effort: any failure is logged and swallowed so it never breaks the loop.
    """
    try:
        child = _JOB_STORE.get_job(child_job_id) or {}
        result_path = (child.get("result") or {}).get("result_path")
        if not result_path:
            return
        result_path = Path(str(result_path))
        data = json.loads(result_path.read_text(encoding="utf-8"))

        exam_dir = result_path.parent.parent
        summary_path = exam_dir / "summary.json"

        source_summary = data.get("summary") or {}
        source_input = data.get("input") or {}
        paper_meta = data.get("paper_meta") or {}
        student_meta = data.get("student_meta") or {}

        if summary_path.exists():
            summary = json.loads(summary_path.read_text(encoding="utf-8"))
        else:
            summary = {}

        metadata = summary.setdefault("metadata", {
            "exam_id": source_input.get("exam_id"),
            "prompt_path": source_input.get("prompt_path"),
        })
        # Fill paper-level fields from the header once (first non-null wins).
        for key in ("paper_title", "subject"):
            if not metadata.get(key) and paper_meta.get(key):
                metadata[key] = paper_meta.get(key)
        students = summary.setdefault("students", {})

        # Students are keyed by a sequential index (1, 2, 3, ...). Reuse the
        # existing slot for this student_id so a re-grade updates in place.
        slot = next(
            (idx for idx, rec in students.items() if rec.get("student_id") == student_id),
            None,
        )
        if slot is None:
            slot = str(len(students) + 1)

        questions = {}
        for qid, q in (data.get("questions") or {}).items():
            questions[qid] = {
                "catalog": q.get("catalog"),
                "type": q.get("type"),
                "score": q.get("vlm_score"),
                "max_score": q.get("max_score"),
            }

        students[slot] = {
            "student_id": student_id,
            "student_name": student_meta.get("student_name"),
            "class_name": student_meta.get("class_name"),
            "exam_number": student_meta.get("exam_number"),
            "paper_path": source_input.get("paper_path"),
            "total_score": source_summary.get("total_score"),
            "total_max": source_summary.get("total_max"),
            "objective_score": source_summary.get("objective_score"),
            "objective_max": source_summary.get("objective_max"),
            "subjective_score": source_summary.get("subjective_score"),
            "subjective_max": source_summary.get("subjective_max"),
            "questions": questions,
        }
        summary["updated_at"] = _now_utc_iso()
        summary["student_count"] = len(students)

        exam_dir.mkdir(parents=True, exist_ok=True)
        summary_path.write_text(_dump_summary(summary), encoding="utf-8")
        _append_task_log(
            task_id, "grading.run",
            f"summary updated student={student_id} file={summary_path}",
        )
    except Exception as exc:
        _append_task_log(task_id, "grading.run", f"summary update failed student={student_id} error={exc}")


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


def submit_grading_sync(
    paper_path: str,
    student_id: str | None = None,
    exam_id: str | None = None,
    rubric_path: str | None = None,
    options: dict[str, Any] | None = None,
    parent_task_id: str | None = None,
) -> dict[str, Any]:
    """Create a job and run it synchronously in the calling thread.

    Same persistence as create_grading_task but runs _run_grading_task inline
    instead of spawning a thread, so the caller (a directory task's loop) blocks
    until the job reaches a terminal state. No reuse/force_regrade check — dedup
    is the caller's responsibility. parent_task_id links this per-item job back
    to the directory task that spawned it.
    """
    submission_key = _build_submission_key(paper_path, student_id)
    payload = {
        "paper_path": paper_path,
        "rubric_path": rubric_path,
        "student_id": student_id,
        "exam_id": exam_id,
        "submission_key": submission_key,
        "parent_task_id": parent_task_id,
        "options": options if isinstance(options, dict) else {},
    }
    task = _JOB_STORE.create_job(task_type="grading.run", request_payload=payload)
    log_path = _task_log_path(task["job_id"], "grading.run")
    log_path.write_text("", encoding="utf-8")
    task = _JOB_STORE.update_job(task["job_id"], log_path=str(log_path))
    _append_task_log(task["job_id"], "grading.run", "task created (batch item)")
    _run_grading_task(task["job_id"], payload)
    return task


# ---------------------------------------------------------------------------
# Directory-mode grading task: one task maintains a table of work items under a
# papers directory, grades them one at a time, refreshes the table to pick up new
# items, and completes once all are done and the directory has been idle.
# ---------------------------------------------------------------------------
def create_directory_grading_task(
    papers_dir: str,
    rubric_path: str | None = None,
    exam_id: str | None = None,
) -> dict[str, Any]:
    from services.dir_scan import load_dir_defaults

    resolved = Path(papers_dir).resolve()
    if not resolved.is_dir():
        raise ValueError(f"papers_dir is not a directory: {resolved}")

    defaults = load_dir_defaults(_COMPONENT_ROOT)
    payload = {
        "paper_path": str(resolved),
        "papers_dir": str(resolved),
        "rubric_path": rubric_path,
        "exam_id": exam_id or resolved.name,
        "mode": "directory",
        "items": [],
        "poll_interval": defaults.poll_interval,
        "stable_checks": defaults.stable_checks,
        "idle_timeout": defaults.idle_timeout,
        "last_new_item_at_iso": None,
    }
    task = _JOB_STORE.create_job(task_type="grading.run", request_payload=payload)
    log_path = _task_log_path(task["job_id"], "grading.run")
    log_path.write_text("", encoding="utf-8")
    task = _JOB_STORE.update_job(task["job_id"], log_path=str(log_path))
    _append_task_log(task["job_id"], "grading.run", f"directory task created papers_dir={resolved}")

    worker = Thread(target=_run_directory_grading_task, args=(task["job_id"],), daemon=True)
    worker.start()
    return task


def _get_items(task_id: str) -> list[dict[str, Any]]:
    request = _JOB_STORE.get_job(task_id).get("request") or {}
    items = request.get("items")
    return list(items) if isinstance(items, list) else []


def _save_items(task_id: str, items: list[dict[str, Any]], **extra: Any) -> None:
    """Read-modify-write the request dict (update_job is a shallow merge)."""
    request = dict(_JOB_STORE.get_job(task_id).get("request") or {})
    request["items"] = items
    request.update(extra)
    _JOB_STORE.update_job(task_id, request=request)


def _refresh_items(task_id: str, papers_dir: Path, items: list[dict[str, Any]]) -> bool:
    """Scan papers_dir and add newly appeared items to the table. Items already
    COMPLETED in the store are marked completed (skip re-grading). Returns True if
    any new item was added."""
    from services.dir_scan import discover_items

    known = {it["key"] for it in items}
    added = False
    for found in discover_items(papers_dir):
        if found["key"] in known:
            continue
        existing = _JOB_STORE.find_latest_job(
            task_type="grading.run", request_field="submission_key", request_value=found["key"],
        )
        already_done = existing is not None and existing.get("status") == "COMPLETED"
        items.append({
            "key": found["key"],
            "path": found["path"],
            "kind": found["kind"],
            "status": "completed" if already_done else "pending",
        })
        known.add(found["key"])
        added = True
        _append_task_log(
            task_id, "grading.run",
            f"item discovered key={found['key']} kind={found['kind']}"
            + (" (already graded, skipped)" if already_done else ""),
        )
    return added


def _run_directory_grading_task(task_id: str) -> None:
    import time as _time

    from services.dir_scan import is_pdf_ready

    _append_task_log(task_id, "grading.run", "directory task started")
    try:
        request = _JOB_STORE.get_job(task_id).get("request") or {}
        papers_dir = Path(str(request["papers_dir"]))
        rubric_path = request.get("rubric_path")
        exam_id = request.get("exam_id")
        poll_interval = float(request.get("poll_interval", 5))
        stable_checks = int(request.get("stable_checks", 2))
        idle_timeout = float(request.get("idle_timeout", 180))

        items = _get_items(task_id)
        stable: dict[Path, tuple[int, float, int]] = {}
        last_new_item_monotonic = _time.monotonic()

        _JOB_STORE.update_job(task_id, status="RUNNING", current_step="scanning")

        while True:
            # -- control: cancel / pause (reuse the checkpoint handler) --------
            if _handle_task_control_checkpoint(task_id, "directory_loop"):
                _append_task_log(task_id, "grading.run", "directory task stopped at checkpoint")
                return

            # -- refresh the table --------------------------------------------
            if _refresh_items(task_id, papers_dir, items):
                last_new_item_monotonic = _time.monotonic()
                _save_items(task_id, items, last_new_item_at_iso=_now_utc_iso())
            else:
                _save_items(task_id, items)

            # -- pick one pending item and grade it ---------------------------
            picked = None
            for it in items:
                if it["status"] != "pending":
                    continue
                if not is_pdf_ready(Path(it["path"]), stable, stable_checks):
                    continue
                picked = it
                break

            if picked is not None:
                key = picked["key"]
                _append_task_log(task_id, "grading.run", f"grading item key={key}")
                _JOB_STORE.update_job(task_id, current_step=f"grading:{key}")
                try:
                    sub = submit_grading_sync(
                        paper_path=picked["path"],
                        student_id=key,
                        exam_id=exam_id,
                        rubric_path=rubric_path,
                        parent_task_id=task_id,
                    )
                    picked["task_id"] = sub["job_id"]
                    final = _JOB_STORE.get_job(sub["job_id"]).get("status")
                    picked["status"] = "completed" if final == "COMPLETED" else "failed"
                    if picked["status"] == "completed":
                        _update_summary(task_id, key, sub["job_id"])
                    _append_task_log(task_id, "grading.run",
                                     f"item done key={key} status={picked['status']} task={sub['job_id']}")
                except Exception as exc:
                    picked["status"] = "failed"
                    _append_task_log(task_id, "grading.run", f"item failed key={key} error={exc}")
                _save_items(task_id, items)
                continue  # immediately look for the next pending item

            # -- nothing to do this round: check idle-completion --------------
            pending = any(it["status"] == "pending" for it in items)
            idle = _time.monotonic() - last_new_item_monotonic
            if not pending and idle > idle_timeout:
                completed = sum(1 for it in items if it["status"] == "completed")
                failed = sum(1 for it in items if it["status"] == "failed")
                _JOB_STORE.update_job(
                    task_id, status="COMPLETED", current_step="completed", progress=100,
                    result={
                        "total": len(items),
                        "completed": completed,
                        "failed": failed,
                        "log_path": str(_task_log_path(task_id, "grading.run")),
                    },
                    error_message=None,
                )
                _append_task_log(
                    task_id, "grading.run",
                    f"directory task completed total={len(items)} completed={completed} failed={failed}",
                )
                return

            _JOB_STORE.update_job(task_id, current_step="idle" if not pending else "waiting")
            _time.sleep(poll_interval)
    except Exception as exc:
        _append_task_exception(task_id, "grading.run", exc)
        _JOB_STORE.update_job(
            task_id, status="FAILED", current_step="failed", error_message=str(exc),
        )


def pause_running_directory_tasks() -> None:
    """Shutdown hook: mark RUNNING directory tasks PAUSED so they can be resumed
    after restart. Their daemon threads die with the process; the persisted items
    table preserves progress."""
    for job in _JOB_STORE.list_jobs(task_type="grading.run"):
        request = job.get("request") or {}
        if request.get("mode") == "directory" and job.get("status") in {"RUNNING", "PENDING"}:
            _JOB_STORE.update_job(job["job_id"], status="PAUSED", current_step="paused")


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
    # paper_path may be a single PDF (grade one paper) or a directory (grade every
    # student under it, refreshing as new ones appear until idle). rubric_path is
    # optional (pipeline falls back to config default_prompt_path); dpi/answer_key/
    # force_regrade all live in config.yaml, so no options come from the API.
    paper_path = str(payload.get("paper_path", ""))
    if Path(paper_path).is_dir():
        return create_directory_grading_task(
            papers_dir=paper_path,
            rubric_path=payload.get("rubric_path"),
            exam_id=payload.get("exam_id"),
        )
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
    request = task.get("request") or {}
    is_directory = request.get("mode") == "directory"
    if status == "PAUSED":
        _JOB_STORE.set_control_action(task_id, None)
        resumed = _JOB_STORE.update_job(task_id, status="RUNNING", current_step="resume_requested")
        if is_directory:
            # The old worker thread is gone (e.g. after restart); spawn a fresh
            # one. Completed items in the persisted table are skipped.
            worker = Thread(target=_run_directory_grading_task, args=(task_id,), daemon=True)
            worker.start()
        return resumed
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
