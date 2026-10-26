"""Lab instructions flyout (manual-view-flyout, manual-track-progress).

A side panel for the running view, laid out like the mockup's `.instructions-flyout`:
a header with "N of M complete" and a close control, one step per manual section (numbered
marker that turns into a green check when all of the section's tasks are done), the
section's markdown, its tasks as checkboxes, and a "Mark step complete" button that ticks
the next open task. Task progress is stored only in QSettings on this computer (D-7) and is
cleared only by this panel's own "Reset progress" - never by a runtime Reset (D-5).
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from pathlib import Path

from PySide6.QtCore import QSettings, Qt, Signal
from PySide6.QtGui import QPixmap, QTextDocument
from PySide6.QtWidgets import (
    QCheckBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from practicum_desktop import icons, theme
from practicum_desktop.api_client import ManualSectionInfo
from practicum_desktop.dialogs import confirm
from practicum_desktop.lab_results import TaskCompletion
from practicum_desktop.screenshots import SOURCE_LAB_VIEW, ScreenshotRecord, ScreenshotStore
from practicum_desktop.widgets import (
    FlowHost,
    MessageBanner,
    copyable_label,
    discard,
    edge_frame,
    make_button,
    role_label,
)

NO_LAB_SELECTED_MESSAGE = "Select a lab to view its manual."
MARKER_SIZE = 20
_PRE_BLOCK = re.compile(r"<pre[^>]*>(.*?)</pre>", re.DOTALL)
_CODE_PARAGRAPH = (
    '<p style="margin:3px 0; padding:4px 6px; background-color:#f3f4f6; '
    "font-family:'Consolas','Courier New',monospace; font-size:11px;\">{body}</p>"
)


def markdown_to_html(markdown: str) -> str:
    """Renders Markdown the way Qt does, but turns code blocks into wrapping monospace
    paragraphs. QLabel never wraps `<pre>` (not even with `white-space:pre-wrap`), which
    forced the narrow flyout to clip whole commands a student has to read."""
    document = QTextDocument()
    document.setMarkdown(markdown)
    html = document.toHtml()
    return _PRE_BLOCK.sub(lambda m: _CODE_PARAGRAPH.format(body=m.group(1)), html)


class StepMarker(QLabel):
    """The round number / check marker in front of each step."""

    def __init__(self, number: int, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._number = number
        self.setFixedSize(MARKER_SIZE, MARKER_SIZE)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.set_state("todo")

    def set_state(self, state: str) -> None:
        """state: done | active | todo"""
        self.state = state
        if state == "done":
            self.setToolTip("Step complete")
            self.setAccessibleName("Step complete")
            if icons.icon_available("success"):
                # The design check: a green circle with a white tick, the marker's own shape.
                self.setStyleSheet("background: transparent;")
                self.setPixmap(icons.pixmap("success", MARKER_SIZE))
                return
            self.setText("\u2713")
            background, colour = theme.GREEN, "white"
        elif state == "active":
            self.setToolTip("Current step")
            self.setAccessibleName(f"Step {self._number}, current")
            self.setText(str(self._number))
            background, colour = theme.INK, "white"
        else:
            self.setToolTip("")
            self.setAccessibleName(f"Step {self._number}")
            self.setText(str(self._number))
            background, colour = theme.LINE_SOFT, theme.MUTED
        self.setStyleSheet(
            f"background: {background}; color: {colour}; border-radius: {MARKER_SIZE // 2}px;"
            " font-size: 11px; font-weight: 700;"
        )


class TaskRow(QWidget):
    """A checkbox with a word-wrapping label (QCheckBox itself cannot wrap)."""

    def __init__(self, text: str, checked: bool, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(8)
        self.checkbox = QCheckBox()
        self.checkbox.setChecked(checked)
        row.addWidget(self.checkbox, 0, Qt.AlignmentFlag.AlignTop)
        self.label = QLabel(text)
        self.label.setWordWrap(True)
        self.label.setStyleSheet("font-size: 12px;")
        self.label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.label.setCursor(Qt.CursorShape.PointingHandCursor)
        row.addWidget(self.label, 1)

    def mousePressEvent(self, event) -> None:
        if self.label.geometry().contains(event.position().toPoint()):
            self.checkbox.toggle()
        super().mousePressEvent(event)


THUMBNAIL_HEIGHT = 90


class ScreenshotRow(QWidget):
    """A step's screenshot evidence: the thumbnail (when attached), Capture lab view /
    Upload image… / Remove, and a one-line status. The flyout owns the store; this only
    shows and asks."""

    capture_requested = Signal(str)  # section id
    upload_requested = Signal(str)
    remove_requested = Signal(str)

    def __init__(self, section_id: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.section_id = section_id
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 4, 0, 0)
        layout.setSpacing(4)
        self.hint_label = role_label("Screenshot required for this step.", "hint", wrap=True)
        self.hint_label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        layout.addWidget(self.hint_label)
        self.thumbnail = QLabel()
        self.thumbnail.setFixedHeight(THUMBNAIL_HEIGHT)
        self.thumbnail.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.thumbnail.setStyleSheet(f"border: 1px solid {theme.LINE}; border-radius: 6px;")
        self.thumbnail.hide()
        layout.addWidget(self.thumbnail)
        self._buttons_host = FlowHost(spacing=6)  # wraps when the flyout is narrow
        buttons = self._buttons_host.flow
        self.capture_button = make_button("Capture lab view", small=True)
        self.capture_button.setToolTip(
            "Take a screenshot of what the lab view shows right now (the embedded desktop or "
            "web page). For terminal work, upload your own screenshot instead."
        )
        self.capture_button.clicked.connect(self._on_capture)
        buttons.addWidget(self.capture_button)
        self.upload_button = make_button("Upload image\u2026", small=True)
        self.upload_button.setToolTip("Attach a screenshot you took yourself (PNG, JPEG, …)")
        self.upload_button.clicked.connect(self._on_upload)
        buttons.addWidget(self.upload_button)
        self.remove_button = make_button("Remove", kind="link", small=True)
        self.remove_button.setToolTip("Detach this screenshot")
        self.remove_button.clicked.connect(self._on_remove)
        self.remove_button.hide()
        buttons.addWidget(self.remove_button)
        layout.addWidget(self._buttons_host)
        self.status_label = role_label("", "hint", wrap=True)
        self.status_label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.status_label.hide()
        layout.addWidget(self.status_label)

    def show_record(self, record: ScreenshotRecord | None) -> None:
        if record is None:
            self.thumbnail.hide()
            self.remove_button.hide()
            self.hint_label.setText("Screenshot required for this step.")
            self.capture_button.setText("Capture lab view")
            self._buttons_host.refit()
            return
        pixmap = QPixmap(str(record.path))
        if not pixmap.isNull():
            self.thumbnail.setPixmap(
                pixmap.scaledToHeight(THUMBNAIL_HEIGHT, Qt.TransformationMode.SmoothTransformation)
            )
            self.thumbnail.show()
        source = "captured from the lab view" if record.source == SOURCE_LAB_VIEW else "uploaded"
        when = record.captured_at.astimezone().strftime("%Y-%m-%d %H:%M")
        self.hint_label.setText(f"Screenshot attached ({source}, {when}).")
        self.thumbnail.setToolTip(str(record.path))
        self.thumbnail.setAccessibleName(f"Screenshot for this step, {source} {when}")
        self.capture_button.setText("Capture again")
        self.remove_button.show()
        self._buttons_host.refit()
        self.set_status("")

    def set_status(self, text: str, error: bool = False) -> None:
        self.status_label.setText(text)
        self.status_label.setProperty("role", "error" if error else "hint")
        theme.restyle(self.status_label)
        self.status_label.setVisible(bool(text))

    def _on_capture(self) -> None:
        self.capture_requested.emit(self.section_id)

    def _on_upload(self) -> None:
        self.upload_requested.emit(self.section_id)

    def _on_remove(self) -> None:
        self.remove_requested.emit(self.section_id)


class ManualFlyout(QWidget):
    """Side panel showing the current lab's manual with locally-tracked task progress."""

    close_requested = Signal()
    progress_changed = Signal(int, int)  # completed, total
    export_requested = Signal()  # the student wants to hand in their results
    screenshot_capture_requested = Signal(str)  # section id: grab the lab view for it
    screenshot_upload_requested = Signal(str)  # section id: pick an image file for it

    def __init__(
        self,
        settings: QSettings,
        parent: QWidget | None = None,
        screenshot_dir: Path | None = None,
    ) -> None:
        super().__init__(parent)
        self._settings = settings
        self._screenshots = ScreenshotStore(settings, screenshot_dir)
        self._screenshot_rows: dict[str, ScreenshotRow] = {}
        self._lab_id: str | None = None
        self._name: str = ""
        self._sections: list[ManualSectionInfo] = []
        # (section, task, checkbox) in document order; drives the progress line and
        # "Mark step complete".
        self._task_boxes: list[tuple[ManualSectionInfo, str, QCheckBox]] = []
        self._markers: list[tuple[ManualSectionInfo, StepMarker]] = []
        self.setObjectName("instructionsFlyout")
        self.setStyleSheet(
            f"QWidget#instructionsFlyout {{ background: {theme.CARD}; "
            f"border-left: 1px solid {theme.LINE}; }}"
        )
        self._build_ui()
        self.show_empty(NO_LAB_SELECTED_MESSAGE)

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        head = QFrame()
        head.setObjectName("panelHead")
        head.setStyleSheet(f"QFrame#panelHead {{ border-bottom: 1px solid {theme.LINE_SOFT}; }}")
        head_row = QHBoxLayout(head)
        head_row.setContentsMargins(16, 12, 12, 12)
        head_row.addWidget(role_label("Lab instructions", "h3"))
        head_row.addStretch(1)
        self.progress_label = role_label("", "hint")
        head_row.addWidget(self.progress_label)
        close_button = make_button("\u00d7", kind="ghost")
        close_button.setToolTip("Hide instructions")
        close_button.setAccessibleName("Hide instructions")
        close_button.setStyleSheet("padding: 0 6px; font-size: 16px;")
        close_button.clicked.connect(self.close_requested.emit)
        head_row.addWidget(close_button)
        layout.addWidget(head)

        self.status_label = copyable_label(NO_LAB_SELECTED_MESSAGE, role="muted")
        self.status_label.setContentsMargins(16, 12, 16, 4)
        layout.addWidget(self.status_label)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._steps_container = QWidget()
        # Let the container be exactly as wide as the viewport: its labels wrap to that width
        # instead of pushing a horizontal scrollbar (or getting clipped).
        self._steps_container.setSizePolicy(
            QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred
        )
        self._steps_layout = QVBoxLayout(self._steps_container)
        self._steps_layout.setContentsMargins(16, 6, 16, 10)
        self._steps_layout.setSpacing(0)
        self._steps_layout.addStretch(1)
        scroll_area.setWidget(self._steps_container)
        layout.addWidget(scroll_area, 1)

        footer = edge_frame("top", theme.LINE_SOFT)
        footer_layout = QVBoxLayout(footer)
        footer_layout.setContentsMargins(16, 12, 16, 12)
        footer_layout.setSpacing(6)
        self.complete_button = make_button(
            "Mark step complete", kind="primary", small=True, icon="success"
        )
        self.complete_button.clicked.connect(self.mark_next_step_complete)
        footer_layout.addWidget(self.complete_button)
        self.done_banner = MessageBanner("ok")
        self.done_banner.hide()
        footer_layout.addWidget(self.done_banner)
        self.export_button = make_button("Export results", small=True)
        self.export_button.setToolTip(
            "Save which steps you completed (and when) to a file you can hand in - as JSON "
            "or a readable report"
        )
        self.export_button.clicked.connect(self.export_requested.emit)
        footer_layout.addWidget(self.export_button)
        self.reset_button = make_button("Reset progress", kind="link", small=True)
        self.reset_button.setToolTip(
            "Clears your checked-off tasks for this lab on this computer only"
        )
        self.reset_button.clicked.connect(self._on_reset_clicked)
        footer_layout.addWidget(self.reset_button, 0, Qt.AlignmentFlag.AlignHCenter)
        layout.addWidget(footer)

    # ----- content ---------------------------------------------------------------------

    def show_lab(self, lab_id: str, name: str, sections: list[ManualSectionInfo]) -> None:
        self._lab_id = lab_id
        self._name = name
        self._sections = sections
        self._clear_steps()

        if not sections:
            self.status_label.setText(
                f"'{name}' has no manual." if name else "This lab has no manual."
            )
            self.status_label.show()
            self._update_progress()
            return

        self.status_label.hide()
        for number, section in enumerate(sections, start=1):
            self._steps_layout.insertWidget(
                self._steps_layout.count() - 1, self._build_step(number, section)
            )
        self._update_progress()

    def show_empty(self, message: str) -> None:
        self._lab_id = None
        self._name = ""
        self._sections = []
        self._clear_steps()
        self.status_label.setText(message)
        self.status_label.show()
        self._update_progress()

    def _build_step(self, number: int, section: ManualSectionInfo) -> QWidget:
        step = edge_frame("bottom", theme.LINE_SOFT)
        row = QHBoxLayout(step)
        row.setContentsMargins(0, 10, 0, 10)
        row.setSpacing(10)

        marker = StepMarker(number)
        row.addWidget(marker, 0, Qt.AlignmentFlag.AlignTop)
        self._markers.append((section, marker))

        body = QVBoxLayout()
        body.setSpacing(4)
        title = QLabel(section.title)
        title.setProperty("role", "label")
        title.setWordWrap(True)
        title.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        body.addWidget(title)

        # QLabel renders the rich text (headings, lists, fenced code) and wraps to the
        # flyout's width without the fixed-height juggling a QTextBrowser would need.
        content = QLabel()
        content.setTextFormat(Qt.TextFormat.RichText)
        content.setText(markdown_to_html(section.content_markdown))
        content.setWordWrap(True)
        # Links stay clickable through the default rich-text interaction flags. Adding
        # TextSelectableByMouse here made Qt 6.12 corrupt the heap when the flyout was torn
        # down after a progress update (reproduced offscreen; see Tigre/06 #15).
        content.setOpenExternalLinks(True)
        content.setStyleSheet(f"color: {theme.MUTED}; font-size: 12px;")
        # Ignored horizontally: a long token (URL, container name) must never widen the
        # panel; the label takes the width it is given and wraps/clips inside it.
        content.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Minimum)
        body.addWidget(content)

        for task in section.tasks:
            # QCheckBox never wraps its text, so the box is bare and a wrapping label sits
            # beside it (clicking the label toggles the box too).
            task_row = TaskRow(task.text, self._load_task_state(section.id, task.id))
            checkbox = task_row.checkbox
            # A bound method, not a lambda capturing `self`: PySide keeps bound-method
            # connections weak, so the flyout and its checkboxes form no reference cycle
            # (a cycle here was torn down in the wrong order and corrupted the heap).
            checkbox.setProperty("task_key", (section.id, task.id))
            checkbox.toggled.connect(self._on_checkbox_toggled)
            body.addWidget(task_row)
            self._task_boxes.append((section, task.id, checkbox))
        if section.requires_screenshot:
            shot_row = ScreenshotRow(section.id)
            shot_row.capture_requested.connect(self.screenshot_capture_requested.emit)
            shot_row.upload_requested.connect(self.screenshot_upload_requested.emit)
            shot_row.remove_requested.connect(self.remove_screenshot)
            if self._lab_id is not None:
                shot_row.show_record(self._screenshots.record(self._lab_id, section.id))
            body.addWidget(shot_row)
            self._screenshot_rows[section.id] = shot_row
        row.addLayout(body, 1)
        return step

    def _clear_steps(self) -> None:
        self._task_boxes = []
        self._markers = []
        self._screenshot_rows = {}
        while self._steps_layout.count() > 1:
            item = self._steps_layout.takeAt(0)
            discard(item.widget())

    # ----- progress ----------------------------------------------------------------------

    def task_progress(self) -> tuple[int, int]:
        """(ticked tasks, tasks)."""
        total = len(self._task_boxes)
        completed = sum(1 for _section, _task, box in self._task_boxes if box.isChecked())
        return completed, total

    def screenshot_progress(self) -> tuple[int, int]:
        """(attached screenshots, screenshots the instructor asked for)."""
        required = list(self._screenshot_rows)
        if self._lab_id is None:
            return 0, len(required)
        attached = sum(
            1 for section_id in required if self._screenshots.record(self._lab_id, section_id)
        )
        return attached, len(required)

    def progress(self) -> tuple[int, int]:
        """(completed, total) items for the current lab: tasks plus requested screenshots."""
        tasks_done, tasks = self.task_progress()
        shots_done, shots = self.screenshot_progress()
        return tasks_done + shots_done, tasks + shots

    def _update_progress(self) -> None:
        completed, total = self.progress()
        tasks_done, tasks = self.task_progress()
        shots_done, shots = self.screenshot_progress()
        self.progress_label.setText(f"{completed} of {total} complete" if total else "")
        self.complete_button.setEnabled(tasks_done < tasks)
        self.reset_button.setEnabled(self._lab_id is not None and total > 0)
        self.export_button.setEnabled(self._lab_id is not None and total > 0)
        if total > 0 and completed == total:
            self.done_banner.set_message(
                "All steps complete. Export your results to hand them in.", "ok"
            )
        elif tasks and tasks_done == tasks and shots_done < shots:
            missing = shots - shots_done
            self.done_banner.set_message(
                f"Every task is ticked; attach the {missing} requested screenshot"
                f"{'s' if missing != 1 else ''} to finish.",
                "warn",
            )
        else:
            self.done_banner.hide()

        active_assigned = False
        for section, marker in self._markers:
            boxes = [box for sec, _task, box in self._task_boxes if sec.id == section.id]
            shot_ok = not section.requires_screenshot or (
                self._lab_id is not None
                and self._screenshots.record(self._lab_id, section.id) is not None
            )
            has_items = bool(boxes) or section.requires_screenshot
            if has_items and all(b.isChecked() for b in boxes) and shot_ok:
                marker.set_state("done")
            elif not active_assigned:
                marker.set_state("active")
                active_assigned = True
            else:
                marker.set_state("todo")
        self.progress_changed.emit(completed, total)

    # ----- screenshots -----------------------------------------------------------------

    def screenshots(self) -> list[ScreenshotRecord]:
        if self._lab_id is None:
            return []
        return self._screenshots.records(self._lab_id, list(self._screenshot_rows))

    def attach_screenshot(
        self, section_id: str, pixmap: QPixmap, source: str = SOURCE_LAB_VIEW
    ) -> bool:
        """Stores a captured image for the step; False (with the reason shown) when it fails."""
        row = self._screenshot_rows.get(section_id)
        if row is None or self._lab_id is None:
            return False
        try:
            record = self._screenshots.save_pixmap(self._lab_id, section_id, pixmap, source)
        except (ValueError, OSError) as exc:
            row.set_status(str(exc), error=True)
            return False
        row.show_record(record)
        self._update_progress()
        return True

    def attach_screenshot_file(self, section_id: str, path: Path) -> bool:
        row = self._screenshot_rows.get(section_id)
        if row is None or self._lab_id is None:
            return False
        try:
            record = self._screenshots.save_file(self._lab_id, section_id, path)
        except (ValueError, OSError) as exc:
            row.set_status(str(exc), error=True)
            return False
        row.show_record(record)
        self._update_progress()
        return True

    def show_screenshot_problem(self, section_id: str, text: str) -> None:
        row = self._screenshot_rows.get(section_id)
        if row is not None:
            row.set_status(text, error=True)

    def remove_screenshot(self, section_id: str) -> None:
        if self._lab_id is None:
            return
        self._screenshots.remove(self._lab_id, section_id)
        row = self._screenshot_rows.get(section_id)
        if row is not None:
            row.show_record(None)
        self._update_progress()

    def mark_next_step_complete(self) -> None:
        """Ticks the first task that is still open (the mockup's footer button)."""
        for _section, _task, box in self._task_boxes:
            if not box.isChecked():
                box.setChecked(True)
                return

    def _on_checkbox_toggled(self, checked: bool) -> None:
        sender = self.sender()
        key = sender.property("task_key") if sender is not None else None
        if not key:
            return
        section_id, task_id = key
        self._on_task_toggled(section_id, task_id, checked)

    def _on_task_toggled(self, section_id: str, task_id: str, checked: bool) -> None:
        self._save_task_state(section_id, task_id, checked)
        self._update_progress()

    def _progress_key(self, section_id: str, task_id: str) -> str:
        return f"manual_progress/{self._lab_id}/{section_id}/{task_id}"

    def _completed_at_key(self, section_id: str, task_id: str) -> str:
        return f"manual_progress/{self._lab_id}/{section_id}/{task_id}_completed_at"

    def _load_task_state(self, section_id: str, task_id: str) -> bool:
        value = self._settings.value(self._progress_key(section_id, task_id), False)
        return value in (True, "true", "1", 1)

    def _load_completed_at(self, section_id: str, task_id: str) -> datetime | None:
        value = self._settings.value(self._completed_at_key(section_id, task_id), "")
        try:
            return datetime.fromisoformat(str(value)) if value else None
        except ValueError:
            return None

    def _save_task_state(self, section_id: str, task_id: str, checked: bool) -> None:
        if self._lab_id is None:
            return
        self._settings.setValue(self._progress_key(section_id, task_id), checked)
        # When it was ticked - kept for the results export; cleared when unticked.
        if checked:
            self._settings.setValue(
                self._completed_at_key(section_id, task_id),
                datetime.now(UTC).isoformat(timespec="seconds"),
            )
        else:
            self._settings.remove(self._completed_at_key(section_id, task_id))

    def task_completions(self) -> list[TaskCompletion]:
        """Every task of the current lab with its state and completion time - the input of
        the results export."""
        return [
            TaskCompletion(
                section_id=section.id,
                task_id=task_id,
                completed=box.isChecked(),
                completed_at=self._load_completed_at(section.id, task_id)
                if box.isChecked()
                else None,
            )
            for section, task_id, box in self._task_boxes
        ]

    @property
    def sections(self) -> list[ManualSectionInfo]:
        return list(self._sections)

    def _on_reset_clicked(self) -> None:
        if self._lab_id is None:
            return
        if not confirm(
            self,
            title="Reset progress?",
            message=(
                f'This clears your checked-off tasks for "{self._name}". It does not '
                "affect the lab's containers or the instructor's content, and cannot be "
                "undone."
            ),
            confirm_label="Reset Progress",
            destructive=True,
        ):
            return
        self._settings.remove(f"manual_progress/{self._lab_id}")
        self._screenshots.clear_lab(self._lab_id)
        self.show_lab(self._lab_id, self._name, self._sections)
