from __future__ import annotations

from PySide6.QtWidgets import QDialog, QLabel

from practicum_desktop import dialogs
from practicum_desktop.dialogs import DESTRUCTIVE_BUTTON_STYLE, ConfirmDialog, confirm


def test_dialog_shows_title_and_message() -> None:
    dialog = ConfirmDialog(None, title="Delete this lab?", message="This cannot be undone.")

    assert dialog.windowTitle() == "Delete this lab?"
    assert dialog.confirm_button.text() == "Confirm"
    assert dialog.cancel_button.text() == "Cancel"


def test_dialog_uses_custom_button_labels() -> None:
    dialog = ConfirmDialog(
        None,
        title="t",
        message="m",
        confirm_label="Delete",
        cancel_label="Keep it",
    )

    assert dialog.confirm_button.text() == "Delete"
    assert dialog.cancel_button.text() == "Keep it"


def test_destructive_dialog_styles_confirm_button_distinctly() -> None:
    destructive_dialog = ConfirmDialog(None, title="t", message="m", destructive=True)
    routine_dialog = ConfirmDialog(None, title="t", message="m", destructive=False)

    assert destructive_dialog.confirm_button.styleSheet() == DESTRUCTIVE_BUTTON_STYLE
    assert routine_dialog.confirm_button.styleSheet() != DESTRUCTIVE_BUTTON_STYLE


def test_accepting_sets_accepted_result() -> None:
    dialog = ConfirmDialog(None, title="t", message="m")

    dialog.accept()

    assert dialog.result() == QDialog.DialogCode.Accepted


def test_canceling_sets_rejected_result() -> None:
    dialog = ConfirmDialog(None, title="t", message="m")

    dialog.reject()

    assert dialog.result() == QDialog.DialogCode.Rejected


def test_confirm_returns_true_when_user_confirms(monkeypatch) -> None:
    class FakeDialog:
        def __init__(self, *args, **kwargs) -> None:
            pass

        def exec(self) -> QDialog.DialogCode:
            return QDialog.DialogCode.Accepted

    monkeypatch.setattr(dialogs, "ConfirmDialog", FakeDialog)

    assert confirm(None, title="t", message="m") is True


def test_confirm_returns_false_when_user_cancels(monkeypatch) -> None:
    class FakeDialog:
        def __init__(self, *args, **kwargs) -> None:
            pass

        def exec(self) -> QDialog.DialogCode:
            return QDialog.DialogCode.Rejected

    monkeypatch.setattr(dialogs, "ConfirmDialog", FakeDialog)

    assert confirm(None, title="t", message="m") is False


def test_results_export_dialog_collects_the_student_name() -> None:
    from practicum_desktop.dialogs import ResultsExportDialog

    dialog = ResultsExportDialog(None, "Static Routing", 3, 3, student_name="Ada")

    assert dialog.windowTitle() == "Export lab results"
    assert dialog.name_field.text() == "Ada"
    assert dialog.name_field.accessibleName() == "Your name"
    labels = [w.text() for w in dialog.findChildren(QLabel)]
    assert any("3 of 3 tasks complete" in t and "all steps done" in t for t in labels)
    assert any("JSON" in t and "Markdown" in t for t in labels)

    dialog.name_field.setText("  Ada Lovelace ")
    assert dialog.student_name == "Ada Lovelace"
    assert dialog.export_button.text() == "Choose file\u2026"

    partial = ResultsExportDialog(None, "Static Routing", 1, 3)
    texts = [w.text() for w in partial.findChildren(QLabel)]
    assert any("1 of 3 tasks complete." in t for t in texts)
