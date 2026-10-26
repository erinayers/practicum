from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from practicum_desktop.api_client import ManualSectionInfo, ManualTaskInfo
from practicum_desktop.lab_results import (
    RESULTS_FORMAT,
    RESULTS_SCHEMA_VERSION,
    LabFacts,
    StepScreenshot,
    TaskCompletion,
    build_results,
    results_file_name,
    results_to_markdown,
    write_results,
)

SECTIONS = [
    ManualSectionInfo(
        "s1",
        "Install",
        "pip install",
        [ManualTaskInfo("t1", "Installed the app"), ManualTaskInfo("t2", "Ran the tests")],
    ),
    ManualSectionInfo("s2", "Run", "flask run", [ManualTaskInfo("t3", "Started the API")]),
    ManualSectionInfo("s3", "Reading", "RFC 1812", []),
]
LAB = LabFacts(
    id="lab-1",
    name="Build a Python API",
    description="A tiny API.",
    author="Dr. Ada",
    version="1.2",
    origin="imported",
    source_file="python-api.json",
)
T1 = datetime(2026, 10, 25, 14, 0, tzinfo=UTC)
T2 = datetime(2026, 10, 25, 14, 30, tzinfo=UTC)
EXPORTED = datetime(2026, 10, 25, 15, 0, tzinfo=UTC)


def _partial() -> dict:
    return build_results(
        LAB,
        SECTIONS,
        [
            TaskCompletion("s1", "t1", True, T1),
            TaskCompletion("s1", "t2", True, T2),
            TaskCompletion("s2", "t3", False),
        ],
        student_name="  Ada Lovelace ",
        exported_at=EXPORTED,
    )


def test_results_document_lists_every_step_and_task_with_state_and_time() -> None:
    results = _partial()

    assert results["format"] == RESULTS_FORMAT
    assert results["schema_version"] == RESULTS_SCHEMA_VERSION
    assert results["exported_at"] == "2026-10-25T15:00:00+00:00"
    assert results["student"] == {"name": "Ada Lovelace"}
    assert results["lab"] == {
        "id": "lab-1",
        "name": "Build a Python API",
        "description": "A tiny API.",
        "author": "Dr. Ada",
        "version": "1.2",
        "origin": "imported",
        "source_file": "python-api.json",
    }
    assert results["summary"] == {
        "completed": 2,
        "total": 3,
        "all_complete": False,
        "percent": 67,
        "screenshots_required": 0,
        "screenshots_attached": 0,
        "first_completed_at": "2026-10-25T14:00:00+00:00",
        "last_completed_at": "2026-10-25T14:30:00+00:00",
    }
    steps = results["steps"]
    assert [s["number"] for s in steps] == [1, 2, 3]
    assert steps[0]["completed"] is True
    assert steps[0]["requires_screenshot"] is False and steps[0]["screenshot"] is None
    assert steps[0]["tasks"][1] == {
        "id": "t2",
        "text": "Ran the tests",
        "completed": True,
        "completed_at": "2026-10-25T14:30:00+00:00",
    }
    assert steps[1]["tasks"][0] == {
        "id": "t3",
        "text": "Started the API",
        "completed": False,
        "completed_at": None,
    }
    assert steps[2]["completed"] is False and steps[2]["tasks"] == []  # no tasks: not "done"


def test_all_complete_and_untracked_tasks() -> None:
    done = build_results(
        LAB,
        SECTIONS[:2],
        [
            TaskCompletion("s1", "t1", True, T1),
            TaskCompletion("s1", "t2", True, T1),
            TaskCompletion("s2", "t3", True, T2),
        ],
        exported_at=EXPORTED,
    )
    assert done["summary"]["all_complete"] is True and done["summary"]["percent"] == 100

    nothing = build_results(LAB, SECTIONS, [], exported_at=EXPORTED)  # never ticked anything
    assert nothing["summary"] == {
        "completed": 0,
        "total": 3,
        "all_complete": False,
        "percent": 0,
        "screenshots_required": 0,
        "screenshots_attached": 0,
        "first_completed_at": None,
        "last_completed_at": None,
    }
    assert all(not t["completed"] for s in nothing["steps"] for t in s["tasks"])


def test_markdown_report_is_readable_and_complete() -> None:
    report = results_to_markdown(_partial())

    assert report.startswith("# Lab results: Build a Python API\n")
    assert "- **Student:** Ada Lovelace" in report
    assert "- **Lab:** Dr. Ada · 1.2" in report
    assert "- **Progress:** 2 of 3 tasks complete (67 %)" in report
    assert "| 1 | Install | Ran the tests | yes |" in report
    assert "| 2 | Run | Started the API | no |  |" in report
    assert "| 3 | Reading | — | — | |" in report
    assert "all steps complete" not in report
    full = results_to_markdown(
        build_results(
            LAB,
            SECTIONS[:1],
            [TaskCompletion("s1", "t1", True, T1), TaskCompletion("s1", "t2", True, T2)],
            exported_at=EXPORTED,
        )
    )
    assert "all steps complete" in full


