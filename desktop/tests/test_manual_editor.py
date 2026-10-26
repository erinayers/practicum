from __future__ import annotations

from PySide6.QtWidgets import QLabel

from practicum_desktop.manual import StepMarker, TaskRow
from practicum_desktop.manual_editor import ManualPreview, ManualStepsEditor, StepRow
from practicum_desktop.quickstart import QuickStartStep, steps_to_manual


def test_editor_adds_removes_and_renumbers_steps() -> None:
    editor = ManualStepsEditor()
    changes: list[int] = []
    editor.changed.connect(lambda: changes.append(1))

    first = editor.add_step()
    first.title_field.setText("One")
    second = editor.add_step(QuickStartStep("Two", "details"))
    third = editor.add_step()
    assert [r.number_label.text() for r in editor.rows] == ["1", "2", "3"]
    assert editor.titled_count() == 2  # the untitled third does not count

    editor.remove_row(first)
    assert editor.rows == [second, third]
    assert [r.number_label.text() for r in editor.rows] == ["1", "2"]
    assert editor.steps()[0] == QuickStartStep("Two", "details")
    assert editor.manual() == {
        "sections": [
            {
                "id": "step-1",
                "title": "Two",
                "content_markdown": "details",
                "tasks": [{"id": "done", "text": "Done: Two"}],
            }
        ]
    }
    assert changes  # every edit notifies the owner

    editor.clear()
    assert editor.rows == [] and editor.manual() is None


def test_remove_button_on_a_row_removes_it() -> None:
    editor = ManualStepsEditor()
    row = editor.add_step(QuickStartStep("Gone"))
    remove = next(b for b in row.findChildren(type(editor.add_button)) if b.text() == "\u00d7")
    assert remove.accessibleName() == "Remove this step"

    remove.click()

    assert editor.rows == []


def test_load_manual_round_trips_and_keeps_authored_details() -> None:
    manual = {
        "sections": [
            {
                "id": "overview",
                "title": "Overview",
                "content_markdown": "## Goal",
                "tasks": [{"id": "a", "text": "Read it."}, {"id": "b", "text": "Understand it."}],
            },
            {
                "id": "step-2",
                "title": "Ping",
                "content_markdown": "ping 10.0.2.10",
                "tasks": [{"id": "done", "text": "Done: Ping"}],
            },
            {"id": "reading", "title": "Reading", "content_markdown": "RFC 1812", "tasks": []},
        ]
    }
    editor = ManualStepsEditor()

    editor.load_manual(manual)

    assert editor.manual() == manual  # untouched → identical
    editor.rows[1].title_field.setText("Ping host-b")  # our generated task follows the title
    assert editor.manual()["sections"][1]["tasks"] == [{"id": "done", "text": "Done: Ping host-b"}]
    editor.load_manual(None)
    assert editor.rows == []


def test_steps_to_manual_keeps_section_ids_unique() -> None:
    manual = steps_to_manual(
        [
            QuickStartStep("A", section_id="step-2"),
            QuickStartStep("B"),  # would be step-2 as well
            QuickStartStep("C", section_id="step-2"),  # duplicate authored id
        ]
    )

    assert [s["id"] for s in manual["sections"]] == ["step-2", "step-2-2", "step-3"]


def test_preview_renders_markdown_markers_and_tasks() -> None:
    preview = ManualPreview()
    assert preview.empty_label.isHidden() is False

    preview.set_steps(
        [
            QuickStartStep("Install", "Run:\n\n```\napt-get install -y git\n```"),
            QuickStartStep("Check", "", tasks=[{"id": "x", "text": "Custom task"}]),
            QuickStartStep(""),  # untitled: not shown
        ]
    )

    assert preview.empty_label.isHidden()
    assert [m.state for m in preview.findChildren(StepMarker)] == ["active", "todo"]
    texts = [lab.text() for lab in preview.findChildren(QLabel)]
    assert "Install" in texts and "Check" in texts
    assert any("apt-get install -y git" in t for t in texts)
    tasks = preview.findChildren(TaskRow)
    assert [t.label.text() for t in tasks] == ["Done: Install", "Custom task"]
    assert all(not t.checkbox.isEnabled() for t in tasks)

    preview.set_steps([])
    assert preview.empty_label.isHidden() is False and preview.findChildren(StepMarker) == []


def test_preview_toggle_switches_pages_and_refreshes() -> None:
    editor = ManualStepsEditor()
    editor.add_step(QuickStartStep("First"))

    editor.preview_button.click()
    assert editor.previewing and editor.preview_button.text() == "Edit"
    assert "First" in [lab.text() for lab in editor.preview.findChildren(QLabel)]

    editor.add_step()  # adding a step returns to the editor with focus on the new row
    assert editor.previewing is False
    assert isinstance(editor.rows[-1], StepRow)


def test_instructor_can_ask_for_a_screenshot_per_step() -> None:
    editor = ManualStepsEditor()
    first = editor.add_step(QuickStartStep("Show the desktop"))
    editor.add_step(QuickStartStep("Read the docs"))
    assert first.screenshot_box.isChecked() is False

    first.screenshot_box.setChecked(True)

    manual = editor.manual()
    assert manual["sections"][0]["requires_screenshot"] is True
    assert "requires_screenshot" not in manual["sections"][1]  # unchanged shape when off
    assert [s.requires_screenshot for s in editor.steps()] == [True, False]

    editor.preview_button.click()
    texts = [lab.text() for lab in editor.preview.findChildren(QLabel)]
    assert sum("Screenshot required" in t for t in texts) == 1

    # round trip through load_manual keeps the flag
    again = ManualStepsEditor()
    again.load_manual(manual)
    assert [r.screenshot_box.isChecked() for r in again.rows] == [True, False]
    assert again.manual() == manual
