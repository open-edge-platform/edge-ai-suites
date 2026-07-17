from threading import Semaphore, Lock
from typing import Callable, Any, Iterator


class QueueFullError(Exception):
    """Raised when the capability queue is at capacity."""
    pass


class OomError(Exception):
    """Raised when a capability call fails due to memory pressure (OOM).

    The CapabilityRunner slot is always released before this propagates, so
    the runner remains READY and subsequent requests can proceed normally.
    """
    pass


class CapabilityRunner:
    def __init__(self, fn: Callable, *, max_concurrency: int = 1,
                 queue_max: int = 8, timeout_s: float | None = None):
        self._fn = fn
        self._semaphore = Semaphore(max_concurrency)
        self._queue_max = queue_max
        self._current_queue = 0
        self._lock = Lock()
        self._timeout_s = timeout_s

    def _release_slot(self) -> None:
        self._semaphore.release()
        with self._lock:
            self._current_queue -= 1

    def _wrap_stream(self, iterator: Iterator) -> Iterator:
        try:
            for item in iterator:
                yield item
        except (RuntimeError, MemoryError) as exc:
            raise OomError(str(exc)) from exc
        finally:
            self._release_slot()

    def submit(self, *args, **kwargs) -> Any:
        with self._lock:
            if self._current_queue >= self._queue_max:
                raise QueueFullError(f"Queue full ({self._queue_max})")
            self._current_queue += 1

        acquired = self._semaphore.acquire(timeout=self._timeout_s)
        if not acquired:
            with self._lock:
                self._current_queue -= 1
            raise QueueFullError(f"Timed out acquiring capacity after {self._timeout_s}s")

        released = False
        try:
            result = self._fn(*args, **kwargs)
            if hasattr(result, "__next__") and hasattr(result, "__iter__"):
                # Streaming callable: keep the slot held until the caller
                # exhausts the iterator.
                released = True
                return self._wrap_stream(result)
            return result
        except (RuntimeError, MemoryError) as exc:
            raise OomError(str(exc)) from exc
        finally:
            if not released:
                self._release_slot()