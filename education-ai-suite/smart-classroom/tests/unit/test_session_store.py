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
    # Simulate an old DB without the new columns, then touch the store.
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

        # Any entry point will do — they all create/migrate the schema on the
        # connection they open. Going through a public one proves the migration
        # reaches a real caller, not just a helper written for this test.
        SessionStore.count()

        conn = sqlite3.connect(db)
        cols = {r[1] for r in conn.execute("PRAGMA table_info(sessions)")}
        conn.close()
        assert "cancel_requested" in cols
        assert "last_heartbeat" in cols

# ----- derived terminal state -----
#
# A session registered through POST /sessions/register has no single call that
# owns its lifetime, so completion is derived from the stages themselves.

def _register(stages):
    SessionStore.create("s1", {"stages": stages}, stages)
    SessionStore.update("s1", state="running")


def test_stays_running_until_every_declared_stage_settles():
    with tempfile.TemporaryDirectory() as tmp, _patch_db(tmp):
        _register(["transcribe", "summarize"])
        SessionStore.set_stage("s1", "transcribe", "done")
        assert SessionStore.get("s1")["state"] == "running"
        SessionStore.set_stage("s1", "summarize", "done")
        assert SessionStore.get("s1")["state"] == "completed"


def test_skipped_stages_do_not_hold_a_session_open():
    with tempfile.TemporaryDirectory() as tmp, _patch_db(tmp):
        _register(["transcribe"])  # the other five are marked skipped
        SessionStore.set_stage("s1", "transcribe", "done")
        assert SessionStore.get("s1")["state"] == "completed"


def test_a_failed_stage_fails_the_session_without_waiting():
    """A broken stage usually stops the ones after it from ever starting, so the
    session must not sit waiting for stages that will stay pending forever."""
    with tempfile.TemporaryDirectory() as tmp, _patch_db(tmp):
        _register(["transcribe", "summarize"])
        SessionStore.set_stage("s1", "transcribe", "failed")
        state = SessionStore.get("s1")
        assert state["state"] == "failed"
        assert "transcribe" in state["error"]
        assert state["stages"]["summarize"] == "pending"


def test_an_interrupted_stage_fails_the_session_and_says_so():
    with tempfile.TemporaryDirectory() as tmp, _patch_db(tmp):
        _register(["transcribe"])
        SessionStore.set_stage("s1", "transcribe", "interrupted")
        state = SessionStore.get("s1")
        assert state["state"] == "failed"
        # A client that hung up is a different story from a stage that broke.
        assert state["error"] == "stage interrupted: transcribe"


def test_regenerating_a_stage_does_not_reopen_a_finished_session():
    """Report regeneration writes running/done onto a completed session; it must
    not drag the session back to running."""
    with tempfile.TemporaryDirectory() as tmp, _patch_db(tmp):
        _register(["transcribe"])
        SessionStore.set_stage("s1", "transcribe", "done")
        assert SessionStore.get("s1")["state"] == "completed"
        SessionStore.set_stage("s1", "report", "running")
        assert SessionStore.get("s1")["state"] == "completed"
        SessionStore.set_stage("s1", "report", "done")
        assert SessionStore.get("s1")["state"] == "completed"


def test_pending_sessions_are_not_derived():
    """create() leaves a session pending; only register/orchestrator promote it
    to running, and only a running session is ever derived."""
    with tempfile.TemporaryDirectory() as tmp, _patch_db(tmp):
        SessionStore.create("s1", {"stages": ["transcribe"]}, ["transcribe"])
        SessionStore.set_stage("s1", "transcribe", "done")
        assert SessionStore.get("s1")["state"] == "pending"


def test_orchestrator_owned_sessions_end_themselves():
    """_run_inner() already marks the run completed/failed and knows about
    failures between stages; deriving here would race it."""
    with tempfile.TemporaryDirectory() as tmp, _patch_db(tmp):
        _register(["transcribe"])
        with patch("utils.orchestrator.running_session_ids", return_value=["s1"]):
            SessionStore.set_stage("s1", "transcribe", "done")
            assert SessionStore.get("s1")["state"] == "running"


# ----- listing -----

def test_list_all_is_newest_first():
    with tempfile.TemporaryDirectory() as tmp, _patch_db(tmp):
        for sid, started in (("old", "2026-09-01T10:00:00"), ("new", "2026-09-09T10:00:00")):
            SessionStore.create(sid, {}, ["transcribe"])
            SessionStore.update(sid, started_at=started)
        assert [s["session_id"] for s in SessionStore.list_all()] == ["new", "old"]


def test_list_all_pages():
    with tempfile.TemporaryDirectory() as tmp, _patch_db(tmp):
        for i in range(5):
            SessionStore.create(f"s{i}", {}, ["transcribe"])
            SessionStore.update(f"s{i}", started_at=f"2026-09-0{i + 1}T10:00:00")
        page = SessionStore.list_all(limit=2, offset=1)
        assert [s["session_id"] for s in page] == ["s3", "s2"]
        assert SessionStore.count() == 5


def test_mutating_a_missing_session_returns_none():
    with tempfile.TemporaryDirectory() as tmp, _patch_db(tmp):
        assert SessionStore.update("nope", state="running") is None
        assert SessionStore.set_stage("nope", "transcribe", "done") is None


def test_a_write_that_raises_leaves_the_row_untouched():
    """The read-modify-write is a transaction, so a half-applied change must not
    reach disk."""
    with tempfile.TemporaryDirectory() as tmp, _patch_db(tmp):
        SessionStore.create("s1", {}, ["transcribe"])

        def boom(state):
            state["state"] = "running"
            raise RuntimeError("boom")

        try:
            SessionStore._mutate("s1", boom)
        except RuntimeError:
            pass
        assert SessionStore.get("s1")["state"] == "pending"
