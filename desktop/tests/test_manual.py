from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QLabel, QPushButton, QSizePolicy

from practicum_desktop import manual
from practicum_desktop.api_client import ManualSectionInfo, ManualTaskInfo
from practicum_desktop.manual import NO_LAB_SELECTED_MESSAGE, ManualFlyout, TaskRow

SECTIONS = [
    ManualSectionInfo(
        "s1", "Install dependencies", "Run `pip install`.", [ManualTaskInfo("t1", "Installed")]
    ),
    ManualSectionInfo(
        "s2",
        "Create your endpoints",
        "Add GET /health.",
        [ManualTaskInfo("t2", "Health added"), ManualTaskInfo("t3", "Hello added")],
    ),
    ManualSectionInfo("s3", "Read me", "A section without tasks.", []),
]


@pytest.fixture
def settings(tmp_path: Path) -> QSettings:
    return QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)


def test_empty_state_and_no_manual(settings: QSettings) -> None:
    flyout = ManualFlyout(settings)

    assert flyout.status_label.text() == NO_LAB_SELECTED_MESSAGE
    assert flyout.progress_label.text() == ""
    assert not flyout.complete_button.isEnabled()

    flyout.show_lab("lab-1", "Empty", [])
    assert flyout.status_label.text() == "'Empty' has no manual."
    assert not flyout.reset_button.isEnabled()


def test_steps_markers_and_progress_line(settings: QSettings) -> None:
    flyout = ManualFlyout(settings)
    flyout.show_lab("lab-1", "API lab", SECTIONS)

    assert flyout.progress_label.text() == "0 of 3 complete"
    assert [marker.state for _s, marker in flyout._markers] == ["active", "todo", "todo"]

    flyout.mark_next_step_complete()  # ticks t1 → section 1 done, section 2 active

    assert flyout.progress() == (1, 3)
    assert flyout.progress_label.text() == "1 of 3 complete"
    assert [marker.state for _s, marker in flyout._markers] == ["done", "active", "todo"]
    assert settings.value("manual_progress/lab-1/s1/t1") in (True, "true")

    flyout.mark_next_step_complete()
    flyout.mark_next_step_complete()

    assert flyout.progress() == (3, 3)
    assert not flyout.complete_button.isEnabled()
    assert [marker.state for _s, marker in flyout._markers] == ["done", "done", "active"]


def test_progress_is_per_lab_and_survives_reloading(settings: QSettings) -> None:
    flyout = ManualFlyout(settings)
    flyout.show_lab("lab-1", "API lab", SECTIONS)
    flyout.mark_next_step_complete()
    emitted: list[tuple[int, int]] = []
    flyout.progress_changed.connect(lambda done, total: emitted.append((done, total)))

    flyout.show_lab("lab-2", "Other", SECTIONS)
    assert flyout.progress() == (0, 3)

    flyout.show_lab("lab-1", "API lab", SECTIONS)
    assert flyout.progress() == (1, 3)
    assert emitted[-1] == (1, 3)


def test_reset_progress_confirms_and_clears_only_this_lab(settings: QSettings, monkeypatch) -> None:
    prompts: list[dict] = []
    answers = iter([False, True])
    monkeypatch.setattr(
        manual, "confirm", lambda *args, **kwargs: prompts.append(kwargs) or next(answers)
    )
    flyout = ManualFlyout(settings)
    flyout.show_lab("lab-2", "Other", SECTIONS)
    flyout.mark_next_step_complete()
    flyout.show_lab("lab-1", "API lab", SECTIONS)
    flyout.mark_next_step_complete()

    flyout.reset_button.click()  # cancelled
    assert flyout.progress() == (1, 3)

    flyout.reset_button.click()  # confirmed
    assert prompts[-1]["destructive"] is True
    assert flyout.progress() == (0, 3)
    assert settings.value("manual_progress/lab-2/s1/t1") in (True, "true")  # untouched


def test_close_control_emits_close_requested(settings: QSettings) -> None:
    flyout = ManualFlyout(settings)
    fired: list[bool] = []
    flyout.close_requested.connect(lambda: fired.append(True))

    buttons = [b for b in flyout.findChildren(QPushButton) if b.text() == "\u00d7"]
    buttons[0].click()

    assert fired == [True]


def test_long_tokens_never_widen_the_panel(settings: QSettings) -> None:
    flyout = ManualFlyout(settings)
    flyout.setFixedWidth(260)
    flyout.show()
    long_section = ManualSectionInfo(
        "s1",
        "A very long title that certainly does not fit on one line of a narrow panel",
        "Run this:\n\n```\ndocker exec -it practicum-0123456789abcdef-a-really-long-node-name bash\n```\n"
        "and visit https://localhost:3001/some/very/long/path/that/keeps/going/and/going",
        [ManualTaskInfo("t1", "A task whose text is long enough that a plain checkbox would "
                        "have overflowed the panel instead of wrapping onto several lines")],
    )

    flyout.show_lab("lab-1", "Wide", [long_section])

    container = flyout._steps_container
    assert container.sizePolicy().horizontalPolicy() == QSizePolicy.Policy.Ignored
    for label in container.findChildren(QLabel):
        if label.wordWrap():
            assert label.sizePolicy().horizontalPolicy() == QSizePolicy.Policy.Ignored
    rows = container.findChildren(TaskRow)
    assert len(rows) == 1 and rows[0].label.wordWrap()
    rows[0].checkbox.setChecked(True)
    assert flyout.progress() == (1, 1)
