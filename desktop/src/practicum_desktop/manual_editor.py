"""Lab instructions editor with a student-view preview (designer-author-manual), shared by
the Quick start screen and the Custom Lab designer.

An instructor writes the manual as numbered *steps*: a title and Markdown details each. A
step becomes one manual section with a single "Done: <title>" task, which is exactly what the
instructions flyout shows students (numbered steps with a checkable task) - see
`quickstart.steps_to_manual`. Manuals that were authored by hand (an imported spec opened
with Edit) may carry several tasks per section or custom section ids; `load_manual` keeps
those on the step so an edit does not flatten them, and regenerates only the task it would
have generated itself ("Done: <old title>").

`ManualPreview` renders the same steps the way the flyout does (markers, Markdown via
`manual.markdown_to_html`, task boxes), so "preview as a student would see it" is the real
rendering, not an approximation.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QScrollArea,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from practicum_desktop import theme
from practicum_desktop.manual import StepMarker, TaskRow, markdown_to_html
from practicum_desktop.quickstart import QuickStartStep, steps_to_manual
from practicum_desktop.widgets import discard, make_button, role_label, style_frame

TITLE_PLACEHOLDER = "Step title, e.g. Install dependencies"
DETAILS_PLACEHOLDER = "What the student does (Markdown; use ``` for commands)"
SCREENSHOT_REQUIRED_TEXT = "Screenshot required: capture the lab view or upload an image."
EMPTY_PREVIEW_TEXT = (
    "No steps yet. Add steps and students will see them here, in the instructions flyout, "
    "once the lab is running."
)


def generated_task_text(title: str) -> str:
    return f"Done: {title}"[:500]


class StepRow(QFrame):
    """One editable instruction step: number, title, details, remove. `section_id` and
    `tasks` are only set for steps loaded from an existing manual that carried more than the
    generated task; they ride along unchanged into the saved manual."""

    changed = Signal()
    removed = Signal(object)

    def __init__(self, number: int, step: QuickStartStep | None = None, parent=None) -> None:
        super().__init__(parent)
        self.section_id: str | None = step.section_id if step else None
        # None = generate the "Done: <title>" task; a list (even empty) = keep as authored.
        self.tasks: list[dict] | None = (
            list(step.tasks) if step is not None and step.tasks is not None else None
        )
        style_frame(self, f"border-bottom: 1px dashed {theme.LINE_SOFT};")
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 6, 0, 8)
        row.setSpacing(8)
        self.number_label = QLabel(str(number))
        self.number_label.setFixedSize(18, 18)
        self.number_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.number_label.setStyleSheet(
            f"background: {theme.LINE_SOFT}; color: {theme.MUTED}; border-radius: 9px;"
            " font-size: 10px;"
        )
        row.addWidget(self.number_label, 0, Qt.AlignmentFlag.AlignTop)
        fields = QVBoxLayout()
        fields.setSpacing(4)
        self.title_field = QLineEdit(step.title if step else "")
        self.title_field.setPlaceholderText(TITLE_PLACEHOLDER)
        self.title_field.setMaxLength(120)
        self.title_field.textChanged.connect(self._on_title_changed)
        fields.addWidget(self.title_field)
        self.details_field = QPlainTextEdit(step.details if step else "")
        self.details_field.setPlaceholderText(DETAILS_PLACEHOLDER)
        self.details_field.setFixedHeight(56)
        self.details_field.textChanged.connect(self.changed.emit)
        fields.addWidget(self.details_field)
        self.screenshot_box = QCheckBox("Ask for a screenshot of this step")
        self.screenshot_box.setToolTip(
            "Students attach a screenshot (captured from the lab view or uploaded) before the "
            "step counts as complete; it is included in their exported results"
        )
        self.screenshot_box.setChecked(bool(step and step.requires_screenshot))
        self.screenshot_box.toggled.connect(self._on_screenshot_toggled)
        fields.addWidget(self.screenshot_box)
        row.addLayout(fields, 1)
        remove = make_button("\u00d7", kind="ghost")
        remove.setToolTip("Remove this step")
        remove.setAccessibleName("Remove this step")
        remove.setStyleSheet("padding: 0 6px; font-size: 15px;")
        remove.clicked.connect(self._on_remove_clicked)
        row.addWidget(remove, 0, Qt.AlignmentFlag.AlignTop)

    def _on_title_changed(self, _text: str) -> None:
        self.changed.emit()

    def _on_screenshot_toggled(self, _checked: bool) -> None:
        self.changed.emit()

    def _on_remove_clicked(self) -> None:
        self.removed.emit(self)

    def set_number(self, number: int) -> None:
        self.number_label.setText(str(number))

    def step(self) -> QuickStartStep:
        return QuickStartStep(
            title=self.title_field.text().strip(),
            details=self.details_field.toPlainText(),
            section_id=self.section_id,
            tasks=list(self.tasks) if self.tasks is not None else None,
            requires_screenshot=self.screenshot_box.isChecked(),
        )


class ManualPreview(QWidget):
    """The steps as the instructions flyout will show them (read-only)."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._host = QWidget()
        self._host.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self._layout = QVBoxLayout(self._host)
        self._layout.setContentsMargins(4, 4, 10, 8)
        self._layout.setSpacing(4)
        self._layout.addStretch(1)
        scroll.setWidget(self._host)
        layout.addWidget(scroll)
        self._widgets: list[QWidget] = []
        self.empty_label = role_label(EMPTY_PREVIEW_TEXT, "muted", wrap=True)
        self._layout.insertWidget(0, self.empty_label)

    def set_steps(self, steps: list[QuickStartStep]) -> None:
        for widget in self._widgets:
            self._layout.removeWidget(widget)
            discard(widget)
        self._widgets = []
        manual = steps_to_manual(steps) or {"sections": []}
        sections = manual["sections"]
        self.empty_label.setVisible(not sections)
        for number, section in enumerate(sections, start=1):
            block = QWidget()
            block_layout = QHBoxLayout(block)
            block_layout.setContentsMargins(0, 4, 0, 6)
            block_layout.setSpacing(8)
            marker = StepMarker(number)
            marker.set_state("active" if number == 1 else "todo")
            block_layout.addWidget(marker, 0, Qt.AlignmentFlag.AlignTop)
            texts = QVBoxLayout()
            texts.setSpacing(2)
            texts.addWidget(role_label(section["title"], "label", wrap=True))
            body = QLabel(markdown_to_html(section["content_markdown"]))
            body.setTextFormat(Qt.TextFormat.RichText)
            body.setWordWrap(True)
            body.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
            body.setStyleSheet("font-size: 12px;")
            texts.addWidget(body)
            for task in section["tasks"]:
                task_row = TaskRow(task["text"], False)
                task_row.checkbox.setEnabled(False)
                texts.addWidget(task_row)
            if section.get("requires_screenshot"):
                texts.addWidget(role_label(SCREENSHOT_REQUIRED_TEXT, "hint"))
            block_layout.addLayout(texts, 1)
            self._layout.insertWidget(self._layout.count() - 1, block)
            self._widgets.append(block)


