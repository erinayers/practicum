from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QDockWidget,
    QGroupBox,
    QLabel,
    QPushButton,
    QScrollArea,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from practicum_desktop.api_client import ManualSectionInfo
from practicum_desktop.dialogs import confirm

NO_LAB_SELECTED_MESSAGE = "Select a lab to view its manual."


class ManualFlyout(QDockWidget):
    """A dockable panel showing the current lab's manual, with locally-tracked task progress."""

    def __init__(self, settings, parent=None) -> None:
        super().__init__("Lab Manual", parent)
        self._settings = settings
        self._lab_id: str | None = None
        self._name: str = ""
        self._sections: list[ManualSectionInfo] = []

        self.setAllowedAreas(
            Qt.DockWidgetArea.RightDockWidgetArea | Qt.DockWidgetArea.LeftDockWidgetArea
        )
        self._build_ui()
        self.hide()

    def _build_ui(self) -> None:
        container = QWidget()
        layout = QVBoxLayout(container)

        self.status_label = QLabel(NO_LAB_SELECTED_MESSAGE)
        self.status_label.setWordWrap(True)
        self.status_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse | Qt.TextInteractionFlag.TextSelectableByKeyboard
        )
        layout.addWidget(self.status_label)

        self.reset_button = QPushButton("Reset Progress")
        self.reset_button.setEnabled(False)
        self.reset_button.clicked.connect(self._on_reset_clicked)
        layout.addWidget(self.reset_button)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        self._sections_container = QWidget()
        self._sections_layout = QVBoxLayout(self._sections_container)
        self._sections_layout.addStretch(1)
        scroll_area.setWidget(self._sections_container)
        layout.addWidget(scroll_area)

        self.setWidget(container)

    def show_lab(self, lab_id: str, name: str, sections: list[ManualSectionInfo]) -> None:
        self._lab_id = lab_id
        self._name = name
        self._sections = sections
        self._clear_sections()

        if not sections:
            self.status_label.setText(f"'{name}' has no manual." if name else "This lab has no manual.")
            self.reset_button.setEnabled(False)
            return

        self.status_label.setText(name)
        self.reset_button.setEnabled(True)
        for section in sections:
            group = QGroupBox(section.title)
            group_layout = QVBoxLayout(group)

            content = QTextBrowser()
            content.setOpenExternalLinks(True)
            content.setMarkdown(section.content_markdown)
            group_layout.addWidget(content)

            for task in section.tasks:
                checkbox = QCheckBox(task.text)
                checkbox.setChecked(self._load_task_state(section.id, task.id))
                checkbox.toggled.connect(
                    lambda checked, section_id=section.id, task_id=task.id: self._save_task_state(
                        section_id, task_id, checked
                    )
                )
                group_layout.addWidget(checkbox)

            self._sections_layout.insertWidget(self._sections_layout.count() - 1, group)

    def show_empty(self, message: str) -> None:
        self._lab_id = None
        self._name = ""
        self._sections = []
        self._clear_sections()
        self.status_label.setText(message)
        self.reset_button.setEnabled(False)

    def _clear_sections(self) -> None:
        while self._sections_layout.count() > 1:
            item = self._sections_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

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
