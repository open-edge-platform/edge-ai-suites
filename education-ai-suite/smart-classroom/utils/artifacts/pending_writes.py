import threading


class PendingWrites:

    _lock = threading.Lock()
    _n = 0

    @classmethod
    def inc(cls):
        with cls._lock:
            cls._n += 1

    @classmethod
    def dec(cls):
        with cls._lock:
            cls._n -= 1

    @classmethod
    def count(cls) -> int:
        with cls._lock:
            return cls._n

    @classmethod
    def is_idle(cls) -> bool:
        with cls._lock:
            return cls._n == 0
