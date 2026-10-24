"""Reading lab files from disk before they are handed to the API.

This module deliberately contains no lab/schema logic (the API is the authority on what a
valid lab is). It only answers "can this file be turned into a JSON object to send?", and
when the answer is no, says exactly why in words a student can act on.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from practicum_desktop.api_client import FieldIssue

LAB_FILE_SUFFIXES = (".json",)
# Lab bundles (.zip) appear in the mockup but no bundle format exists yet (Tigre/11 C8 /
# S-13). Until one does, a .zip is rejected with a specific message rather than a JSON error.
UNSUPPORTED_BUNDLE_SUFFIXES = (".zip",)
# Generous for a JSON spec with an embedded manual, small enough to refuse obvious mistakes
# (a disk image, a video) before reading them into memory.
MAX_LAB_FILE_BYTES = 5 * 1024 * 1024

SAMPLES_DIR = Path(__file__).resolve().parent / "samples"


@dataclass
class LabFileReadResult:
    success: bool
    definition: dict[str, object] | None = None
    error: str = ""


def read_lab_file(path: Path | str) -> LabFileReadResult:
    """Reads a lab file and returns the parsed JSON object, or a specific error."""
    path = Path(path)

    if path.suffix.lower() in UNSUPPORTED_BUNDLE_SUFFIXES:
        return LabFileReadResult(
            success=False,
            error=(
                f"'{path.name}' is a lab bundle (.zip). Bundles aren't supported yet — "
                "choose the .json lab export instead."
            ),
        )

    if not path.exists():
        return LabFileReadResult(
            success=False, error=f"The file '{path}' could not be found. It may have been moved."
        )
    if not path.is_file():
        return LabFileReadResult(success=False, error=f"'{path}' is not a file.")

    try:
        size = path.stat().st_size
    except OSError as exc:
        return LabFileReadResult(success=False, error=f"Could not read '{path.name}': {exc}")
    if size > MAX_LAB_FILE_BYTES:
        return LabFileReadResult(
            success=False,
            error=(
                f"'{path.name}' is {_format_size(size)}, larger than the "
                f"{_format_size(MAX_LAB_FILE_BYTES)} limit for lab files. "
                "This does not look like a Practicum lab export."
            ),
        )

    try:
        raw = path.read_bytes()
    except OSError as exc:
        return LabFileReadResult(success=False, error=f"Could not read '{path.name}': {exc}")

    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        return LabFileReadResult(
            success=False,
            error=(
                f"'{path.name}' is not a text file (expected UTF-8 JSON). "
                "Make sure you selected the lab export, not a different file."
            ),
        )

    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as exc:
        return LabFileReadResult(
            success=False,
            error=(
                f"'{path.name}' is not valid JSON: {exc.msg} "
                f"(line {exc.lineno}, column {exc.colno})."
            ),
        )

    if not isinstance(parsed, dict):
        kind = "a list" if isinstance(parsed, list) else f"a {type(parsed).__name__}"
        return LabFileReadResult(
            success=False,
            error=(
                f"'{path.name}' contains {kind}, not a lab definition. A lab file is a "
                "single JSON object with 'name', 'nodes', 'networks' and 'interfaces'."
            ),
        )

    return LabFileReadResult(success=True, definition=parsed)


def format_issue(issue: FieldIssue) -> str:
    """Renders a structured API validation issue as one readable line.

    ["nodes", "0", "image"] + "Field required" -> "nodes[0].image: Field required".
    """
    location = ""
    for part in issue.location:
        if part.isdigit():
            location += f"[{part}]"
        else:
            location += f".{part}" if location else part
    # Pydantic prefixes custom validator failures with "Value error, "; drop the noise.
    message = issue.message.removeprefix("Value error, ")
    return f"{location}: {message}" if location else message


@dataclass
class LabFileEntry:
    """A file offered in the Open Lab File list (a recent file or a bundled sample)."""

    path: Path
    kind: str  # "recent" | "sample"
    exists: bool = True
    size_bytes: int | None = None

    @property
    def name(self) -> str:
        return self.path.name

    @property
    def hint(self) -> str:
        label = "Sample lab" if self.kind == "sample" else "Recent"
        if not self.exists:
            return f"{label} · file not found"
        if self.size_bytes is None:
            return label
        return f"{label} · {_format_size(self.size_bytes)}"


def describe_lab_file(path: Path, kind: str) -> LabFileEntry:
    try:
        size: int | None = path.stat().st_size
        exists = path.is_file()
    except OSError:
        size, exists = None, False
    return LabFileEntry(path=path, kind=kind, exists=exists, size_bytes=size)


def sample_lab_files(samples_dir: Path = SAMPLES_DIR) -> list[LabFileEntry]:
    """Lab files bundled with the desktop package, sorted by name. Empty if none ship."""
    if not samples_dir.is_dir():
        return []
    return [
        describe_lab_file(path, "sample")
        for path in sorted(samples_dir.iterdir())
        if path.suffix.lower() in LAB_FILE_SUFFIXES and path.is_file()
    ]


def _format_size(size: int) -> str:
    if size < 1024:
        return f"{size} B"
    if size < 1024 * 1024:
        return f"{max(1, round(size / 1024))} KB"
    return f"{size / (1024 * 1024):.1f} MB"
