"""Base monitor interface for video stream processors."""

from __future__ import annotations

from abc import ABC, abstractmethod


class BaseMonitor(ABC):
    @abstractmethod
    def start(self) -> None: ...

    @abstractmethod
    def stop(self) -> None: ...

    @abstractmethod
    def pause(self) -> None: ...

    @abstractmethod
    def resume(self) -> None: ...

    @property
    @abstractmethod
    def status(self) -> str: ...

    @property
    @abstractmethod
    def is_running(self) -> bool: ...
