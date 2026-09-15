"""Regression tests for stopping video-analytics pipelines and reporting status.

Both bugs covered here had the same symptom in the app: the user pressed Stop
and the video kept streaming.

  1. stop_pipeline() used to set the monitor thread's stop flag *after* it had
     already terminated the process. The monitor polls every 2s and treats any
     non-graceful exit as a crash to relaunch, so it could put a fresh pipeline
     into self.pipelines that stop_pipeline then deleted without killing -
     leaving a live, untracked pipeline nothing could ever stop.

  2. monitor_pipeline_status() computed `all_stopped` and never used it, so the
     status stream ran `while True` forever. The response body never ended and
     every session permanently pinned one of the browser's six connections per
     origin; once they ran out, the Stop button's own requests never got a
     socket and were queued indefinitely.

The service is built with object.__new__ rather than its constructor, which
resolves model paths and settles the DL Streamer environment - neither is
needed by, or relevant to, the logic under test.
"""

import asyncio
import logging
import threading

import pytest

from components.va import va_pipeline_service as va_mod
from components.va.va_pipeline_service import VideoAnalyticsPipelineService


class FakeProcess:
    """Stand-in for PipelineRunnerClient with the surface these methods touch."""

    def __init__(self, alive=True, normal_exit=False, error="boom", pid=4321):
        self._alive = alive
        self._normal_exit = normal_exit
        self._error = error
        self.pid = pid
        self.returncode = None if alive else 1
        self.final_event = "eos" if normal_exit else "error"
        self.terminated = False
        self.killed = False
        self.closed = False
        self.stop_requested = False
        # Set by the test to capture the stop flag's state at kill time.
        self.on_terminate = None

    def poll(self):
        return None if self._alive else (self.returncode or 1)

    def exited_normally(self):
        return self._normal_exit

    def error_text(self):
        return self._error

    def request_stop(self):
        self.stop_requested = True
        self._die()
        return True

    def terminate(self):
        self.terminated = True
        self._die()

    def kill(self):
        self.killed = True
        self._die()

    def _die(self):
        if self.on_terminate:
            self.on_terminate()
        self._alive = False
        self.returncode = self.returncode or 1

    def wait(self, timeout=None):
        return self.returncode

    def close(self):
        self.closed = True


def make_service(**attrs):
    """A service with only the attributes the methods under test read."""
    svc = object.__new__(VideoAnalyticsPipelineService)
    svc.logger = logging.getLogger("test.va")
    svc.pipelines = {}
    svc.pipeline_logs = {}
    svc.pipeline_log_handles = {}
    svc.pipeline_output_files = {}
    svc.monitor_threads = {}
    svc.monitor_stop_flags = {}
    svc.pipeline_params = {}
    svc.pipeline_retry_counts = {}
    svc.pipeline_final_status = {}
    svc.pipeline_errors = {}
    svc.max_retries = 10
    svc.on_all_pipelines_done = None
    svc._reports_generated = False
    svc._any_pipeline_ran = True
    for key, value in attrs.items():
        setattr(svc, key, value)
    return svc


@pytest.fixture
def no_rtsp_recorder(monkeypatch):
    """stop_pipeline calls out to the recorder; irrelevant here."""
    monkeypatch.setattr(va_mod, "stop_rtsp_recording", lambda name: None)


# --- 1. the stop/monitor race ------------------------------------------------


def test_stop_pipeline_sets_monitor_flag_before_killing(no_rtsp_recorder):
    """The monitor must be retired before the process can look like a crash."""
    flag = threading.Event()
    proc = FakeProcess(alive=True)
    seen = {}
    proc.on_terminate = lambda: seen.setdefault("flag_set", flag.is_set())

    svc = make_service(
        pipelines={"front": proc},
        monitor_stop_flags={"front": flag},
    )

    assert svc.stop_pipeline("front") is True
    assert seen["flag_set"] is True, "monitor was still armed when the process died"
    assert flag.is_set()


def test_stop_pipeline_leaves_no_untracked_pipeline(no_rtsp_recorder):
    """After a stop, nothing is left in the registry for this pipeline."""
    svc = make_service(
        pipelines={"front": FakeProcess(alive=True)},
        monitor_stop_flags={"front": threading.Event()},
        pipeline_params={"front": {"options": object(), "description": "..."}},
        pipeline_retry_counts={"front": 3},
    )

    svc.stop_pipeline("front")

    assert "front" not in svc.pipelines
    assert svc.pipeline_final_status["front"] == "stopped"
    assert "front" not in svc.pipeline_params
    assert "front" not in svc.pipeline_retry_counts


