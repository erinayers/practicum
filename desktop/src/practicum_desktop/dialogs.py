from __future__ import annotations

from PySide6.QtWidgets import QDialog, QDialogButtonBox, QLabel, QVBoxLayout, QWidget

DESTRUCTIVE_BUTTON_STYLE = "background-color: #dc2626; color: white; font-weight: 600;"


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
