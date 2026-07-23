"""Grading service (pure-VLM). Job framework + task lifecycle.

Only task_type "grading.run" is supported. The actual grading is delegated to
run_vlm_grading_pipeline; everything else here (job store, state machine,
pause/resume/cancel via checkpoints, task logging) is grading-method agnostic.
"""
from __future__ import annotations

import json
import time
import traceback
import yaml
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


def get_rubric_content(filename: str) -> dict[str, Any]:
    name = Path(str(filename or "")).name.strip()
    if not name:
        raise ValueError("filename is required")
    path = _rubrics_upload_dir() / name
    if not path.exists() or not path.is_file():
        raise KeyError(f"rubric not found: {name}")
    return {"filename": name, "content": path.read_text(encoding="utf-8")}


def update_rubric_content(filename: str, content: str) -> dict[str, Any]:
    name = Path(str(filename or "")).name.strip()
    if not name:
        raise ValueError("filename is required")
    path = _rubrics_upload_dir() / name
    if not path.exists() or not path.is_file():
        raise KeyError(f"rubric not found: {name}")
    path.write_text(content, encoding="utf-8")
    return {"filename": name, "size_bytes": len(content.encode("utf-8"))}


def list_rubrics() -> dict[str, Any]:
    """List every .txt/.json rubric under the rubrics/ directory, newest first."""
    rubrics_dir = _rubrics_upload_dir()
    rubrics: list[dict[str, Any]] = []
    for path in rubrics_dir.iterdir():
        if not path.is_file() or path.suffix.lower() not in {".txt", ".json"}:
            continue
        stat = path.stat()
        rubrics.append({
            "filename": path.name,
            "rubric_path": str(path),
            "size_bytes": stat.st_size,
            "modified_at": datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat(),
        })
    rubrics.sort(key=lambda r: r["modified_at"], reverse=True)
    return {"total": len(rubrics), "rubrics": rubrics}


def _windows_drives() -> list[dict[str, Any]]:
    """Enumerate available Windows drive roots (C:\\, D:\\, ...) as directory entries."""
    import string

    drives: list[dict[str, Any]] = []
    for letter in string.ascii_uppercase:
        root = Path(f"{letter}:\\")
        if root.exists():
            drives.append({"name": f"{letter}:\\", "path": str(root), "is_dir": True})
    return drives


def list_directory(path: str | None = None) -> dict[str, Any]:
    """List sub-directories and PDF files under a server-side path, for the UI
    directory picker. path=None returns the roots (Windows drive letters, or "/"
    on POSIX). Only directories and *.pdf files are returned; file contents are
    never read. Selecting one of the returned directory paths yields a real,
    server-visible absolute path usable as a grading task's paper_path."""
    import os

    if not path:
        if os.name == "nt":
            return {"path": "", "parent": None, "entries": _windows_drives()}
        root = Path("/")
        return {"path": str(root), "parent": None, "entries": _scan_dir(root)}

    target = Path(path)
    if not target.exists():
        raise ValueError(f"path does not exist: {path}")
    if not target.is_dir():
        raise ValueError(f"path is not a directory: {path}")

    parent = str(target.parent) if target.parent != target else None
    return {"path": str(target), "parent": parent, "entries": _scan_dir(target)}


def _scan_dir(target: Path) -> list[dict[str, Any]]:
    """Return sub-directories and *.pdf files under target, directories first,
    each sorted by name. Unreadable entries are skipped silently."""
    dirs: list[dict[str, Any]] = []
    files: list[dict[str, Any]] = []
    try:
        for entry in target.iterdir():
            try:
                if entry.is_dir():
                    dirs.append({"name": entry.name, "path": str(entry), "is_dir": True})
                elif entry.is_file() and entry.suffix.lower() == ".pdf":
                    files.append({"name": entry.name, "path": str(entry), "is_dir": False})
            except (OSError, PermissionError):
                continue
    except (OSError, PermissionError) as exc:
        raise ValueError(f"cannot read directory: {exc}") from exc
    dirs.sort(key=lambda e: e["name"].lower())
    files.sort(key=lambda e: e["name"].lower())
    return dirs + files


