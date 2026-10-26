from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtCore import QSettings
from PySide6.QtGui import QColor, QPixmap
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


def test_done_marker_uses_the_design_check_icon(settings: QSettings) -> None:
    flyout = ManualFlyout(settings)
    flyout.show_lab("lab-1", "API lab", SECTIONS)

    flyout.mark_next_step_complete()

    done_marker = flyout._markers[0][1]
    assert done_marker.state == "done"
    assert done_marker.pixmap() is not None and not done_marker.pixmap().isNull()
    assert done_marker.accessibleName() == "Step complete"
    active_marker = flyout._markers[1][1]
    assert active_marker.text() == "2"
    assert active_marker.accessibleName() == "Step 2, current"
    assert not flyout.complete_button.icon().isNull()


def test_ticking_a_task_records_when_and_the_export_control_follows(settings: QSettings) -> None:
    flyout = ManualFlyout(settings)
    flyout.show_empty("nothing")
    assert flyout.export_button.isEnabled() is False

    flyout.show_lab("lab-1", "API lab", SECTIONS)
    assert flyout.export_button.isEnabled() is True
    assert flyout.done_banner.isHidden()
    before = [c for c in flyout.task_completions()]
    assert all(not c.completed and c.completed_at is None for c in before)
    assert [(c.section_id, c.task_id) for c in before] == [
        ("s1", "t1"),
        ("s2", "t2"),
        ("s2", "t3"),
    ]

    flyout.mark_next_step_complete()

    first = flyout.task_completions()[0]
    assert first.completed is True and first.completed_at is not None
    assert first.completed_at.tzinfo is not None  # stored as an ISO timestamp with zone
    assert settings.value("manual_progress/lab-1/s1/t1_completed_at")

    flyout._task_boxes[0][2].setChecked(False)  # untick: the time goes too
    assert flyout.task_completions()[0].completed_at is None
    assert not settings.value("manual_progress/lab-1/s1/t1_completed_at", "")

    fired: list[int] = []
    flyout.export_requested.connect(lambda: fired.append(1))
    for _ in range(3):
        flyout.mark_next_step_complete()
    assert flyout.progress() == (3, 3)
    assert flyout.done_banner.isHidden() is False
    assert "All steps complete" in flyout.done_banner.text()
    flyout.export_button.click()
    assert fired == [1]

    # timestamps survive reloading the lab (they live in QSettings like the ticks)
    again = ManualFlyout(settings)
    again.show_lab("lab-1", "API lab", SECTIONS)
    assert all(c.completed and c.completed_at for c in again.task_completions())
    assert again.sections == SECTIONS


SHOT_SECTIONS = [
    ManualSectionInfo(
        "s1", "Configure", "Do it", [ManualTaskInfo("t1", "Done")], requires_screenshot=True
    ),
    ManualSectionInfo("s2", "Verify", "Check", [ManualTaskInfo("t2", "Done")]),
]


def _pixmap() -> QPixmap:
    pixmap = QPixmap(10, 6)
    pixmap.fill(QColor(10, 200, 10))
    return pixmap


def test_a_requested_screenshot_is_part_of_the_steps_progress(
    settings: QSettings, tmp_path: Path
) -> None:
    flyout = ManualFlyout(settings, screenshot_dir=tmp_path / "shots")
    captures: list[str] = []
    uploads: list[str] = []
    flyout.screenshot_capture_requested.connect(captures.append)
    flyout.screenshot_upload_requested.connect(uploads.append)
    flyout.show_lab("lab-1", "Lab", SHOT_SECTIONS)

    assert flyout.progress() == (0, 3)  # two tasks + one requested screenshot
    row = flyout._screenshot_rows["s1"]
    assert row.thumbnail.isHidden() and row.remove_button.isHidden()
    assert "Screenshot required" in row.hint_label.text()
    assert "s2" not in flyout._screenshot_rows  # only where the instructor asked

    row.capture_button.click()
    row.upload_button.click()
    assert captures == ["s1"] and uploads == ["s1"]

    # every task ticked but the screenshot missing: not complete, and it says why
    flyout.mark_next_step_complete()
    flyout.mark_next_step_complete()
    assert flyout.task_progress() == (2, 2) and flyout.progress() == (2, 3)
    assert flyout.complete_button.isEnabled() is False  # nothing left to tick
    assert "attach the 1 requested screenshot" in flyout.done_banner.text()
    assert flyout.done_banner.property("banner") == "warn"
    assert [m.state for _s, m in flyout._markers] == ["active", "done"]

    assert flyout.attach_screenshot("s1", _pixmap()) is True
    assert flyout.progress() == (3, 3)
    assert "All steps complete" in flyout.done_banner.text()
    assert [m.state for _s, m in flyout._markers] == ["done", "done"]
    assert row.thumbnail.isHidden() is False and row.remove_button.isHidden() is False
    assert "captured from the lab view" in row.hint_label.text()
    assert row.capture_button.text() == "Capture again"
    shots = flyout.screenshots()
    assert [s.section_id for s in shots] == ["s1"] and shots[0].path.is_file()

    # survives reopening; removing it reopens the gap
    again = ManualFlyout(settings, screenshot_dir=tmp_path / "shots")
    again.show_lab("lab-1", "Lab", SHOT_SECTIONS)
    assert again.progress() == (3, 3)
    again.remove_screenshot("s1")
    assert again.progress() == (2, 3) and again.screenshots() == []
    assert not (tmp_path / "shots" / "lab-1" / "s1.png").exists()


def test_upload_attaches_an_image_file_and_reports_bad_ones(
    settings: QSettings, tmp_path: Path
) -> None:
    flyout = ManualFlyout(settings, screenshot_dir=tmp_path / "shots")
    flyout.show_lab("lab-1", "Lab", SHOT_SECTIONS)
    image = tmp_path / "proof.png"
    assert _pixmap().save(str(image), "PNG")

    assert flyout.attach_screenshot_file("s1", image) is True
    assert "uploaded" in flyout._screenshot_rows["s1"].hint_label.text()

    bad = tmp_path / "notes.txt"
    bad.write_text("hello")
    assert flyout.attach_screenshot_file("s1", bad) is False
    status = flyout._screenshot_rows["s1"].status_label
    assert status.isHidden() is False and "not an image" in status.text()
    assert flyout.screenshots()[0].source == "upload"  # the good one is kept

    flyout.show_screenshot_problem("s1", "The lab view is not showing a web interface")
    assert "not showing a web interface" in status.text()
    assert flyout.attach_screenshot("nope", _pixmap()) is False  # no such step


def test_reset_progress_also_removes_screenshots(
    settings: QSettings, tmp_path: Path, monkeypatch
) -> None:
    flyout = ManualFlyout(settings, screenshot_dir=tmp_path / "shots")
    flyout.show_lab("lab-1", "Lab", SHOT_SECTIONS)
    flyout.attach_screenshot("s1", _pixmap())
    monkeypatch.setattr("practicum_desktop.manual.confirm", lambda *a, **k: True)

    flyout.reset_button.click()

    assert flyout.screenshots() == []
    assert not (tmp_path / "shots" / "lab-1").exists()
