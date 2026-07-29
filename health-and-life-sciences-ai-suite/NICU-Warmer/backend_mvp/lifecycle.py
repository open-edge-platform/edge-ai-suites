from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import threading
from typing import Optional


class Lifecycle(str, Enum):
    INITIALIZING = "initializing"
    PREPARING = "preparing"
    READY = "ready"
    STARTING = "starting"
    RUNNING = "running"
    ERROR = "error"


_ALLOWED_TRANSITIONS: dict[Lifecycle, set[Lifecycle]] = {
    Lifecycle.INITIALIZING: {Lifecycle.PREPARING, Lifecycle.ERROR},
    Lifecycle.PREPARING: {Lifecycle.READY, Lifecycle.ERROR},
    Lifecycle.READY: {Lifecycle.STARTING, Lifecycle.PREPARING, Lifecycle.ERROR},
    Lifecycle.STARTING: {Lifecycle.RUNNING, Lifecycle.READY, Lifecycle.ERROR},
    Lifecycle.RUNNING: {Lifecycle.READY, Lifecycle.ERROR},
    # Allow ERROR -> READY so the user can recover by clicking Stop or by
    # applying a different device profile, without restarting the container.
    Lifecycle.ERROR: {Lifecycle.PREPARING, Lifecycle.READY},
}


def allowed_transitions() -> dict[str, list[str]]:
    return {
        src.value: sorted(dst.value for dst in dsts)
        for src, dsts in _ALLOWED_TRANSITIONS.items()
    }


@dataclass(frozen=True)
class LifecycleSnapshot:
    lifecycle: str
    last_error: Optional[str]


class LifecycleManager:
    def __init__(self) -> None:
        self._state = Lifecycle.INITIALIZING
        self._last_error: Optional[str] = None
        self._lock = threading.Lock()

    def transition(self, target: Lifecycle) -> None:
        with self._lock:
            if target not in _ALLOWED_TRANSITIONS[self._state]:
                raise ValueError(
                    f"Invalid lifecycle transition: {self._state.value} -> {target.value}"
                )
            self._state = target
            if target != Lifecycle.ERROR:
                self._last_error = None

    def start_transition(self) -> bool:
        """Atomically transition from READY to STARTING.

        Returns False when lifecycle is not READY, which protects against
        duplicate starts under concurrent requests.
        """
        with self._lock:
            if self._state != Lifecycle.READY:
                return False
            self._state = Lifecycle.STARTING
            self._last_error = None
            return True

    def mark_error(self, error: str) -> None:
        with self._lock:
            self._state = Lifecycle.ERROR
            self._last_error = error

    def can_start(self) -> bool:
        with self._lock:
            return self._state == Lifecycle.READY

    def state(self) -> Lifecycle:
        with self._lock:
            return self._state

    def snapshot(self) -> LifecycleSnapshot:
        with self._lock:
            return LifecycleSnapshot(
                lifecycle=self._state.value,
                last_error=self._last_error,
            )
