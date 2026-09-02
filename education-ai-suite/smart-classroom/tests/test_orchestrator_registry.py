import threading
from unittest.mock import patch

from utils import orchestrator


def _clear():
    with orchestrator._RUNNING_LOCK:
        orchestrator._RUNNING.clear()


def _new_task():
    return orchestrator._RunningTask(thread=object(), cancel_event=threading.Event())


def test_start_process_registers_session():
    with orchestrator._RUNNING_LOCK:
        orchestrator._RUNNING.clear()
    with patch.object(orchestrator, "generate_session_id", return_value="s1"), patch.object(
        orchestrator, "session_store"
    ), patch.object(orchestrator.threading, "Thread") as mthread:
        mthread.return_value.start = lambda: None
        orchestrator.start_process({"stages": ["transcribe"], "audio_path": "/x.wav"})
    try:
        assert "s1" in orchestrator.running_session_ids()
    finally:
        _clear()


def test_request_cancel_sets_event():
    _clear()
    task = _new_task()
    with orchestrator._RUNNING_LOCK:
        orchestrator._RUNNING["s1"] = task
    try:
        ok = orchestrator.request_cancel("s1")
        assert ok is True
        assert task.cancel_event.is_set()
    finally:
        _clear()


def test_request_cancel_stops_va_service():
    _clear()
    with orchestrator._RUNNING_LOCK:
        orchestrator._RUNNING["s1"] = _new_task()
    class FakeVA:
        def __init__(self):
            self.stopped = False
        def stop_all_pipelines(self, timeout=None):
            self.stopped = True
    va = FakeVA()
    with orchestrator._RUNNING_LOCK:
        orchestrator._RUNNING["s1"].va_service = va
    try:
        orchestrator.request_cancel("s1")
        assert va.stopped is True
    finally:
        _clear()


def test_request_cancel_no_task_returns_false():
    _clear()
    assert orchestrator.request_cancel("nope") is False


def test_concurrency_gate_rejects_when_full():
    _clear()
    # pre-fill 2 running tasks (the limit)
    with orchestrator._RUNNING_LOCK:
        orchestrator._RUNNING["s1"] = _new_task()
        orchestrator._RUNNING["s2"] = _new_task()
    try:
        with patch.object(orchestrator, "generate_session_id", return_value="s9"), patch.object(
            orchestrator, "session_store"
        ):
            try:
                orchestrator.start_process({"stages": ["transcribe"], "audio_path": "/x.wav"})
            except orchestrator._ConcurrencyLimit:
                assert True
            else:
                assert False, "expected _ConcurrencyLimit"
    finally:
        _clear()


def test_concurrency_gate_allows_when_under_limit():
    _clear()
    with patch.object(orchestrator, "generate_session_id", return_value="s1"), patch.object(
        orchestrator, "session_store"
    ), patch.object(orchestrator.threading, "Thread") as mthread:
        mthread.return_value.start = lambda: None
        orchestrator.start_process({"stages": ["transcribe"], "audio_path": "/x.wav"})
    try:
        assert "s1" in orchestrator.running_session_ids()
        # allow a second one
        with patch.object(orchestrator, "generate_session_id", return_value="s2"), patch.object(
            orchestrator, "session_store"
        ), patch.object(orchestrator.threading, "Thread") as mt2:
            mt2.return_value.start = lambda: None
            orchestrator.start_process({"stages": ["transcribe"], "audio_path": "/x.wav"})
        assert "s2" in orchestrator.running_session_ids()
    finally:
        _clear()