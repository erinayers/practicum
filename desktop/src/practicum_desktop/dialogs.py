from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QLineEdit,
    QVBoxLayout,
    QWidget,
)

DESTRUCTIVE_BUTTON_STYLE = "background-color: #dc2626; color: white; font-weight: 600;"

COPYABLE_TEXT_FLAGS = (
    Qt.TextInteractionFlag.TextSelectableByMouse | Qt.TextInteractionFlag.TextSelectableByKeyboard
)


class ConfirmDialog(QDialog):
    """A styled, reusable confirmation dialog for destructive or otherwise consequential
    actions.

    This exists so the app never falls back to a native OS/Qt message box for
    confirmations, which would break the illusion of a self-contained application (see
    windows-desktop-in-app-dialogs.md). Prefer the module-level `confirm(...)` helper
    over constructing this directly.
    """

    def __init__(
        self,
        parent: QWidget | None,
        title: str,
        message: str,
        confirm_label: str = "Confirm",
        cancel_label: str = "Cancel",
        destructive: bool = False,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setModal(True)

        layout = QVBoxLayout(self)

        message_label = QLabel(message)
        message_label.setWordWrap(True)
        layout.addWidget(message_label)

        button_box = QDialogButtonBox()
        self.cancel_button = button_box.addButton(
            cancel_label, QDialogButtonBox.ButtonRole.RejectRole
        )
        self.confirm_button = button_box.addButton(
            confirm_label, QDialogButtonBox.ButtonRole.AcceptRole
        )
        if destructive:
            self.confirm_button.setStyleSheet(DESTRUCTIVE_BUTTON_STYLE)

        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)


def confirm(
    parent: QWidget | None,
    title: str,
    message: str,
    confirm_label: str = "Confirm",
    cancel_label: str = "Cancel",
    destructive: bool = False,
) -> bool:
    """Shows an in-app confirmation dialog and blocks until the user responds.

    Returns True only if the user selected the confirm action. This is the only
    sanctioned way to ask for confirmation anywhere in the desktop app.
    """
    dialog = ConfirmDialog(
        parent,
        title=title,
        message=message,
        confirm_label=confirm_label,
        cancel_label=cancel_label,
        destructive=destructive,
    )
    return dialog.exec() == QDialog.DialogCode.Accepted


class ResultsExportDialog(QDialog):
    """Asks for the student's name before the results file is written, and shows what will
    be exported ("3 of 3 tasks complete"). In-app, like every other dialog; only the save
    picker that follows is native (D-39)."""

    def __init__(
        self,
        parent: QWidget | None,
        lab_name: str,
        completed: int,
        total: int,
        student_name: str = "",
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Export lab results")
        self.setModal(True)
        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        intro = QLabel(
            f'Save your progress on "{lab_name}" to a file you can hand in: every step and '
            "task, whether you completed it and when."
        )
        intro.setWordWrap(True)
        layout.addWidget(intro)
        summary = QLabel(
            f"{completed} of {total} tasks complete"
            + (" \u2014 all steps done." if total and completed == total else ".")
        )
        summary.setStyleSheet("font-weight: 600;")
        layout.addWidget(summary)
        name_label = QLabel("Your name (written into the file)")
        layout.addWidget(name_label)
        self.name_field = QLineEdit(student_name)
        self.name_field.setPlaceholderText("e.g. Ada Lovelace")
        self.name_field.setMaxLength(120)
        self.name_field.setAccessibleName("Your name")
        layout.addWidget(self.name_field)
        hint = QLabel("Choose JSON for an instructor's tooling or a Markdown report to read.")
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #6b7280; font-size: 12px;")
        layout.addWidget(hint)
        buttons = QDialogButtonBox()
        self.cancel_button = buttons.addButton("Cancel", QDialogButtonBox.ButtonRole.RejectRole)
        self.export_button = buttons.addButton(
            "Choose file\u2026", QDialogButtonBox.ButtonRole.AcceptRole
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.name_field.setFocus()

    @property
    def student_name(self) -> str:
        return self.name_field.text().strip()
