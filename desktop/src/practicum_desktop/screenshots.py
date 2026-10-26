"""Student screenshots attached to manual steps (manual-track-progress: "request a
screenshot" / "take a screenshot from the embedded window or upload their own").

A step whose section has `requires_screenshot` shows capture / upload controls in the
instructions flyout. The image is stored as a PNG under the app's data folder
(`<AppDataLocation>/screenshots/<lab id>/<section id>.png` - one per step, replaced on
re-capture) and referenced from the same local progress store as the ticks
(`manual_progress/<lab>/<section>/screenshot*` in QSettings), so it is per student, per
computer, never part of the instructor's spec, and rides along into the exported results.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from PySide6.QtCore import QSettings, QStandardPaths
from PySide6.QtGui import QImage, QPixmap

SOURCE_LAB_VIEW = "lab_view"  # captured from the embedded lab view
SOURCE_UPLOAD = "upload"  # a file the student chose
IMAGE_FILTER = "Images (*.png *.jpg *.jpeg *.bmp *.gif *.webp);;All files (*)"
MAX_IMAGE_BYTES = 25 * 1024 * 1024


@dataclass(frozen=True)
class ScreenshotRecord:
    section_id: str
    path: Path
    captured_at: datetime
    source: str  # SOURCE_LAB_VIEW | SOURCE_UPLOAD


def default_screenshot_dir() -> Path:
    base = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppDataLocation)
    return Path(base or Path.home() / ".practicum") / "screenshots"


class ScreenshotStore:
    """Files on disk + their bookkeeping in QSettings, keyed like the task ticks."""

    def __init__(self, settings: QSettings, base_dir: Path | None = None) -> None:
        self._settings = settings
        self.base_dir = base_dir or default_screenshot_dir()

    # ----- keys / paths ------------------------------------------------------------------

    @staticmethod
    def _key(lab_id: str, section_id: str, suffix: str = "") -> str:
        return f"manual_progress/{lab_id}/{section_id}/screenshot{suffix}"

    def path_for(self, lab_id: str, section_id: str) -> Path:
        return self.base_dir / lab_id / f"{section_id}.png"

    # ----- read ----------------------------------------------------------------------------

    def record(self, lab_id: str, section_id: str) -> ScreenshotRecord | None:
        """The step's screenshot, or None when there is none (or its file is gone)."""
        stored = str(self._settings.value(self._key(lab_id, section_id), "") or "")
        if not stored:
            return None
        path = Path(stored)
        if not path.is_file():
            return None
        raw_at = str(self._settings.value(self._key(lab_id, section_id, "_at"), "") or "")
        try:
            captured_at = datetime.fromisoformat(raw_at) if raw_at else datetime.now(UTC)
        except ValueError:
            captured_at = datetime.now(UTC)
        source = str(
            self._settings.value(self._key(lab_id, section_id, "_source"), SOURCE_UPLOAD) or ""
        )
        return ScreenshotRecord(section_id, path, captured_at, source)

    def records(self, lab_id: str, section_ids: list[str]) -> list[ScreenshotRecord]:
        found = (self.record(lab_id, section_id) for section_id in section_ids)
        return [record for record in found if record is not None]

    # ----- write ---------------------------------------------------------------------------

    def save_pixmap(
        self, lab_id: str, section_id: str, pixmap: QPixmap, source: str = SOURCE_LAB_VIEW
    ) -> ScreenshotRecord:
        if pixmap.isNull():
            raise ValueError("There is nothing to capture yet.")
        path = self.path_for(lab_id, section_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        if not pixmap.save(str(path), "PNG"):
            raise OSError(f"Could not write {path}")
        return self._remember(lab_id, section_id, path, source)

    def save_file(self, lab_id: str, section_id: str, image_path: Path) -> ScreenshotRecord:
        """Copies the student's own image in (re-encoded as PNG so every screenshot is the
        same kind of file), after checking it really is an image of a sane size."""
        if not image_path.is_file():
            raise ValueError(f"{image_path} is not a file.")
        if image_path.stat().st_size > MAX_IMAGE_BYTES:
            raise ValueError("That image is larger than 25 MB; please use a smaller one.")
        image = QImage(str(image_path))
        if image.isNull():
            raise ValueError(f"{image_path.name} is not an image Practicum can read.")
        path = self.path_for(lab_id, section_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        if not image.save(str(path), "PNG"):
            raise OSError(f"Could not write {path}")
        return self._remember(lab_id, section_id, path, SOURCE_UPLOAD)

    def _remember(self, lab_id: str, section_id: str, path: Path, source: str) -> ScreenshotRecord:
        captured_at = datetime.now(UTC).replace(microsecond=0)  # stored at second precision
        self._settings.setValue(self._key(lab_id, section_id), str(path))
        self._settings.setValue(
            self._key(lab_id, section_id, "_at"), captured_at.isoformat(timespec="seconds")
        )
        self._settings.setValue(self._key(lab_id, section_id, "_source"), source)
        return ScreenshotRecord(section_id, path, captured_at, source)

    def remove(self, lab_id: str, section_id: str) -> None:
        record = self.record(lab_id, section_id)
        for suffix in ("", "_at", "_source"):
            self._settings.remove(self._key(lab_id, section_id, suffix))
        if record is not None:
            record.path.unlink(missing_ok=True)

    def clear_lab(self, lab_id: str) -> None:
        """Deletes every screenshot file of the lab (the settings keys go with the progress)."""
        folder = self.base_dir / lab_id
        if folder.is_dir():
            for file in folder.glob("*.png"):
                file.unlink(missing_ok=True)
            try:
                folder.rmdir()
            except OSError:
                pass
