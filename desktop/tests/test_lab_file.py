from __future__ import annotations

import json
from pathlib import Path

from practicum_desktop.api_client import FieldIssue
from practicum_desktop.lab_file import (
    MAX_LAB_FILE_BYTES,
    SAMPLES_DIR,
    LabFileEntry,
    describe_lab_file,
    format_issue,
    read_lab_file,
    sample_lab_files,
)

REPO_EXAMPLES_DIR = Path(__file__).resolve().parents[2] / "examples"


def _write(path: Path, content: str | bytes) -> Path:
    if isinstance(content, str):
        path.write_text(content, encoding="utf-8")
    else:
        path.write_bytes(content)
    return path


def test_read_lab_file_returns_parsed_object(tmp_path: Path) -> None:
    path = _write(tmp_path / "lab.json", json.dumps({"name": "Lab", "nodes": []}))

    result = read_lab_file(path)

    assert result.success is True
    assert result.definition == {"name": "Lab", "nodes": []}
    assert result.error == ""


def test_read_lab_file_accepts_utf8_bom(tmp_path: Path) -> None:
    path = _write(tmp_path / "lab.json", b"\xef\xbb\xbf" + b'{"name": "Lab"}')

    result = read_lab_file(path)

    assert result.success is True
    assert result.definition == {"name": "Lab"}


def test_read_lab_file_rejects_zip_bundles_with_specific_message(tmp_path: Path) -> None:
    path = _write(tmp_path / "python-api-lab.zip", b"PK\x03\x04")

    result = read_lab_file(path)

    assert result.success is False
    assert "python-api-lab.zip" in result.error
    assert "Bundles aren't supported yet" in result.error
    assert ".json" in result.error


def test_read_lab_file_reports_missing_file(tmp_path: Path) -> None:
    result = read_lab_file(tmp_path / "gone.json")

    assert result.success is False
    assert "could not be found" in result.error


def test_read_lab_file_reports_directory(tmp_path: Path) -> None:
    result = read_lab_file(tmp_path)

    assert result.success is False
    assert "is not a file" in result.error


def test_read_lab_file_rejects_oversized_file_without_reading_it(tmp_path: Path) -> None:
    path = tmp_path / "huge.json"
    with path.open("wb") as handle:
        handle.truncate(MAX_LAB_FILE_BYTES + 1)

    result = read_lab_file(path)

    assert result.success is False
    assert "larger than the 5.0 MB limit" in result.error


def test_read_lab_file_rejects_binary_content(tmp_path: Path) -> None:
    path = _write(tmp_path / "image.json", b"\xff\xfe\x00\x01binary")

    result = read_lab_file(path)

    assert result.success is False
    assert "not a text file" in result.error


def test_read_lab_file_reports_json_syntax_error_with_position(tmp_path: Path) -> None:
    path = _write(tmp_path / "broken.json", '{\n  "name": "Lab",\n  "nodes": [\n}')

    result = read_lab_file(path)

    assert result.success is False
    assert "broken.json" in result.error
    assert "not valid JSON" in result.error
    assert "line 4" in result.error


def test_read_lab_file_rejects_non_object_json(tmp_path: Path) -> None:
    path = _write(tmp_path / "list.json", "[1, 2, 3]")

    result = read_lab_file(path)

    assert result.success is False
    assert "contains a list, not a lab definition" in result.error


def test_format_issue_renders_location_path() -> None:
    issue = FieldIssue(
        location=["nodes", "0", "image"], message="Field required", issue_type="missing"
    )

    assert format_issue(issue) == "nodes[0].image: Field required"


def test_format_issue_strips_pydantic_value_error_prefix() -> None:
    issue = FieldIssue(
        location=[], message="Value error, node ids must be unique", issue_type="value_error"
    )

    assert format_issue(issue) == "node ids must be unique"


def test_format_issue_without_location_returns_message_only() -> None:
    issue = FieldIssue(location=[], message="extra fields not permitted", issue_type="extra")

    assert format_issue(issue) == "extra fields not permitted"


def test_describe_lab_file_reports_size_and_existence(tmp_path: Path) -> None:
    path = _write(tmp_path / "lab.json", "x" * 2048)

    entry = describe_lab_file(path, "recent")

    assert entry.name == "lab.json"
    assert entry.exists is True
    assert entry.size_bytes == 2048
    assert entry.hint == "Recent · 2 KB"


def test_describe_lab_file_marks_missing_files() -> None:
    entry = describe_lab_file(Path("/definitely/not/here.json"), "recent")

    assert entry.exists is False
    assert entry.hint == "Recent · file not found"


def test_lab_file_entry_sample_hint() -> None:
    entry = LabFileEntry(path=Path("static-routing.json"), kind="sample", size_bytes=512)

    assert entry.hint == "Sample lab · 512 B"


def test_sample_lab_files_lists_bundled_json_only(tmp_path: Path) -> None:
    _write(tmp_path / "b.json", "{}")
    _write(tmp_path / "a.json", "{}")
    _write(tmp_path / "notes.txt", "ignore me")
    (tmp_path / "nested").mkdir()

    entries = sample_lab_files(tmp_path)

    assert [entry.name for entry in entries] == ["a.json", "b.json"]
    assert all(entry.kind == "sample" for entry in entries)


def test_sample_lab_files_is_empty_when_directory_missing(tmp_path: Path) -> None:
    assert sample_lab_files(tmp_path / "missing") == []


def test_bundled_samples_exist_and_parse() -> None:
    entries = sample_lab_files()

    assert [entry.name for entry in entries] == [
        "static-routing.json",
        "ubuntu-quickstart.json",
        "ubuntu-webtop.json",
    ]
    for entry in entries:
        assert read_lab_file(entry.path).success is True


def test_bundled_samples_match_repo_examples() -> None:
    """The samples shipped in the package are copies of the repo's examples/ files; keep
    them byte-identical so the two never drift apart. Only runs inside a dev checkout."""
    if not REPO_EXAMPLES_DIR.is_dir():
        return
    for example in sorted(REPO_EXAMPLES_DIR.glob("*.json")):
        bundled = SAMPLES_DIR / example.name
        assert bundled.is_file(), f"{example.name} is missing from the bundled samples"
        assert bundled.read_bytes() == example.read_bytes(), f"{example.name} differs"