def test_monitor_does_not_restart_a_pipeline_being_stopped():
    """The in-loop guard: the flag may be set after the iteration has begun."""
    flag = threading.Event()
    # A crashed-looking process that trips the stop flag the moment the monitor
    # inspects it - exactly the race stop_pipeline() creates.
    proc = FakeProcess(alive=False, normal_exit=False)
    original_exited_normally = proc.exited_normally

    def exited_normally():
        flag.set()
        return original_exited_normally()

    proc.exited_normally = exited_normally

    svc = make_service(
        pipelines={"front": proc},
        monitor_stop_flags={"front": flag},
        pipeline_params={"front": {"options": object(), "description": "..."}},
    )

    launches = []
    svc._launch_pipeline_internal = lambda *a, **kw: launches.append(a)

    svc._monitor_pipeline("front")

    assert launches == [], "monitor relaunched a pipeline that was being stopped"


def test_monitor_still_restarts_a_genuine_crash():
    """The guard must not cost us the ordinary auto-restart."""
    flag = threading.Event()
    proc = FakeProcess(alive=False, normal_exit=False)

    svc = make_service(
        pipelines={"front": proc},
        monitor_stop_flags={"front": flag},
        pipeline_params={"front": {"options": "opts", "description": "desc"}},
    )

    launches = []

    def fake_launch(name, options, description):
        launches.append(name)
        # Stop the loop after one restart so the test terminates.
        flag.set()

    svc._launch_pipeline_internal = fake_launch

    svc._monitor_pipeline("front")

    assert launches == ["front"]
    assert svc.pipeline_retry_counts["front"] == 1


# --- 2. the status stream that never ended -----------------------------------


def drain(agen, limit=10):
    """Collect frames from the async generator, with a cap so a regression to
    `while True` fails the test instead of hanging it."""

    async def run():
        frames = []
        async for frame in agen:
            frames.append(frame)
            if len(frames) >= limit:
                raise AssertionError("status stream did not end")
        return frames

    return asyncio.run(run())


def test_status_stream_ends_once_every_pipeline_is_settled():
    svc = make_service(
        pipelines={"front": FakeProcess(alive=False, normal_exit=True)},
        pipeline_final_status={"front": "eos"},
    )

    frames = drain(svc.monitor_pipeline_status(check_interval=0))

    assert len(frames) == 1
    front = next(p for p in frames[0]["pipelines"] if p["pipeline_name"] == "front")
    assert front["status"] == "stopped_normal"
    assert front["final_status"] == "eos"


def test_status_stream_ends_after_pipelines_are_deregistered():
    """stop_pipeline removes the entry entirely; the stream must still end."""
    svc = make_service(pipelines={}, pipeline_final_status={"front": "stopped"})

    frames = drain(svc.monitor_pipeline_status(check_interval=0))

    assert len(frames) == 1
    assert all(p["status"] == "not_found" for p in frames[0]["pipelines"])


def test_status_stream_stays_open_across_a_crash_and_restart():
    """Dead but not finalised means a relaunch is coming - not a terminal state."""
    proc = FakeProcess(alive=False, normal_exit=False, error="rtsp: failed to connect")
    svc = make_service(
        pipelines={"front": proc},
        pipeline_final_status={},  # monitor thread has not given a verdict
    )

    with pytest.raises(AssertionError, match="did not end"):
        drain(svc.monitor_pipeline_status(check_interval=0), limit=3)


def test_status_stream_reports_the_failure_reason():
    """The detail the UI puts in front of the user for a bad source URL."""
    proc = FakeProcess(alive=False, normal_exit=False, error="Failed to connect")
    svc = make_service(
        pipelines={"front": proc},
        pipeline_final_status={"front": "failed"},
    )

    frames = drain(svc.monitor_pipeline_status(check_interval=0))

    front = next(p for p in frames[0]["pipelines"] if p["pipeline_name"] == "front")
    assert front["status"] == "stopped_error"
    assert front["final_status"] == "failed"
    assert front["errors"] == ["Failed to connect"]


def test_status_stream_waits_for_the_first_pipeline_to_register():
    """A client can connect a beat before the pipelines exist."""
    svc = make_service(pipelines={}, _any_pipeline_ran=False)

    with pytest.raises(AssertionError, match="did not end"):
        drain(svc.monitor_pipeline_status(check_interval=0), limit=3)
