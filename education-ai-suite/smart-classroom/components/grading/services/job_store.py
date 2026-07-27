from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any
from uuid import uuid4


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class JsonJobStore:
    def __init__(self, store_path: Path) -> None:
        self._store_path = store_path
        self._lock = Lock()
        self._jobs: dict[str, dict[str, Any]] = {}
        self._load()

    def _load(self) -> None:
        self._store_path.parent.mkdir(parents=True, exist_ok=True)
        if not self._store_path.exists():
            self._persist()
            return

        try:
            raw = json.loads(self._store_path.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                self._jobs = raw
        except Exception:
            # Keep service alive even if store file is malformed.
            self._jobs = {}
            self._persist()

    def _persist(self) -> None:
        self._store_path.write_text(
            json.dumps(self._jobs, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def create_job(self, task_type: str, request_payload: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            job_id = str(uuid4())
            ts = _now_iso()
            job = {
                "job_id": job_id,
                "task_type": task_type,
                "status": "PENDING",
                "current_step": "queued",
                "progress": 0,
                "control_action": None,
                "control_requested_at": None,
                "checkpoint_step": None,
                "request": request_payload,
                "result": None,
                "error_message": None,
                "created_at": ts,
                "updated_at": ts,
            }
            self._jobs[job_id] = job
            self._persist()
            return dict(job)

    def update_job(self, job_id: str, **updates: Any) -> dict[str, Any]:
        with self._lock:
            if job_id not in self._jobs:
                raise KeyError(job_id)
            self._jobs[job_id].update(updates)
            self._jobs[job_id]["updated_at"] = _now_iso()
            self._persist()
            return dict(self._jobs[job_id])

    def get_job(self, job_id: str) -> dict[str, Any]:
        with self._lock:
            if job_id not in self._jobs:
                raise KeyError(job_id)
            return dict(self._jobs[job_id])

    def list_jobs(self, task_type: str | None = None) -> list[dict[str, Any]]:
        with self._lock:
            return [
                dict(job)
                for job in self._jobs.values()
                if task_type is None or str(job.get("task_type")) == task_type
            ]

    def delete_job(self, job_id: str) -> dict[str, Any]:
        with self._lock:
            if job_id not in self._jobs:
                raise KeyError(job_id)
            job = dict(self._jobs.pop(job_id))
            self._persist()
            return job

    def set_control_action(self, job_id: str, action: str | None) -> dict[str, Any]:
        with self._lock:
            if job_id not in self._jobs:
                raise KeyError(job_id)

            if action not in {None, "pause", "cancel"}:
                raise ValueError(f"unsupported control action: {action}")

            self._jobs[job_id]["control_action"] = action
            self._jobs[job_id]["control_requested_at"] = _now_iso() if action else None
            self._jobs[job_id]["updated_at"] = _now_iso()
            self._persist()
            return dict(self._jobs[job_id])

    def find_latest_job(
        self,
        *,
        task_type: str | None = None,
        request_field: str | None = None,
        request_value: Any = None,
    ) -> dict[str, Any] | None:
        with self._lock:
            candidates: list[dict[str, Any]] = []
            for job in self._jobs.values():
                if task_type is not None and str(job.get("task_type")) != task_type:
                    continue
                if request_field is not None:
                    request_payload = job.get("request")
                    if not isinstance(request_payload, dict):
                        continue
                    if request_payload.get(request_field) != request_value:
                        continue
                candidates.append(job)

            if not candidates:
                return None

            candidates.sort(key=lambda x: str(x.get("created_at", "")), reverse=True)
            return dict(candidates[0])
