"""Lab results: what a student hands in after working through the instructions
(manual-track-progress, "export the lab results").

Progress lives on the student's computer only (`QSettings`, per lab and task, with the time
each task was ticked). `build_results` turns that plus the lab's metadata into a portable
document - every step and task with its completed flag and timestamp, a summary, the
student's name and the export time - which `write_results` saves as JSON (machine-readable,
for an instructor's tooling) or as a Markdown report (readable as is), by file extension.
No Qt in here so the format is testable on its own.
"""

from __future__ import annotations

import base64
import hashlib
import json
import re
import shutil
import zipfile
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from practicum_desktop.api_client import ManualSectionInfo

RESULTS_FORMAT = "practicum-lab-results"
RESULTS_SCHEMA_VERSION = "1.1"  # 1.1: steps[].requires_screenshot / screenshot, summary counts
RESULTS_FILTER = (
    "Lab results (*.json);;Lab report (*.md);;Lab results bundle (*.zip);;All files (*)"
)


@dataclass(frozen=True)
class TaskCompletion:
    """One task's state as recorded on this computer."""

    section_id: str
    task_id: str
    completed: bool
    completed_at: datetime | None = None


@dataclass(frozen=True)
class StepScreenshot:
    """A screenshot the student attached to a step (the file lives on this computer)."""

    section_id: str
    path: Path
    captured_at: datetime | None = None
    source: str = ""  # "lab_view" (captured from the embedded view) | "upload"


@dataclass(frozen=True)
class LabFacts:
    """What the results say about the lab itself (from the lab list + preview)."""

    id: str
    name: str
    description: str = ""
    author: str = ""
    version: str = ""
    origin: str = ""
    source_file: str | None = None


def _iso(moment: datetime | None) -> str | None:
    if moment is None:
        return None
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=UTC)
    return moment.isoformat(timespec="seconds")


def build_results(
    lab: LabFacts,
    sections: list[ManualSectionInfo],
    completions: list[TaskCompletion],
    student_name: str = "",
    exported_at: datetime | None = None,
    screenshots: Sequence[StepScreenshot] = (),
) -> dict:
    """The results document. Steps follow the manual's order; a task the student never
    ticked is listed as not completed so the instructor sees gaps, not just the ticks.
    `screenshots` are the attached images (any object with section_id / path / captured_at /
    source, e.g. `screenshots.ScreenshotRecord`); a requested screenshot that is missing
    shows as `"screenshot": null`."""
    by_key = {(c.section_id, c.task_id): c for c in completions}
    shots_by_section = {s.section_id: s for s in screenshots}
    steps = []
    total = completed = 0
    shots_required = shots_attached = 0
    stamps: list[datetime] = []
    for number, section in enumerate(sections, start=1):
        tasks = []
        for task in section.tasks:
            state = by_key.get((section.id, task.id))
            done = bool(state and state.completed)
            total += 1
            completed += int(done)
            if done and state is not None and state.completed_at is not None:
                stamps.append(state.completed_at)
            tasks.append(
                {
                    "id": task.id,
                    "text": task.text,
                    "completed": done,
                    "completed_at": _iso(state.completed_at) if done and state else None,
                }
            )
        step: dict = {
            "number": number,
            "id": section.id,
            "title": section.title,
            "completed": bool(tasks) and all(t["completed"] for t in tasks),
            "tasks": tasks,
            "requires_screenshot": bool(section.requires_screenshot),
            "screenshot": None,
        }
        shot = shots_by_section.get(section.id)
        if section.requires_screenshot:
            shots_required += 1
        if shot is not None:
            shots_attached += 1 if section.requires_screenshot else 0
            captured = shot.captured_at
            if captured is not None:
                stamps.append(captured)
            step["screenshot"] = {
                "file": f"screenshots/{_safe_name(section.id)}.png",
                "source_path": str(shot.path),
                "captured_at": _iso(captured),
                "source": shot.source or "",
            }
        if section.requires_screenshot and shot is None:
            step["completed"] = False
        steps.append(step)
    exported = exported_at or datetime.now(UTC)
    return {
        "format": RESULTS_FORMAT,
        "schema_version": RESULTS_SCHEMA_VERSION,
        "exported_at": _iso(exported),
        "student": {"name": student_name.strip()},
        "lab": {
            "id": lab.id,
            "name": lab.name,
            "description": lab.description,
            "author": lab.author,
            "version": lab.version,
            "origin": lab.origin,
            "source_file": lab.source_file,
        },
        "summary": {
            "completed": completed,
            "total": total,
            "all_complete": (total > 0 or shots_required > 0)
            and completed == total
            and shots_attached == shots_required,
            "percent": round(100 * completed / total) if total else 0,
            "screenshots_required": shots_required,
            "screenshots_attached": shots_attached,
            "first_completed_at": _iso(min(stamps)) if stamps else None,
            "last_completed_at": _iso(max(stamps)) if stamps else None,
        },
        "steps": steps,
    }


