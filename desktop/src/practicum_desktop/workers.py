from __future__ import annotations

from typing import Any, Callable

from PySide6.QtCore import QThread, Signal


class CallableWorker(QThread):
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
