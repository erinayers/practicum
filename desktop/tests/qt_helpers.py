from __future__ import annotations

from typing import ClassVar

from PySide6.QtCore import QObject, Signal


class ImmediateWorker(QObject):
    """Drop-in for CallableWorker that runs the callable synchronously on the calling
    thread, so widget tests don't need to wait on real QThreads. Monkeypatch it onto the
    module under test: `monkeypatch.setattr(some_module, "CallableWorker", ImmediateWorker)`."""

    finished_call = Signal(object)

    def __init__(self, func, *args, **kwargs) -> None:
        super().__init__()
        self._func = func
        self._args = args
        self._kwargs = kwargs

    def start(self) -> None:
        self.finished_call.emit(self._func(*self._args, **self._kwargs))


class StalledWorker(QObject):
    """A worker that never finishes on its own; call `finish()` to emit the result. Lets a
    test observe the in-flight ("busy") state of a dialog."""

    finished_call = Signal(object)
    instances: ClassVar[list[StalledWorker]] = []

    def __init__(self, func, *args, **kwargs) -> None:
        super().__init__()
        self._func = func
        self._args = args
        self._kwargs = kwargs
        StalledWorker.instances.append(self)

    def start(self) -> None:
        pass

    def finish(self) -> None:
        self.finished_call.emit(self._func(*self._args, **self._kwargs))
