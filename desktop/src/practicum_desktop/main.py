from __future__ import annotations

import sys

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from practicum_desktop.main_window import MainWindow
from practicum_desktop.theme import apply_theme


def main() -> None:
    # Required by QtWebEngine (the embedded lab view) before the application is created.
    QApplication.setAttribute(Qt.ApplicationAttribute.AA_ShareOpenGLContexts)
    app = QApplication(sys.argv)
    app.setApplicationName("Practicum")
    app.setOrganizationName("Practicum")
    apply_theme(app)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