# ---------------------------------------------------------------------------
# Task control (pause / resume / cancel) via checkpoints
# ---------------------------------------------------------------------------
def _handle_task_control_checkpoint(task_id: str, checkpoint_step: str) -> bool:
    """Check for a pending pause/cancel at a checkpoint. Returns True if the
    worker must STOP here (pause or cancel), False to keep running.

    Pause is exit-based, not blocking: on pause the worker records PAUSED and
    returns True so the current thread unwinds and dies. There is never a live
    worker while a task is PAUSED. Resume spawns a fresh, single worker; any
    in-flight paper is re-graded whole (matches the crash re-grade policy)."""
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
        _append_task_log(task_id, task_type, f"checkpoint={checkpoint_step} action=pause applied (worker exiting)")
        _JOB_STORE.set_control_action(task_id, None)
        _JOB_STORE.update_job(
            task_id, status="PAUSED", current_step=f"paused:{checkpoint_step}",
            checkpoint_step=checkpoint_step,
        )
        return True

    return False


def _grade_one_paper(
    task_id: str,
    paper_path: str,
    student_id: str | None,
    rubric_path: str | None,
    progress_span: tuple[int, int] | None = None,
) -> dict[str, Any]:
    """Grade a single paper by calling the VLM pipeline inline (no sub-job).

    Runs in the caller's thread and reports progress / checkpoints against
    `task_id` — the ONE task that owns this work, whether it grades a lone paper
    or is a directory task iterating over students. Returns the pipeline result
    ({stopped: bool, result_path, summary}); the caller decides how to record it.
    progress_span maps the pipeline's internal 0-100 onto a slice of the owning
    task's progress bar (e.g. per-student within a directory run)."""
    payload = {
        "paper_path": paper_path,
        "rubric_path": rubric_path,
        "student_id": student_id,
        "options": {},
    }

    def _progress(step: str, progress: int) -> None:
        if progress_span is not None:
            lo, hi = progress_span
            progress = lo + int((hi - lo) * progress / 100)
        _append_task_log(task_id, "grading.run", f"progress step={step} value={progress}")
        _JOB_STORE.update_job(task_id, status="RUNNING", current_step=step, progress=progress)

    return run_vlm_grading_pipeline(
        task_id=task_id,
        request_payload=payload,
        update_progress=_progress,
        check_checkpoint=lambda cp: _handle_task_control_checkpoint(task_id, cp),
        log_event=lambda message: _append_task_log(task_id, "grading.run", message),
    )


def _reset_ocr_for_new_worker() -> None:
    """Rebuild the process-global OCR engine on this (new) worker thread. Safe to
    call even if OCR was never loaded. See ocr_service.reset_ocr for why."""
    try:
        from providers.ocr_service import reset_ocr
        reset_ocr()
    except Exception:
        pass


