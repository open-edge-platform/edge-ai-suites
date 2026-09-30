import threading

from utils.va_completion import wait_for_va_completion


class FakeService:
    """Minimal stand-in for VideoAnalyticsPipelineService's completion surface."""

    def __init__(self, final_status=None, running=None):
        self.pipeline_final_status = dict(final_status or {})
        self._running = set(running or [])

    def is_pipeline_running(self, name):
        return name in self._running


def _wait(service, wanted, done=None, timeout=1.0, **kw):
    done = done if done is not None else threading.Event()
    final_status = {}
    ok = wait_for_va_completion(
        service, wanted, done, final_status, timeout, **kw
    )
    return ok, final_status


def test_done_event_returns_immediately():
    service = FakeService(running=["front"])
    done = threading.Event()
    done.set()
    ok, final_status = _wait(service, ["front"], done=done)
    assert ok is True


def test_all_final_status_eos_returns_true():
    service = FakeService(final_status={"front": "eos"}, running=["front"])
    ok, final_status = _wait(service, ["front"], timeout=0.2)
    assert ok is True
    assert final_status["front"] == "eos"


def test_any_final_status_failed_returns_true():
    service = FakeService(final_status={"front": "failed", "back": "eos"})
    ok, _ = _wait(service, ["front", "back"], timeout=0.2)
    assert ok is True


def test_all_processes_down_fallback_returns_true():
    service = FakeService(final_status={})  # nothing recorded
    ok, _ = _wait(service, ["front"], timeout=1.0, interval=0.01, grace_polls=2)
    assert ok is True


def test_running_until_timeout_returns_false():
    service = FakeService(running=["front"])
    ok, _ = _wait(service, ["front"], timeout=0.05, interval=0.01)
    assert ok is False


def test_final_status_refreshed_into_caller_dict():
    service = FakeService(final_status={"front": "eos"}, running=["front"])
    done = threading.Event()
    final_status = {"stale": True}
    ok = wait_for_va_completion(service, ["front"], done, final_status, 0.2)
    assert ok is True
    assert final_status == {"stale": True, "front": "eos"}


def test_brief_dip_does_not_complete_prematurely():
    """A pipeline that briefly drops then stays up must not complete via fallback."""
    service = FakeService(running=["front"])
    count = [0]

    def is_running(name):
        count[0] += 1
        if count[0] == 1:
            return False  # brief dip
        return True       # stays up

    service.is_pipeline_running = is_running
    # grace_polls=3 -> the single down tick never accumulates to 3, so it times out
    ok, _ = _wait(service, ["front"], timeout=0.3, interval=0.01, grace_polls=3)
    assert ok is False
