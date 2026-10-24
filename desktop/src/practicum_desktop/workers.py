from __future__ import annotations

from collections.abc import Callable
from typing import Any, ClassVar

from PySide6.QtCore import QThread, Signal


class ManagedThread(QThread):
    """A QThread that cannot be garbage-collected while it is running.

    Qt aborts the whole process with "QThread: Destroyed while thread '' is still running"
    when the Python wrapper of a running thread is dropped - which happened whenever a
    screen replaced `self._some_worker = CallableWorker(...)` while the previous call was
    still in flight (a second "Use <port>" click, a status poll firing before a slow
    `docker inspect` round returned). Every instance registers itself here on start and is
    released when it finishes, so a caller dropping its reference is harmless.
    """

    _active: ClassVar[set[ManagedThread]] = set()

    def start(self, *args: Any, **kwargs: Any) -> None:
        ManagedThread._active.add(self)
        self.finished.connect(self._release)
        super().start(*args, **kwargs)

    def _release(self) -> None:
        ManagedThread._active.discard(self)

    @classmethod
    def active_count(cls) -> int:
        return len(cls._active)

    @classmethod
    def wait_for_all(cls, timeout_ms: int = 2000) -> bool:
        """Waits for every running worker (used when the window closes). Returns True when
        all finished within the timeout."""
        done = True
        for worker in list(cls._active):
            if worker.isRunning() and not worker.wait(timeout_ms):
                done = False
        return done


class CallableWorker(ManagedThread):
    """Runs any blocking callable off the UI thread and reports the result via a signal."""

    finished_call = Signal(object)

    def __init__(self, func: Callable[..., Any], *args: Any, parent=None, **kwargs: Any) -> None:
        super().__init__(parent)
        self._func = func
        self._args = args
        self._kwargs = kwargs

    def run(self) -> None:
        result = self._func(*self._args, **self._kwargs)
        self.finished_call.emit(result)