def _safe_name(section_id: str) -> str:
    return re.sub(r"[^a-z0-9-]+", "-", section_id.lower()).strip("-") or "step"


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def results_file_name(lab_name: str, student_name: str = "", extension: str = "json") -> str:
    """'static-routing-fundamentals-results-ada-lovelace.json'."""
    parts = [_slug(lab_name) or "lab", "results"]
    if _slug(student_name):
        parts.append(_slug(student_name))
    return "-".join(parts) + f".{extension}"


def _local(iso: str | None) -> str:
    if not iso:
        return ""
    try:
        return datetime.fromisoformat(iso).astimezone().strftime("%Y-%m-%d %H:%M")
    except ValueError:
        return iso


def results_to_markdown(results: dict) -> str:
    """A report a person can read (or paste into an LMS) - the same facts as the JSON."""
    lab = results["lab"]
    summary = results["summary"]
    lines = [f"# Lab results: {lab['name']}", ""]
    student = results["student"]["name"]
    lines.append(f"- **Student:** {student or '(not given)'}")
    lines.append(f"- **Exported:** {_local(results['exported_at'])}")
    meta = " · ".join(p for p in (lab.get("author"), lab.get("version")) if p)
    if meta:
        lines.append(f"- **Lab:** {meta}")
    if lab.get("description"):
        lines.append(f"- **About:** {lab['description']}")
    lines.append(
        f"- **Progress:** {summary['completed']} of {summary['total']} tasks complete "
        f"({summary['percent']} %)" + (" — all steps complete" if summary["all_complete"] else "")
    )
    if summary.get("screenshots_required"):
        lines.append(
            f"- **Screenshots:** {summary['screenshots_attached']} of "
            f"{summary['screenshots_required']} requested attached"
        )
    if summary.get("first_completed_at"):
        lines.append(
            f"- **Worked on:** {_local(summary['first_completed_at'])} → "
            f"{_local(summary['last_completed_at'])}"
        )
    lines += ["", "| # | Step | Task | Done | Completed |", "|---|---|---|---|---|"]
    for step in results["steps"]:
        if not step["tasks"]:
            lines.append(f"| {step['number']} | {step['title']} | — | — | |")
        for task in step["tasks"]:
            lines.append(
                f"| {step['number']} | {step['title']} | {task['text']} | "
                f"{'yes' if task['completed'] else 'no'} | {_local(task['completed_at'])} |"
            )
    shots = [s for s in results["steps"] if s.get("screenshot") or s.get("requires_screenshot")]
    if shots:
        lines += ["", "## Screenshots", ""]
        for step in shots:
            shot = step.get("screenshot")
            if shot is None:
                lines.append(f"- Step {step['number']} ({step['title']}): **missing**")
                continue
            how = "captured from the lab view" if shot["source"] == "lab_view" else "uploaded"
            lines.append(
                f"### Step {step['number']}: {step['title']} ({how}, {_local(shot['captured_at'])})"
            )
            lines.append(f"![Step {step['number']}]({shot['file']})")
            lines.append("")
    lines.append("")
    return "\n".join(lines)


def _screenshot_files(results: dict) -> list[tuple[str, Path]]:
    """(relative name inside the export, source path) for every attached screenshot."""
    files = []
    for step in results["steps"]:
        shot = step.get("screenshot")
        if shot and shot.get("source_path"):
            files.append((shot["file"], Path(shot["source_path"])))
    return files


def _public(results: dict) -> dict:
    """The document without the student's local file paths."""
    copy = json.loads(json.dumps(results))
    for step in copy["steps"]:
        if step.get("screenshot"):
            step["screenshot"].pop("source_path", None)
    return copy


def write_results(path: Path, results: dict) -> None:
    """`.zip`: a bundle (results.json + report.md + screenshots/); `.md`: the report with the
    screenshots copied into `<name>-screenshots/` beside it; otherwise JSON with every
    screenshot embedded as base64 PNG (one self-contained file to hand in)."""
    suffix = path.suffix.lower()
    shots = _screenshot_files(results)
    public = _public(results)
    if suffix == ".zip":
        with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
            bundle.writestr("results.json", json.dumps(public, indent=2, ensure_ascii=False) + "\n")
            bundle.writestr("report.md", results_to_markdown(public))
            for name, source in shots:
                if source.is_file():
                    bundle.write(source, name)
        return
    if suffix == ".md":
        if shots:
            folder = path.with_name(f"{path.stem}-screenshots")
            folder.mkdir(parents=True, exist_ok=True)
            for step in public["steps"]:
                if step.get("screenshot"):
                    file_name = Path(step["screenshot"]["file"]).name
                    step["screenshot"]["file"] = f"{folder.name}/{file_name}"
            for name, source in shots:
                if source.is_file():
                    shutil.copyfile(source, folder / Path(name).name)
        path.write_text(results_to_markdown(public), encoding="utf-8")
        return
    for step in public["steps"]:
        shot = step.get("screenshot")
        if not shot:
            continue
        source = next((s for n, s in shots if n == shot["file"]), None)
        if source is not None and source.is_file():
            data = source.read_bytes()
            shot["sha256"] = hashlib.sha256(data).hexdigest()
            shot["png_base64"] = base64.b64encode(data).decode("ascii")
    path.write_text(json.dumps(public, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
