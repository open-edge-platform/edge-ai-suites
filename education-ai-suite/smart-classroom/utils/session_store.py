import os
import json
import sqlite3
from datetime import datetime, timezone
from threading import Lock

from utils.runtime_config_loader import RuntimeConfig

_ALL_STAGES = ("transcribe", "summarize", "mindmap", "va", "segmentation", "report")

_DB_FILE = "sessions.db"


class SessionStore:
    _states = {}
    _lock = Lock()

    @classmethod
    def _db_path(cls) -> str:
        proj = RuntimeConfig.get_section("Project")
        base = os.path.join(proj.get("location"), proj.get("name"))
        os.makedirs(base, exist_ok=True)
        return os.path.join(base, _DB_FILE)

    @classmethod
    def _conn(cls) -> sqlite3.Connection:
        conn = sqlite3.connect(cls._db_path(), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    @classmethod
    def _init_table(cls) -> None:
        conn = cls._conn()
        try:
            cls._create_table(conn)
        finally:
            conn.close()

    @classmethod
    def _create_table(cls, conn) -> None:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS sessions (
                session_id      TEXT PRIMARY KEY,
                state           TEXT,
                current_stage   TEXT,
                stages          TEXT,
                sources         TEXT,
                error           TEXT,
                started_at      TEXT,
                updated_at      TEXT,
                request         TEXT,
                cancel_requested INTEGER DEFAULT 0,
                last_heartbeat  TEXT
            )
            """
        )
        conn.commit()
        cls._migrate(conn)

    @classmethod
    def _migrate(cls, conn) -> None:
        """Add columns introduced in later versions to pre-existing databases."""
        existing = {r[1] for r in conn.execute("PRAGMA table_info(sessions)")}
        if "cancel_requested" not in existing:
            conn.execute("ALTER TABLE sessions ADD COLUMN cancel_requested INTEGER DEFAULT 0")
        if "last_heartbeat" not in existing:
            conn.execute("ALTER TABLE sessions ADD COLUMN last_heartbeat TEXT")
        conn.commit()

    @classmethod
    def create(cls, session_id: str, request: dict, stages: list) -> dict:
        with cls._lock:
            cls._init_table()
            now = _now_iso()
            state = {
                "session_id": session_id,
                "state": "pending",
                "stages": {s: "pending" for s in _ALL_STAGES},
                "current_stage": None,
                "sources": _extract_sources(request),
                "error": None,
                "started_at": now,
                "updated_at": now,
                "request": request,
            }
            for s in stages:
                state["stages"][s] = "pending"
            for s in set(_ALL_STAGES) - set(stages):
                state["stages"][s] = "skipped"
            cls._states[session_id] = state
            cls._upsert(state)
            return dict(state)

    @classmethod
    def get(cls, session_id: str) -> dict | None:
        with cls._lock:
            state = cls._states.get(session_id)
            if state:
                return dict(state)
            row = cls._select(session_id)
            if row:
                state = _row_to_dict(row)
                cls._states[session_id] = state
                return dict(state)
            return None

    @classmethod
    def update(cls, session_id: str, **fields) -> dict | None:
        with cls._lock:
            state = cls._states.get(session_id)
            if state is None:
                row = cls._select(session_id)
                if row is None:
                    return None
                state = _row_to_dict(row)
                cls._states[session_id] = state
            state.update(fields)
            state["updated_at"] = _now_iso()
            cls._upsert(state)
            return dict(state)

    @classmethod
    def set_stage(cls, session_id: str, stage: str, status: str) -> dict | None:
        with cls._lock:
            state = cls._states.get(session_id)
            if state is None:
                row = cls._select(session_id)
                if row is None:
                    return None
                state = _row_to_dict(row)
                cls._states[session_id] = state
            if stage in state["stages"]:
                state["stages"][stage] = status
            if status in ("running", "done", "failed"):
                state["current_stage"] = stage
            state["updated_at"] = _now_iso()
            cls._upsert(state)
            return dict(state)

    @classmethod
    def mark_completed(cls, session_id: str) -> dict | None:
        return cls.update(session_id, state="completed")

    @classmethod
    def mark_failed(cls, session_id: str, error: str) -> dict | None:
        return cls.update(session_id, state="failed", error=error)

    @classmethod
    def mark_cancelled(cls, session_id: str) -> dict | None:
        return cls.update(session_id, state="cancelled")

    @classmethod
    def list_all(cls) -> list:
        with cls._lock:
            cls._init_table()
            conn = cls._conn()
            try:
                rows = conn.execute("SELECT * FROM sessions ORDER BY started_at").fetchall()
                return [_row_to_dict(r) for r in rows]
            finally:
                conn.close()

    @classmethod
    def delete(cls, session_id: str) -> bool:
        with cls._lock:
            cls._init_table()
            conn = cls._conn()
            try:
                cur = conn.execute(
                    "DELETE FROM sessions WHERE session_id = ?", (session_id,)
                )
                conn.commit()
                deleted = cur.rowcount > 0
            finally:
                conn.close()
            cls._states.pop(session_id, None)
            return deleted

    @classmethod
    def recover_after_restart(cls) -> None:
        with cls._lock:
            cls._init_table()
            conn = cls._conn()
            try:
                rows = conn.execute("SELECT * FROM sessions WHERE state = 'running'").fetchall()
                for row in rows:
                    state = _row_to_dict(row)
                    state["state"] = "failed"
                    state["error"] = "process interrupted (restart)"
                    state["updated_at"] = _now_iso()
                    cls._states[state["session_id"]] = state
                    cls._upsert(state)
            finally:
                conn.close()

    @classmethod
    def _upsert(cls, state: dict) -> None:
        conn = cls._conn()
        try:
            cls._create_table(conn)
            conn.execute(
                """
                INSERT OR REPLACE INTO sessions
                (session_id, state, current_stage, stages, sources, error, started_at, updated_at, request,
                 cancel_requested, last_heartbeat)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    state["session_id"],
                    state.get("state"),
                    state.get("current_stage"),
                    json.dumps(state.get("stages"), ensure_ascii=False),
                    json.dumps(state.get("sources"), ensure_ascii=False),
                    state.get("error"),
                    state.get("started_at"),
                    state.get("updated_at"),
                    json.dumps(state.get("request"), ensure_ascii=False),
                    state.get("cancel_requested", 0),
                    state.get("last_heartbeat"),
                ),
            )
            conn.commit()
        finally:
            conn.close()

    @classmethod
    def _select(cls, session_id: str) -> sqlite3.Row | None:
        conn = cls._conn()
        try:
            cls._create_table(conn)
            return conn.execute(
                "SELECT * FROM sessions WHERE session_id = ?", (session_id,)
            ).fetchone()
        finally:
            conn.close()


def _row_to_dict(row) -> dict:
    return {
        "session_id": row["session_id"],
        "state": row["state"],
        "current_stage": row["current_stage"],
        "stages": json.loads(row["stages"] or "{}"),
        "sources": json.loads(row["sources"] or "{}"),
        "error": row["error"],
        "started_at": row["started_at"],
        "updated_at": row["updated_at"],
        "request": json.loads(row["request"] or "{}"),
        "cancel_requested": row["cancel_requested"] if "cancel_requested" in row.keys() else 0,
        "last_heartbeat": row["last_heartbeat"] if "last_heartbeat" in row.keys() else None,
    }


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _extract_sources(request: dict) -> dict:
    sources = {}
    audio = request.get("audio_path")
    if audio:
        sources["audio"] = os.path.basename(audio)
    video = request.get("video_sources") or {}
    video_files = {k: v for k, v in video.items() if v}
    if video_files:
        sources["video"] = {k: os.path.basename(v) for k, v in video_files.items()}
    return sources
