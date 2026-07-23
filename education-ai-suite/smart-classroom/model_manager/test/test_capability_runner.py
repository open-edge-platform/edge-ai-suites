import threading
import time

from model_manager.capability.runner import CapabilityRunner, QueueFullError, OomError


def test_returns_result():
    runner = CapabilityRunner(lambda x: x * 2)
    assert runner.submit(21) == 42


def test_exception_propagation():
    def boom():
        raise ValueError("boom")

    runner = CapabilityRunner(boom)
    try:
        runner.submit()
        assert False, "expected ValueError"
    except ValueError as exc:
        assert str(exc) == "boom"


def test_single_concurrency():
    started = threading.Event()
    release = threading.Event()
    active = []
    max_active = [0]
    lock = threading.Lock()

    def work():
        with lock:
            active.append(1)
            max_active[0] = max(max_active[0], len(active))
        started.set()
        release.wait(1.0)
        with lock:
            active.pop()
        return "done"

    runner = CapabilityRunner(work, max_concurrency=1, queue_max=8)

    results = []

    def call():
        results.append(runner.submit())

    t1 = threading.Thread(target=call)
    t1.start()
    started.wait(1.0)

    # Second submission must block on the semaphore, not run concurrently.
    t2 = threading.Thread(target=call)
    t2.start()
    time.sleep(0.1)

    release.set()
    t1.join(2.0)
    t2.join(2.0)

    assert max_active[0] == 1
    assert results == ["done", "done"]


def test_queue_rejection():
    release = threading.Event()
    in_call = threading.Event()

    def work():
        in_call.set()
        release.wait(2.0)
        return "ok"

    # max_concurrency=1, queue_max=1: one running occupies the only slot.
    runner = CapabilityRunner(work, max_concurrency=1, queue_max=1)

    t = threading.Thread(target=runner.submit)
    t.start()
    in_call.wait(1.0)

    try:
        runner.submit()
        assert False, "expected QueueFullError"
    except QueueFullError:
        pass
    finally:
        release.set()
        t.join(2.0)


def test_streaming_holds_slot_until_exhausted():
    def stream(n):
        for i in range(n):
            yield i

    runner = CapabilityRunner(stream, max_concurrency=1, queue_max=4)
    it = runner.submit(3)

    assert list(it) == [0, 1, 2]
    # Slot released after exhaustion — a subsequent call still works.
    assert list(runner.submit(2)) == [0, 1]


def test_oom_fails_one_request_runner_stays_ready():
    """RuntimeError (simulated GPU OOM) wraps to OomError; runner stays READY."""
    call_count = [0]

    def sometimes_oom():
        call_count[0] += 1
        if call_count[0] == 1:
            raise RuntimeError("CUDA out of memory. Tried to allocate 2.00 GiB")
        return "ok"

    runner = CapabilityRunner(sometimes_oom)

    try:
        runner.submit()
        assert False, "expected OomError"
    except OomError:
        pass

    # Slot must be released — queue counter back to zero.
    assert runner._current_queue == 0
    # Runner is READY: next request succeeds.
    assert runner.submit() == "ok"


def test_memory_error_wrapped_as_oom():
    """Python MemoryError is also wrapped to OomError."""
    runner = CapabilityRunner(lambda: (_ for _ in ()).throw(MemoryError("no memory")))
    try:
        runner.submit()
        assert False, "expected OomError"
    except OomError:
        pass
    assert runner._current_queue == 0


def test_oom_in_stream_releases_slot():
    """OOM mid-stream raises OomError and releases the slot."""
    def oom_stream():
        yield 1
        raise RuntimeError("out of memory")

    runner = CapabilityRunner(oom_stream, max_concurrency=1, queue_max=4)
    it = runner.submit()
    assert next(it) == 1

    try:
        next(it)
        assert False, "expected OomError"
    except OomError:
        pass

    # Slot released — runner accepts new requests.
    assert runner._current_queue == 0


if __name__ == "__main__":
    for name in sorted(n for n in dir() if n.startswith("test_")):
        globals()[name]()
    print("ALL TESTS PASSED")