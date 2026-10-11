from __future__ import annotations

import pytest
from PySide6.QtWidgets import QApplication


@pytest.fixture(scope="session", autouse=True)
def qapp() -> QApplication:
    """Ensures a QApplication exists for the test session.

    PySide6 requires a QApplication instance before constructing any QWidget (e.g. the
    ConfirmDialog tested in test_dialogs.py). Session-scoped and autouse so individual
    test files don't need to request it explicitly.
    """
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app