class ManualStepsEditor(QWidget):
    """The step list with "+ Add step" and an Edit / Preview switch. `changed` fires on any
    edit; `steps()` is what `quickstart.steps_to_manual` turns into the spec's manual."""

    changed = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.rows: list[StepRow] = []
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self.stack = QStackedWidget()
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        host = QWidget()
        self.steps_layout = QVBoxLayout(host)
        self.steps_layout.setContentsMargins(0, 0, 6, 0)
        self.steps_layout.setSpacing(0)
        self.steps_layout.addStretch(1)
        self.scroll.setWidget(host)
        self.stack.addWidget(self.scroll)
        self.preview = ManualPreview()
        self.stack.addWidget(self.preview)
        layout.addWidget(self.stack, 1)

        buttons = QHBoxLayout()
        buttons.setSpacing(8)
        self.add_button = make_button("+ Add step", small=True)
        self.add_button.clicked.connect(self._on_add_clicked)
        buttons.addWidget(self.add_button)
        self.preview_button = make_button("Preview", small=True)
        self.preview_button.setCheckable(True)
        self.preview_button.setToolTip("Show the steps as students will see them")
        self.preview_button.toggled.connect(self._on_preview_toggled)
        buttons.addWidget(self.preview_button)
        buttons.addStretch(1)
        layout.addLayout(buttons)

    # ----- steps -------------------------------------------------------------------------

    def add_step(self, step: QuickStartStep | None = None, focus: bool = True) -> StepRow:
        row = StepRow(len(self.rows) + 1, step)
        row.changed.connect(self._on_row_changed)
        row.removed.connect(self.remove_row)
        self.steps_layout.insertWidget(self.steps_layout.count() - 1, row)
        self.rows.append(row)
        if step is None and focus:
            self.preview_button.setChecked(False)
            row.title_field.setFocus()
        self.changed.emit()
        return row

    def remove_row(self, row: StepRow) -> None:
        if row in self.rows:
            self.rows.remove(row)
        self.steps_layout.removeWidget(row)
        discard(row)
        for number, remaining in enumerate(self.rows, start=1):
            remaining.set_number(number)
        self.changed.emit()

    def clear(self) -> None:
        for row in list(self.rows):
            self.rows.remove(row)
            self.steps_layout.removeWidget(row)
            discard(row)
        self.preview_button.setChecked(False)
        self.changed.emit()

    def set_steps(self, steps: list[QuickStartStep]) -> None:
        self.clear()
        for step in steps:
            self.add_step(step, focus=False)

    def load_manual(self, manual: dict | None) -> None:
        """Fills the editor from a spec's `manual` (one step per section). The task the
        editor would generate itself is dropped so a renamed step regenerates it; anything
        else (several tasks, none at all, custom wording, custom ids) is preserved on the step."""
        steps: list[QuickStartStep] = []
        for section in (manual or {}).get("sections") or []:
            title = str(section.get("title") or "")
            tasks: list[dict] | None = [dict(task) for task in section.get("tasks") or []]
            if len(tasks) == 1 and tasks[0].get("text") == generated_task_text(title):
                tasks = None  # ours: regenerate from the (possibly renamed) title
            steps.append(
                QuickStartStep(
                    title=title,
                    details=str(section.get("content_markdown") or ""),
                    section_id=str(section.get("id") or "") or None,
                    tasks=tasks,
                    requires_screenshot=bool(section.get("requires_screenshot")),
                )
            )
        self.set_steps(steps)

    def steps(self) -> list[QuickStartStep]:
        return [row.step() for row in self.rows]

    def titled_count(self) -> int:
        return sum(1 for row in self.rows if row.step().title)

    def manual(self) -> dict | None:
        return steps_to_manual(self.steps())

    # ----- preview -----------------------------------------------------------------------

    @property
    def previewing(self) -> bool:
        return self.stack.currentWidget() is self.preview

    def _on_preview_toggled(self, checked: bool) -> None:
        if checked:
            self.preview.set_steps(self.steps())
            self.stack.setCurrentWidget(self.preview)
            self.preview_button.setText("Edit")
        else:
            self.stack.setCurrentWidget(self.scroll)
            self.preview_button.setText("Preview")

    def _on_add_clicked(self) -> None:
        self.add_step()

    def _on_row_changed(self) -> None:
        self.changed.emit()
