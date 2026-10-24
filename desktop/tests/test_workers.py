from __future__ import annotations

import gc
import threading
import time

from PySide6.QtCore import QCoreApplication, QEventLoop, QTimer

from practicum_desktop.workers import CallableWorker, ManagedThread


def _spin(app, ms: int) -> None:
    loop = QEventLoop()
    QTimer.singleShot(ms, loop.quit)
    loop.exec()


def _spin_until(app, condition, timeout_ms: int = 3000) -> None:
    """Queued signal delivery can lag behind deferred deletions of big widget trees from
    earlier tests, so wait for the condition rather than a fixed interval."""
    waited = 0
    while not condition() and waited < timeout_ms:
        _spin(app, 50)
        waited += 50


def test_running_worker_survives_losing_its_last_reference(qapp: QCoreApplication) -> None:
    """The Tigre/06 #6 crash: `self._worker = CallableWorker(...)` replacing a running worker
    used to garbage-collect it → "QThread: Destroyed while thread is still running" → abort.
    ManagedThread keeps every running worker alive until it finishes."""
    gate = threading.Event()
    results: list[str] = []

    def slow() -> str:
        gate.wait(5)
        return "done"

    worker = CallableWorker(slow)
    worker.finished_call.connect(results.append)
    worker.start()
    assert ManagedThread.active_count() >= 1

    worker = None  # the only Python reference is gone while the thread still runs
    gc.collect()
    time.sleep(0.05)
    gate.set()
    _spin_until(qapp, lambda: results == ["done"] and ManagedThread.active_count() == 0)

    assert results == ["done"]
    assert ManagedThread.active_count() == 0


def test_wait_for_all_blocks_until_workers_finish(qapp: QCoreApplication) -> None:
    worker = CallableWorker(lambda: time.sleep(0.1) or "ok")
    worker.start()

    assert ManagedThread.wait_for_all(2000) is True
    _spin_until(qapp, lambda: ManagedThread.active_count() == 0)
    assert ManagedThread.active_count() == 0


def test_callable_worker_passes_args_and_kwargs(qapp: QCoreApplication) -> None:
    results: list[object] = []
    worker = CallableWorker(lambda a, b=0: a + b, 2, b=3)
    worker.finished_call.connect(results.append)
    worker.start()
    worker.wait(2000)
    _spin_until(qapp, lambda: results == [5])

    assert results == [5]
