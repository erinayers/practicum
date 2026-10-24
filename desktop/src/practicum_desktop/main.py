from __future__ import annotations

import sys
import threading
import time
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication, QMessageBox

from practicum_desktop.main_window import MainWindow
from practicum_desktop.theme import apply_theme


def _start_embedded_api() -> tuple[uvicorn.Server, threading.Thread]:
    """Run the local API alongside the desktop UI in packaged builds."""
    import uvicorn

    from practicum.main import app as api_app

    # A windowed PyInstaller app has no stdout/stderr streams; Uvicorn's default
    # formatter probes stderr.isatty(), which fails when stderr is None.
    config = uvicorn.Config(
        api_app, host="127.0.0.1", port=8000, log_level="warning", log_config=None
    )
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, name="practicum-api", daemon=True)
    thread.start()
    deadline = time.monotonic() + 15
    while not server.started and thread.is_alive() and time.monotonic() < deadline:
        time.sleep(0.05)
    if not server.started:
        server.should_exit = True
        thread.join(timeout=2)
        raise RuntimeError("The Practicum API could not start on 127.0.0.1:8000.")
    return server, thread


def _app_icon_path() -> Path:
    if getattr(sys, "frozen", False):
        base = Path(sys._MEIPASS)
    else:
        base = Path(__file__).resolve().parents[3]
    return base / "assets" / "practicum.ico"


def main() -> None:
    # Required by QtWebEngine (the embedded lab view) before the application is created.
    QApplication.setAttribute(Qt.ApplicationAttribute.AA_ShareOpenGLContexts)
    app = QApplication(sys.argv)
    app.setApplicationName("Practicum")
    app.setOrganizationName("Practicum")
    app.setWindowIcon(QIcon(str(_app_icon_path())))

    embedded_api = None
    # The packaged executable is self-contained. Source/dev launches keep using the
    # repository's start-practicum.bat workflow, which manages the API separately.
    if getattr(sys, "frozen", False):
        try:
            embedded_api = _start_embedded_api()
        except RuntimeError as exc:
            QMessageBox.critical(None, "Practicum could not start", str(exc))
            return

    apply_theme(app)
    window = MainWindow()
    window.show()
    exit_code = app.exec()
    if embedded_api:
        server, thread = embedded_api
        server.should_exit = True
        thread.join(timeout=10)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
