from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtCore import QSettings
from PySide6.QtGui import QColor, QImage, QPixmap

from practicum_desktop.screenshots import SOURCE_LAB_VIEW, SOURCE_UPLOAD, ScreenshotStore


@pytest.fixture
def settings(tmp_path: Path) -> QSettings:
    return QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)


def _pixmap(colour=(200, 30, 30)) -> QPixmap:
    pixmap = QPixmap(12, 8)
    pixmap.fill(QColor(*colour))
    return pixmap


def test_store_saves_captures_as_png_and_remembers_them(
    settings: QSettings, tmp_path: Path
) -> None:
    store = ScreenshotStore(settings, tmp_path / "shots")

    assert store.record("lab-1", "s1") is None
    record = store.save_pixmap("lab-1", "s1", _pixmap())

    assert record.path == tmp_path / "shots" / "lab-1" / "s1.png"
    assert record.path.is_file() and record.source == SOURCE_LAB_VIEW
    assert record.captured_at.tzinfo is not None
    assert settings.value("manual_progress/lab-1/s1/screenshot") == str(record.path)
    again = ScreenshotStore(settings, tmp_path / "shots").record("lab-1", "s1")  # reloaded
    assert again is not None and again.path == record.path and again.source == SOURCE_LAB_VIEW
    assert store.records("lab-1", ["s1", "s2"]) == [again]

    replaced = store.save_pixmap("lab-1", "s1", _pixmap((0, 0, 255)))
    assert replaced.path == record.path  # one file per step, replaced in place
    assert QImage(str(replaced.path)).pixelColor(0, 0) == QColor(0, 0, 255)


def test_store_imports_a_students_own_image_as_png(settings: QSettings, tmp_path: Path) -> None:
    store = ScreenshotStore(settings, tmp_path / "shots")
    original = tmp_path / "mine.jpg"
    assert _pixmap((1, 2, 3)).save(str(original), "JPEG")

    record = store.save_file("lab-1", "s2", original)

    assert record.source == SOURCE_UPLOAD
    assert record.path.suffix == ".png" and not QImage(str(record.path)).isNull()
    not_an_image = tmp_path / "notes.txt"
    not_an_image.write_text("hello")
    with pytest.raises(ValueError, match="not an image"):
        store.save_file("lab-1", "s2", not_an_image)
    with pytest.raises(ValueError, match="not a file"):
        store.save_file("lab-1", "s2", tmp_path / "nope.png")
    assert store.record("lab-1", "s2") == record  # a failed upload keeps the previous one


def test_store_forgets_missing_files_and_clears_a_lab(settings: QSettings, tmp_path: Path) -> None:
    store = ScreenshotStore(settings, tmp_path / "shots")
    record = store.save_pixmap("lab-1", "s1", _pixmap())
    store.save_pixmap("lab-1", "s2", _pixmap())

    record.path.unlink()
    assert store.record("lab-1", "s1") is None  # file gone outside the app → no screenshot

    store.remove("lab-1", "s2")
    assert store.record("lab-1", "s2") is None
    assert not (tmp_path / "shots" / "lab-1" / "s2.png").exists()
    assert settings.value("manual_progress/lab-1/s2/screenshot_source") is None

    store.save_pixmap("lab-1", "s1", _pixmap())
    store.clear_lab("lab-1")
    assert not (tmp_path / "shots" / "lab-1").exists()

    with pytest.raises(ValueError, match="nothing to capture"):
        store.save_pixmap("lab-1", "s1", QPixmap())