def test_write_results_picks_the_format_by_extension(tmp_path: Path) -> None:
    results = _partial()

    write_results(tmp_path / "r.json", results)
    write_results(tmp_path / "r.md", results)
    write_results(tmp_path / "r.txt", results)

    assert json.loads((tmp_path / "r.json").read_text(encoding="utf-8")) == results
    assert (tmp_path / "r.md").read_text(encoding="utf-8") == results_to_markdown(results)
    assert json.loads((tmp_path / "r.txt").read_text(encoding="utf-8")) == results  # default JSON


def test_results_file_name() -> None:
    assert results_file_name("Build a Python API", "Ada Lovelace") == (
        "build-a-python-api-results-ada-lovelace.json"
    )
    assert results_file_name("Build a Python API") == "build-a-python-api-results.json"
    assert results_file_name("!!!", "", "md") == "lab-results.md"


# ----- screenshots (user request: instructors ask, students capture or upload) -----------------

SHOT_SECTIONS = [
    ManualSectionInfo(
        "s1", "Configure", "Do it", [ManualTaskInfo("t1", "Done")], requires_screenshot=True
    ),
    ManualSectionInfo(
        "s2", "Verify", "Check", [ManualTaskInfo("t2", "Done")], requires_screenshot=True
    ),
]


def _png(path: Path, colour: tuple[int, int, int] = (10, 20, 30)) -> Path:
    from PySide6.QtGui import QColor, QImage

    image = QImage(8, 6, QImage.Format.Format_RGB32)
    image.fill(QColor(*colour))
    assert image.save(str(path), "PNG")
    return path


def test_requested_screenshots_count_towards_completion(tmp_path: Path) -> None:
    shot = _png(tmp_path / "s1.png")
    done = [TaskCompletion("s1", "t1", True, T1), TaskCompletion("s2", "t2", True, T2)]

    missing_one = build_results(
        LAB,
        SHOT_SECTIONS,
        done,
        exported_at=EXPORTED,
        screenshots=[StepScreenshot("s1", shot, T2, "lab_view")],
    )
    summary = missing_one["summary"]
    assert summary["completed"] == 2 and summary["total"] == 2  # every task ticked…
    assert summary["screenshots_required"] == 2 and summary["screenshots_attached"] == 1
    assert summary["all_complete"] is False  # …but a requested screenshot is missing
    first, second = missing_one["steps"]
    assert first["requires_screenshot"] is True
    assert first["screenshot"] == {
        "file": "screenshots/s1.png",
        "source_path": str(shot),
        "captured_at": "2026-10-25T14:30:00+00:00",
        "source": "lab_view",
    }
    assert first["completed"] is True
    assert second["screenshot"] is None and second["completed"] is False

    both = build_results(
        LAB,
        SHOT_SECTIONS,
        done,
        exported_at=EXPORTED,
        screenshots=[
            StepScreenshot("s1", shot, T2, "lab_view"),
            StepScreenshot("s2", shot, T2, "upload"),
        ],
    )
    assert both["summary"]["all_complete"] is True
    report = results_to_markdown(both)
    assert "- **Screenshots:** 2 of 2 requested attached" in report
    assert "### Step 1: Configure (captured from the lab view" in report
    assert "![Step 2](screenshots/s2.png)" in report
    assert "**missing**" in results_to_markdown(missing_one)


def test_exports_carry_the_screenshots_in_each_format(tmp_path: Path) -> None:
    import zipfile
    import base64
    import hashlib

    shot = _png(tmp_path / "src.png")
    results = build_results(
        LAB,
        SHOT_SECTIONS[:1],
        [TaskCompletion("s1", "t1", True, T1)],
        student_name="Ada",
        exported_at=EXPORTED,
        screenshots=[StepScreenshot("s1", shot, T2, "upload")],
    )
    out = tmp_path / "out"
    out.mkdir()

    # JSON: self-contained, image embedded, local path not leaked
    write_results(out / "r.json", results)
    saved = json.loads((out / "r.json").read_text(encoding="utf-8"))
    shot_json = saved["steps"][0]["screenshot"]
    assert "source_path" not in shot_json
    assert base64.b64decode(shot_json["png_base64"]) == shot.read_bytes()
    assert shot_json["sha256"] == hashlib.sha256(shot.read_bytes()).hexdigest()
    assert results["steps"][0]["screenshot"]["source_path"] == str(shot)  # input untouched

    # Markdown: report + a folder of images beside it
    write_results(out / "r.md", results)
    report = (out / "r.md").read_text(encoding="utf-8")
    assert "![Step 1](r-screenshots/s1.png)" in report
    assert (out / "r-screenshots" / "s1.png").read_bytes() == shot.read_bytes()

    # Zip: one bundle with results.json, report.md and screenshots/
    write_results(out / "r.zip", results)
    with zipfile.ZipFile(out / "r.zip") as bundle:
        assert sorted(bundle.namelist()) == ["report.md", "results.json", "screenshots/s1.png"]
        inner = json.loads(bundle.read("results.json"))
        assert inner["steps"][0]["screenshot"]["file"] == "screenshots/s1.png"
        assert "png_base64" not in inner["steps"][0]["screenshot"]
        assert bundle.read("screenshots/s1.png") == shot.read_bytes()