def _run_grading_task(task_id: str, request_payload: dict[str, Any]) -> None:
    """Worker for a lone single-paper task (paper_path is one PDF)."""
    _append_task_log(task_id, "grading.run", "task started")
    _reset_ocr_for_new_worker()
    try:
        pipeline_result = _grade_one_paper(
            task_id=task_id,
            paper_path=str(request_payload["paper_path"]),
            student_id=request_payload.get("student_id"),
            rubric_path=request_payload.get("rubric_path"),
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


def _update_summary(task_id: str, student_id: str, result_path: str) -> None:
    """Fold a just-graded student's result into outputs/<task_id>/summary.json.

    Reads the student's grading_result.json (result_path, produced inline by the
    pipeline), then read-modify-writes the task-level summary.json living one
    directory above the student's folder. Best-effort: any failure is logged and
    swallowed so it never breaks the loop.
    """
    try:
        if not result_path:
            return
        result_path = Path(str(result_path))
        data = json.loads(result_path.read_text(encoding="utf-8"))

        task_dir = result_path.parent.parent
        summary_path = task_dir / "summary.json"

        source_summary = data.get("summary") or {}
        source_input = data.get("input") or {}
        paper_meta = data.get("paper_meta") or {}
        student_meta = data.get("student_meta") or {}

        if summary_path.exists():
            summary = json.loads(summary_path.read_text(encoding="utf-8"))
        else:
            summary = {}

        metadata = summary.setdefault("metadata", {
            "task_id": task_id,
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

        task_dir.mkdir(parents=True, exist_ok=True)
        summary_path.write_text(_dump_summary(summary), encoding="utf-8")
        _append_task_log(
            task_id, "grading.run",
            f"summary updated student={student_id} file={summary_path}",
        )
    except Exception as exc:
        _append_task_log(task_id, "grading.run", f"summary update failed student={student_id} error={exc}")


def _outputs_root() -> Path:
    return _COMPONENT_ROOT / "outputs"


def _validate_task_id(task_id: str) -> str:
    """Reject anything that could escape the outputs/ root (path traversal)."""
    name = str(task_id or "").strip()
    if not name or name in {".", ".."} or "/" in name or "\\" in name:
        raise ValueError(f"invalid task_id: {task_id!r}")
    return name


def _empty_summary(task_id: str, prompt_path: str | None = None) -> dict[str, Any]:
    """The empty summary shell served before any student has been graded, and
    seeded at task creation so the summary endpoint never 404s."""
    return {
        "metadata": {"task_id": task_id, "prompt_path": prompt_path},
        "students": {},
        "updated_at": _now_utc_iso(),
        "student_count": 0,
    }


def _seed_empty_summary(task_id: str, prompt_path: str | None = None) -> None:
    """Write an empty summary.json for a task if none exists yet. Best-effort."""
    try:
        task_dir = _outputs_root() / _validate_task_id(task_id)
        summary_path = task_dir / "summary.json"
        if summary_path.exists():
            return
        task_dir.mkdir(parents=True, exist_ok=True)
        summary_path.write_text(_dump_summary(_empty_summary(task_id, prompt_path)), encoding="utf-8")
    except Exception:
        pass


def get_task_summary(task_id: str) -> dict[str, Any]:
    """Return outputs/<task_id>/summary.json, or an empty shell if it does not
    exist yet. Readable at any time (does not require the task to be COMPLETED)."""
    name = _validate_task_id(task_id)
    summary_path = _outputs_root() / name / "summary.json"
    if summary_path.exists():
        return json.loads(summary_path.read_text(encoding="utf-8"))
    return _empty_summary(name)


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


def _config_debug_mode() -> bool:
    """Read grading.debug_mode from the component config.yaml (default False)."""
    try:
        import yaml

        raw = yaml.safe_load((_COMPONENT_ROOT / "config.yaml").read_text(encoding="utf-8")) or {}
        return bool((raw.get("grading") or {}).get("debug_mode", False))
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
        "submission_key": submission_key,
        "options": options_obj,
    }
    task = _JOB_STORE.create_job(task_type="grading.run", request_payload=payload)
    log_path = _task_log_path(task["job_id"], "grading.run")
    log_path.write_text("", encoding="utf-8")
    task = _JOB_STORE.update_job(task["job_id"], log_path=str(log_path))
    _append_task_log(task["job_id"], "grading.run", "task created")
    _seed_empty_summary(task["job_id"], rubric_path)

    worker = Thread(target=_run_grading_task, args=(task["job_id"], payload), daemon=True)
    worker.start()
    return task


# ---------------------------------------------------------------------------
# Directory-mode grading task: one task maintains a table of work items under a
# papers directory, grades them one at a time, refreshes the table to pick up new
# items, and completes once all are done and the directory has been idle.
# ---------------------------------------------------------------------------
def create_directory_grading_task(
    papers_dir: str,
    rubric_path: str | None = None,
) -> dict[str, Any]:
    from services.dir_scan import load_dir_defaults

    resolved = Path(papers_dir).resolve()
    if not resolved.is_dir():
        raise ValueError(f"papers_dir is not a directory: {resolved}")

    lock_path = resolved / ".grading.lock"
    if lock_path.exists():
        raise ValueError(
            f"Directory {resolved.name} is already being graded (.grading.lock exists). "
            f"Wait for the task to finish or cancel it before submitting again."
        )

    defaults = load_dir_defaults(_COMPONENT_ROOT)
    payload = {
        "paper_path": str(resolved),
        "papers_dir": str(resolved),
        "rubric_path": rubric_path,
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
    _seed_empty_summary(task["job_id"], rubric_path)
    lock_path.write_text(task["job_id"], encoding="utf-8")

    worker = Thread(target=_run_directory_grading_task, args=(task["job_id"], lock_path), daemon=True)
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
    """Scan papers_dir and add newly appeared papers to this task's item table.
    The table (persisted in the task's request) is the single source of truth for
    what has been graded, so a newly seen paper is always added as pending; items
    already in the table (incl. completed ones) are left untouched. Returns True
    if any new item was added."""
    from services.dir_scan import discover_items

    known = {it["key"] for it in items}
    added = False
    for found in discover_items(papers_dir):
        if found["key"] in known:
            continue
        items.append({
            "key": found["key"],
            "path": found["path"],
            "kind": found["kind"],
            "status": "pending",
        })
        known.add(found["key"])
        added = True
        _append_task_log(
            task_id, "grading.run",
            f"item discovered key={found['key']} kind={found['kind']}",
        )
    return added


def _run_directory_grading_task(task_id: str, lock_path: Path | None = None) -> None:
    import time as _time

    from services.dir_scan import is_pdf_ready

    _append_task_log(task_id, "grading.run", "directory task started")
    _reset_ocr_for_new_worker()
    try:
        request = _JOB_STORE.get_job(task_id).get("request") or {}
        papers_dir = Path(str(request["papers_dir"]))
        rubric_path = request.get("rubric_path")
        poll_interval = float(request.get("poll_interval", 5))
        stable_checks = int(request.get("stable_checks", 2))
        idle_timeout = float(request.get("idle_timeout", 180))

        items = _get_items(task_id)
        stable: dict[Path, tuple[int, float, int]] = {}
        last_new_item_monotonic = _time.monotonic()

        _JOB_STORE.update_job(task_id, status="RUNNING", current_step="scanning")

        while True:
            if _handle_task_control_checkpoint(task_id, "directory_loop"):
                _append_task_log(task_id, "grading.run", "directory task stopped at checkpoint")
                return

            if _refresh_items(task_id, papers_dir, items):
                last_new_item_monotonic = _time.monotonic()
                _save_items(task_id, items, last_new_item_at_iso=_now_utc_iso())
            else:
                _save_items(task_id, items)

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
                    # Grade this paper inline, in THIS worker/thread — no sub-job.
                    # Checkpoints fire against this directory task, so a pause/cancel
                    # takes effect mid-paper and the pipeline returns stopped=True.
                    result = _grade_one_paper(
                        task_id=task_id,
                        paper_path=picked["path"],
                        student_id=key,
                        rubric_path=rubric_path,
                    )
                    if result.get("stopped"):
                        # A pause/cancel interrupted this paper mid-way. Leave the
                        # item pending (whole-paper re-grade on resume); the pipeline
                        # already settled this task's own PAUSED/CANCELLED state, so
                        # the worker exits now.
                        _append_task_log(task_id, "grading.run",
                                         f"item interrupted key={key} (kept pending), worker exiting")
                        _save_items(task_id, items)
                        return
                    picked["status"] = "completed"
                    _update_summary(task_id, key, result["result_path"])
                    _append_task_log(task_id, "grading.run",
                                     f"item done key={key} status=completed")
                except Exception as exc:
                    picked["status"] = "failed"
                    _append_task_log(task_id, "grading.run", f"item failed key={key} error={exc}")
                    if _config_debug_mode():
                        for _line in traceback.format_exc().strip().splitlines():
                            _append_task_log(task_id, "grading.run", f"  {_line}")
                _save_items(task_id, items)
                continue  # immediately look for the next pending item

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
    finally:
        if lock_path is not None:
            try:
                lock_path.unlink(missing_ok=True)
            except Exception:
                pass


def pause_running_directory_tasks() -> None:
    """Shutdown hook: mark RUNNING directory tasks PAUSED so they can be resumed
    after restart. Their daemon threads die with the process; the persisted items
    table preserves progress."""
    for job in _JOB_STORE.list_jobs(task_type="grading.run"):
        request = job.get("request") or {}
        if request.get("mode") == "directory" and job.get("status") in {"RUNNING", "PENDING"}:
            _JOB_STORE.update_job(job["job_id"], status="PAUSED", current_step="paused")


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
        )
    return create_grading_task(
        paper_path=paper_path,
        rubric_path=payload.get("rubric_path"),
        student_id=_build_submission_key(paper_path, None),
        options={},
    )


def get_task_status(task_id: str) -> dict[str, Any]:
    return _JOB_STORE.get_job(task_id)


def _dir_info(job: dict[str, Any]) -> dict[str, Any] | None:
    """Summarize a directory-mode task from its persisted item table, for the UI
    task panel. Returns None for single-paper tasks (no item table). Counts are
    derived from request.items; `current` is the item being graded now (parsed
    from current_step "grading:<key>"), or None when not actively grading."""
    request = job.get("request") or {}
    if request.get("mode") != "directory":
        return None

    items = request.get("items")
    items = items if isinstance(items, list) else []
    total = len(items)
    completed = sum(1 for it in items if it.get("status") == "completed")
    failed = sum(1 for it in items if it.get("status") == "failed")
    pending = sum(1 for it in items if it.get("status") == "pending")

    current = None
    step = str(job.get("current_step") or "")
    if step.startswith("grading:"):
        current = step.split(":", 1)[1] or None

    papers_dir = request.get("papers_dir")
    rubric_path = request.get("rubric_path")
    return {
        "papers_dir": papers_dir,
        "dir_name": Path(papers_dir).name if papers_dir else None,
        "rubric_path": rubric_path,
        "rubric_name": Path(rubric_path).name if rubric_path else None,
        "total": total,
        "completed": completed,
        "failed": failed,
        "pending": pending,
        "current": current,
        "last_new_item_at": request.get("last_new_item_at_iso"),
    }


def read_task_log(task_id: str, tail: int = 50) -> dict[str, Any]:
    """Return the last `tail` lines of a task's log file. Missing log -> empty."""
    job = _JOB_STORE.get_job(task_id)  # raises KeyError if unknown
    log_path = job.get("log_path")
    if not log_path:
        return {"task_id": task_id, "log_path": None, "lines": []}

    path = Path(log_path)
    if not path.exists():
        return {"task_id": task_id, "log_path": str(path), "lines": []}

    tail = max(1, min(int(tail), 5000))
    with path.open("r", encoding="utf-8", errors="replace") as f:
        lines = f.read().splitlines()
    return {"task_id": task_id, "log_path": str(path), "lines": lines[-tail:]}


def update_grading_config(
    dpi: int | None = None,
    vlm_temperature: float | None = None,
    poll_interval: int | None = None,
    stable_checks: int | None = None,
    idle_timeout: int | None = None,
) -> dict[str, Any]:
    import re
    from services.vlm_grading_pipeline import _component_root
    path = _component_root() / "config.yaml"
    text = path.read_text(encoding="utf-8")

    def replace_scalar(t: str, key: str, value: str) -> str:
        return re.sub(
            rf"^(\s+{re.escape(key)}\s*:).*$",
            rf"\g<1> {value}",
            t,
            flags=re.MULTILINE,
        )

    if dpi is not None:
        text = replace_scalar(text, "dpi", str(int(dpi)))
    if vlm_temperature is not None:
        text = replace_scalar(text, "temperature", str(float(vlm_temperature)))
    if poll_interval is not None:
        text = replace_scalar(text, "poll_interval", str(int(poll_interval)))
    if stable_checks is not None:
        text = replace_scalar(text, "stable_checks", str(int(stable_checks)))
    if idle_timeout is not None:
        text = replace_scalar(text, "idle_timeout", str(int(idle_timeout)))

    path.write_text(text, encoding="utf-8")
    return get_grading_config()


def get_grading_config() -> dict[str, Any]:
    """Expose a small, curated slice of the grading component config for display.

    Only a few user-facing fields are surfaced (image dpi, vlm model / temperature);
    the full config.yaml is intentionally not returned."""
    from services.vlm_grading_pipeline import _load_component_config

    cfg = _load_component_config()
    image = cfg.get("image") if isinstance(cfg.get("image"), dict) else {}
    vlm = cfg.get("vlm") if isinstance(cfg.get("vlm"), dict) else {}
    watch = cfg.get("watch") if isinstance(cfg.get("watch"), dict) else {}
    return {
        "dpi": image.get("dpi"),
        "vlm_temperature": vlm.get("temperature"),
        "poll_interval": watch.get("poll_interval"),
        "stable_checks": watch.get("stable_checks"),
        "idle_timeout": watch.get("idle_timeout"),
    }


def list_tasks(status: str | None = None) -> dict[str, Any]:
    """List all tasks (newest first), optionally filtered by status, with a
    per-status count over the full set (before filtering)."""
    jobs = _JOB_STORE.list_jobs()
    status_counts: dict[str, int] = {}
    for job in jobs:
        key = str(job.get("status", ""))
        status_counts[key] = status_counts.get(key, 0) + 1

    if status is not None:
        wanted = status.upper()
        jobs = [job for job in jobs if str(job.get("status", "")).upper() == wanted]

    jobs.sort(key=lambda j: str(j.get("created_at", "")), reverse=True)
    tasks = [
        {
            "task_id": job["job_id"],
            "task_type": str(job.get("task_type", "")),
            "status": job.get("status"),
            "current_step": job.get("current_step"),
            "progress": job.get("progress"),
            "error_message": job.get("error_message"),
            "created_at": job.get("created_at"),
            "updated_at": job.get("updated_at"),
            "log_path": job.get("log_path"),
            "dir_info": _dir_info(job),
        }
        for job in jobs
    ]
    return {"total": len(tasks), "status_counts": status_counts, "tasks": tasks}


def get_task_result(task_id: str) -> dict[str, Any]:
    task = get_task_status(task_id)
    status = task.get("status")
    if status != "COMPLETED":
        raise RuntimeError(f"task not completed, current status: {status}")
    result = task.get("result")
    if not isinstance(result, dict):
        raise RuntimeError("task completed but result is missing")
    return {"task_id": task_id, "task_type": str(task.get("task_type", "")), "status": status, "result": result}


# ---------------------------------------------------------------------------
# pause / resume (process stays up). pause is exit-based: the worker thread dies
# at its next checkpoint, leaving PAUSED persisted and no live worker. resume is
# an API that spawns exactly one fresh worker to continue from the items table.
# A fresh worker thread rebuilds the OCR engine (reset_ocr), because PaddleOCR's
# process-global predictor cannot be reused across the thread that first ran it.
# ---------------------------------------------------------------------------
def _spawn_task_worker(task_id: str) -> None:
    """Start the correct worker thread for a task, based on its mode. The worker
    resets the process-global OCR engine on entry so the new thread builds its
    own predictor (the old thread's is unusable across threads)."""
    request = _JOB_STORE.get_job(task_id).get("request") or {}
    if request.get("mode") == "directory":
        # Completed items in the persisted table are skipped; any pending item
        # (incl. one interrupted mid-paper) is re-graded whole.
        Thread(target=_run_directory_grading_task, args=(task_id,), daemon=True).start()
    else:
        # Single paper: no per-section checkpoint is persisted, so the whole
        # paper is re-graded from scratch.
        Thread(target=_run_grading_task, args=(task_id, request), daemon=True).start()


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
        # PAUSED is the only state with no live worker (pause is exit-based), so
        # spawning exactly one fresh worker here can never race an existing one.
        _JOB_STORE.set_control_action(task_id, None)
        resumed = _JOB_STORE.update_job(task_id, status="RUNNING", current_step="resume_requested")
        _spawn_task_worker(task_id)
        return resumed
    if status == "RUNNING":
        return _JOB_STORE.get_job(task_id)
    if status == "PAUSING":
        raise RuntimeError("task is pausing, retry resume after it reaches PAUSED")
    raise RuntimeError(f"resume not allowed in current status: {status}")


def delete_task(task_id: str) -> None:
    import shutil

    _validate_task_id(task_id)
    job = _JOB_STORE.get_job(task_id)
    status = str(job.get("status", ""))

    if status in _ACTIVE_TASK_STATUSES:
        try:
            _JOB_STORE.update_job(task_id, status="CANCELLED", current_step="deleted")
            _JOB_STORE.set_control_action(task_id, "cancel")
        except Exception:
            pass

    papers_dir_str = (job.get("request") or {}).get("papers_dir") or (job.get("request") or {}).get("paper_path")
    if papers_dir_str:
        lock = Path(str(papers_dir_str)) / ".grading.lock"
        try:
            lock.unlink(missing_ok=True)
        except Exception:
            pass

    outputs_dir = _outputs_root() / task_id
    if outputs_dir.exists():
        shutil.rmtree(outputs_dir, ignore_errors=True)

    log = _task_log_path(task_id, "grading.run")
    try:
        log.unlink(missing_ok=True)
    except Exception:
        pass

    _JOB_STORE.delete_job(task_id)


def request_task_cancel(task_id: str) -> dict[str, Any]:
    task = get_task_status(task_id)
    status = task.get("status")
    if status in {"RUNNING", "PAUSING", "PAUSED", "PENDING"}:
        _JOB_STORE.set_control_action(task_id, "cancel")
        return _JOB_STORE.update_job(task_id, status="CANCELLING", current_step="cancel_requested")
    if status in _TERMINAL_TASK_STATUSES or status == "CANCELLING":
        return _JOB_STORE.get_job(task_id)
    raise RuntimeError(f"cancel not allowed in current status: {status}")
