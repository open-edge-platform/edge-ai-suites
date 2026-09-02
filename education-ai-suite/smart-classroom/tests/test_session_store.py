import sqlite3
import tempfile
from pathlib import Path
from unittest.mock import patch

from utils.session_store import SessionStore


def _patch_db(tmp):
    return patch(
        "utils.session_store.SessionStore._db_path",
        return_value=str(Path(tmp) / "sessions.db"),
    )


def test_create_and_update_new_columns():
    with tempfile.TemporaryDirectory() as tmp, _patch_db(tmp):
        SessionStore.create("s1", {"stages": ["transcribe"]}, ["transcribe"])
        SessionStore.update("s1", cancel_requested=1, last_heartbeat="2026-09-01T10:00:00Z")
        state = SessionStore.get("s1")
        assert state["cancel_requested"] == 1
        assert state["last_heartbeat"] == "2026-09-01T10:00:00Z"


def test_mark_cancelled():
    with tempfile.TemporaryDirectory() as tmp, _patch_db(tmp):
        SessionStore.create("s1", {"stages": ["transcribe"]}, ["transcribe"])
        SessionStore.mark_cancelled("s1")
        state = SessionStore.get("s1")
        assert state["state"] == "cancelled"


def test_migration_adds_columns_to_existing_db():
    # Simulate an old DB without the new columns, then have _init_table migrate it.
    with tempfile.TemporaryDirectory() as tmp, _patch_db(tmp):
        db = str(Path(tmp) / "sessions.db")
        conn = sqlite3.connect(db)
        conn.execute(
            "CREATE TABLE sessions (session_id TEXT PRIMARY KEY, state TEXT, "
            "current_stage TEXT, stages TEXT, sources TEXT, error TEXT, "
            "started_at TEXT, updated_at TEXT, request TEXT)"
        )
        conn.commit()
        conn.close()

        SessionStore._init_table()

        conn = sqlite3.connect(db)
        cols = {r[1] for r in conn.execute("PRAGMA table_info(sessions)")}
        conn.close()
        assert "cancel_requested" in cols
        assert "last_heartbeat" in cols