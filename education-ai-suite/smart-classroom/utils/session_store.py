import os
import json
import sqlite3
from datetime import datetime, timezone
from threading import Lock

from utils.pipeline_catalog import ALL_STAGES, SETTLED_STAGE_STATUSES
from utils.runtime_config_loader import RuntimeConfig

_DB_FILE = "sessions.db"


class SessionStore:
    """SQLite-backed session records.

    Deliberately without an in-memory row cache. One measured 5 ms, of which the
    SELECT it would have saved is 0.17 ms - the cost is the commit's fsync, not
    the read - so the cache bought about 3% on a call made a dozen times per
    session while growing without bound and going stale the moment a second
    process wrote a row.
    """

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
        # Autocommit
        conn.isolation_level = None
        return conn

    @classmethod
    def _create_table(cls, conn) -> None:
        """Take the caller's connection rather than opening its own: _mutate() needs the DDL, the
        read and the write to share one transaction."""
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
        cls._migrate(conn)

    @classmethod
    def _migrate(cls, conn) -> None:
        """Add columns introduced in later versions to pre-existing databases."""
        existing = {r[1] for r in conn.execute("PRAGMA table_info(sessions)")}
        if "cancel_requested" not in existing:
            conn.execute("ALTER TABLE sessions ADD COLUMN cancel_requested INTEGER DEFAULT 0")
        if "last_heartbeat" not in existing:
            conn.execute("ALTER TABLE sessions ADD COLUMN last_heartbeat TEXT")

    @classmethod
    def create(cls, session_id: str, request: dict, stages: list) -> dict:
        with cls._lock:
            now = _now_iso()
            state = {
                "session_id": session_id,
                "state": "pending",
                "stages": {s: "pending" for s in ALL_STAGES},
                "current_stage": None,
                "sources": _extract_sources(request),
                "error": None,
                "started_at": now,
                "updated_at": now,
                "request": request,
            }
            for s in stages:
                state["stages"][s] = "pending"
            for s in set(ALL_STAGES) - set(stages):
                state["stages"][s] = "skipped"
            conn = cls._conn()
            try:
                cls._create_table(conn)
                cls._write(conn, state)
            finally:
                conn.close()
            return dict(state)

    @classmethod
    def get(cls, session_id: str) -> dict | None:
        with cls._lock:
            conn = cls._conn()
            try:
                cls._create_table(conn)
                row = cls._select(conn, session_id)
                return _row_to_dict(row) if row else None
            finally:
                conn.close()

    @classmethod
    def _mutate(cls, session_id: str, apply) -> dict | None:
        """Read-modify-write one row inside a single write transaction.

        BEGIN IMMEDIATE takes the write lock up front, so a concurrent writer
        cannot slip a change in between the read and the write - _write() writes
        the whole row back, and would otherwise silently discard it.
        """
        with cls._lock:
            conn = cls._conn()
            try:
                cls._create_table(conn)
                conn.execute("BEGIN IMMEDIATE")
                try:
                    row = cls._select(conn, session_id)
                    if row is None:
                        conn.execute("ROLLBACK")
                        return None
                    state = _row_to_dict(row)
                    apply(state)
                    state["updated_at"] = _now_iso()
                    cls._write(conn, state)
                    conn.execute("COMMIT")
                except BaseException:
                    conn.execute("ROLLBACK")
                    raise
                return dict(state)
            finally:
                conn.close()

    @classmethod
    def update(cls, session_id: str, **fields) -> dict | None:
        return cls._mutate(session_id, lambda state: state.update(fields))

    @classmethod
    def set_stage(cls, session_id: str, stage: str, status: str) -> dict | None:
        def apply(state):
            if stage in state["stages"]:
                state["stages"][stage] = status
            if status in ("running", "done", "failed"):
                state["current_stage"] = stage
            cls._apply_derived_state(state)

        return cls._mutate(session_id, apply)

    @classmethod
    def _apply_derived_state(cls, state: dict) -> None:
        """Close out a client-driven session once every declared stage settles."""
        if state.get("state") != "running":
            return
        from utils import orchestrator
        if state.get("session_id") in orchestrator.running_session_ids():
            return

        stages = state.get("stages") or {}
        declared = [s for s in stages.values() if s != "skipped"]
        if not declared:
            return

        failed = sorted(s for s, st in stages.items() if st == "failed")
        interrupted = sorted(s for s, st in stages.items() if st == "interrupted")
        if failed or interrupted:
            reasons = []
            if failed:
                reasons.append(f"stage failed: {', '.join(failed)}")
            if interrupted:
                reasons.append(f"stage interrupted: {', '.join(interrupted)}")
            state["state"] = "failed"
            state["error"] = state.get("error") or "; ".join(reasons)
            return

        if any(s not in SETTLED_STAGE_STATUSES for s in declared):
            return
        state["state"] = "completed"

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
    def list_all(cls, limit: int | None = None, offset: int = 0) -> list:
        """Newest first, which is the order the history reads in. `limit=None`
        returns everything, for callers that need to scan (list_running_sessions)."""
        with cls._lock:
            conn = cls._conn()
            try:
                cls._create_table(conn)
                sql = "SELECT * FROM sessions ORDER BY started_at DESC, session_id DESC"
                params: tuple = ()
                if limit is not None:
                    sql += " LIMIT ? OFFSET ?"
                    params = (limit, max(0, offset))
                return [_row_to_dict(r) for r in conn.execute(sql, params).fetchall()]
            finally:
                conn.close()

    @classmethod
    def count(cls) -> int:
        with cls._lock:
            conn = cls._conn()
            try:
                cls._create_table(conn)
                return conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
            finally:
                conn.close()

    @classmethod
    def delete(cls, session_id: str) -> bool:
        with cls._lock:
            conn = cls._conn()
            try:
                cls._create_table(conn)
                cur = conn.execute(
                    "DELETE FROM sessions WHERE session_id = ?", (session_id,)
                )
                return cur.rowcount > 0
            finally:
                conn.close()

    @classmethod
    def recover_after_restart(cls) -> None:
        with cls._lock:
            conn = cls._conn()
            try:
                cls._create_table(conn)
                conn.execute("BEGIN IMMEDIATE")
                try:
                    rows = conn.execute(
                        "SELECT * FROM sessions WHERE state = 'running'"
                    ).fetchall()
                    for row in rows:
                        state = _row_to_dict(row)
                        state["state"] = "failed"
                        state["error"] = "process interrupted (restart)"
                        state["updated_at"] = _now_iso()
                        cls._write(conn, state)
                    conn.execute("COMMIT")
                except BaseException:
                    conn.execute("ROLLBACK")
                    raise
            finally:
                conn.close()

    @classmethod
    def _write(cls, conn, state: dict) -> None:
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

    @classmethod
    def _select(cls, conn, session_id: str) -> sqlite3.Row | None:
        return conn.execute(
            "SELECT * FROM sessions WHERE session_id = ?", (session_id,)
        ).fetchone()


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
