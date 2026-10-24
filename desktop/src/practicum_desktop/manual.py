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

from PySide6.QtCore import QSettings, Qt, Signal
from PySide6.QtGui import QTextDocument
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

from practicum_desktop import theme
from practicum_desktop.api_client import ManualSectionInfo
from practicum_desktop.dialogs import confirm
from practicum_desktop.widgets import (
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
            self.setText("\u2713")
            background, colour = theme.GREEN, "white"
        elif state == "active":
            self.setText(str(self._number))
            background, colour = theme.INK, "white"
        else:
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


class ManualFlyout(QWidget):
    """Side panel showing the current lab's manual with locally-tracked task progress."""

    close_requested = Signal()
    progress_changed = Signal(int, int)  # completed, total

    def __init__(self, settings: QSettings, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._settings = settings
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
        self.complete_button = make_button("\u2713 Mark step complete", kind="primary", small=True)
        self.complete_button.clicked.connect(self.mark_next_step_complete)
        footer_layout.addWidget(self.complete_button)
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
        row.addLayout(body, 1)
        return step

    def _clear_steps(self) -> None:
        self._task_boxes = []
        self._markers = []
        while self._steps_layout.count() > 1:
            item = self._steps_layout.takeAt(0)
            discard(item.widget())

    # ----- progress ----------------------------------------------------------------------

    def progress(self) -> tuple[int, int]:
        """(completed tasks, total tasks) for the current lab."""
        total = len(self._task_boxes)
        completed = sum(1 for _section, _task, box in self._task_boxes if box.isChecked())
        return completed, total

    def _update_progress(self) -> None:
        completed, total = self.progress()
        self.progress_label.setText(f"{completed} of {total} complete" if total else "")
        self.complete_button.setEnabled(completed < total)
        self.reset_button.setEnabled(self._lab_id is not None and total > 0)

        active_assigned = False
        for section, marker in self._markers:
            boxes = [box for sec, _task, box in self._task_boxes if sec.id == section.id]
            if boxes and all(box.isChecked() for box in boxes):
                marker.set_state("done")
            elif not active_assigned:
                marker.set_state("active")
                active_assigned = True
            else:
                marker.set_state("todo")
        self.progress_changed.emit(completed, total)

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

    def _load_task_state(self, section_id: str, task_id: str) -> bool:
        value = self._settings.value(self._progress_key(section_id, task_id), False)
        return value in (True, "true", "1", 1)

    def _save_task_state(self, section_id: str, task_id: str, checked: bool) -> None:
        if self._lab_id is None:
            return
        self._settings.setValue(self._progress_key(section_id, task_id), checked)

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
        self.show_lab(self._lab_id, self._name, self._sections)
