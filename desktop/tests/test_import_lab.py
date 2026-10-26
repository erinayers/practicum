from __future__ import annotations

import json
from pathlib import Path

import pytest
from PySide6.QtCore import QSettings, Qt
from PySide6.QtWidgets import QDialog
from qt_helpers import ImmediateWorker, StalledWorker

from practicum_desktop import import_lab
from practicum_desktop.api_client import (
    DockerEngineResult,
    FieldIssue,
    ImportLabResult,
    NetworkCheckResult,
    NodeProgressInfo,
    PortCheckResult,
    PortConflict,
    StartResult,
    StatusResult,
    SubnetConflict,
)
from practicum_desktop.import_lab import (
    API_UNAVAILABLE_MESSAGE,
    FILE_HINT_ROLE,
    MAX_RECENT_FILES,
    RECENT_FILES_KEY,
    STAGE_DONE,
    STAGE_FAILED,
    ImportLabDialog,
    RecentLabFiles,
)

VALID_LAB = {
    "name": "Static Routing",
    "nodes": [{"id": "a", "image": "alpine:3.21"}],
    "networks": [{"id": "lan", "subnet": "10.0.0.0/24"}],
    "interfaces": [{"node": "a", "network": "lan", "address": "10.0.0.10/24"}],
}


class FakeApiClient:
    def __init__(
        self,
        import_result: ImportLabResult | None = None,
        ports: PortCheckResult | None = None,
        start: StartResult | None = None,
        networks: NetworkCheckResult | None = None,
    ) -> None:
        self._import_result = import_result or ImportLabResult(
            success=True, lab_id="lab-1", lab_name="Static Routing"
        )
        self._ports = ports or PortCheckResult(success=True, has_conflicts=False)
        self._networks = networks or NetworkCheckResult(success=True, has_conflicts=False)
        self._start = start or StartResult(success=True, detail="Lab started.")
        self.engine = DockerEngineResult(success=True, available=True, os_type="linux")
        self.engine_calls = 0
        self.import_calls: list[dict] = []
        self.source_files: list[str | None] = []
        self.ports_calls: list[str] = []
        self.networks_calls: list[str] = []
        self.start_calls: list[str] = []
        self.start_waits: list[bool] = []
        self.status_calls: list[str] = []
        self._statuses: list[StatusResult] = []

    def check_networks(self, lab_id: str) -> NetworkCheckResult:
        self.networks_calls.append(lab_id)
        return self._networks

    def get_docker_engine(self) -> DockerEngineResult:
        self.engine_calls += 1
        return self.engine

    def import_lab(self, definition: dict, source_file: str | None = None) -> ImportLabResult:
        self.import_calls.append(definition)
        self.source_files.append(source_file)
        return self._import_result

    def check_ports(self, lab_id: str) -> PortCheckResult:
        self.ports_calls.append(lab_id)
        return self._ports

    def start_lab(self, lab_id: str, wait: bool = True) -> StartResult:
        self.start_calls.append(lab_id)
        self.start_waits.append(wait)
        return self._start

    def get_status(self, lab_id: str) -> StatusResult:
        self.status_calls.append(lab_id)
        if self._statuses:
            return self._statuses.pop(0)
        return StatusResult(success=True, lab_status="running")


@pytest.fixture
def settings(tmp_path: Path) -> QSettings:
    return QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)


@pytest.fixture
def lab_file(tmp_path: Path) -> Path:
    path = tmp_path / "static-routing.json"
    path.write_text(json.dumps(VALID_LAB), encoding="utf-8")
    return path


@pytest.fixture
def immediate(monkeypatch) -> None:
    monkeypatch.setattr(import_lab, "CallableWorker", ImmediateWorker)


def _pick_file(monkeypatch, path: Path | None) -> list:
    calls: list = []

    def fake_get_open_file_name(parent, caption, directory, filter_):
        calls.append((caption, directory, filter_))
        return (str(path) if path else "", filter_)

    monkeypatch.setattr(
        import_lab.QFileDialog, "getOpenFileName", staticmethod(fake_get_open_file_name)
    )
    return calls


def _row_text(dialog: ImportLabDialog, row: int) -> str:
    item = dialog.files_list.item(row)
    return f"{item.text()}\n{item.data(FILE_HINT_ROLE)}"


# ----- RecentLabFiles ------------------------------------------------------------------


def test_recent_files_start_empty(settings: QSettings) -> None:
    assert RecentLabFiles(settings).paths() == []


def test_recent_files_add_puts_newest_first_and_dedupes(
    settings: QSettings, tmp_path: Path
) -> None:
    recent = RecentLabFiles(settings)
    first, second = tmp_path / "first.json", tmp_path / "second.json"

    recent.add(first)
    recent.add(second)
    recent.add(first)

    assert recent.paths() == [first.resolve(), second.resolve()]


def test_recent_files_are_capped(settings: QSettings, tmp_path: Path) -> None:
    recent = RecentLabFiles(settings)
    for index in range(MAX_RECENT_FILES + 3):
        recent.add(tmp_path / f"lab-{index}.json")

    paths = recent.paths()

    assert len(paths) == MAX_RECENT_FILES
    assert paths[0] == (tmp_path / f"lab-{MAX_RECENT_FILES + 2}.json").resolve()


def test_recent_files_tolerates_single_string_value(settings: QSettings, tmp_path: Path) -> None:
    settings.setValue(RECENT_FILES_KEY, str(tmp_path / "only.json"))

    assert RecentLabFiles(settings).paths() == [tmp_path / "only.json"]


# ----- choosing a file ------------------------------------------------------------------


def test_dialog_lists_bundled_samples_with_open_disabled(settings: QSettings) -> None:
    dialog = ImportLabDialog(FakeApiClient(), settings)

    names = [_row_text(dialog, i).splitlines()[0] for i in range(dialog.files_list.count())]
    assert names == [
        "static-routing.json",
        "ubuntu-quickstart.json",
        "ubuntu-webtop.json",
        "windows-quickstart.json",
    ]
    assert dialog.open_button.isEnabled() is False
    assert dialog.api_banner.isHidden() is True


def test_dialog_lists_recent_files_first_and_disables_missing_ones(
    settings: QSettings, lab_file: Path, tmp_path: Path
) -> None:
    recent = RecentLabFiles(settings)
    recent.add(tmp_path / "moved-away.json")
    recent.add(lab_file)

    dialog = ImportLabDialog(FakeApiClient(), settings)

    second = dialog.files_list.item(1)
    assert _row_text(dialog, 0) == f"static-routing.json\nRecent · {lab_file.stat().st_size} B"
    assert _row_text(dialog, 1) == "moved-away.json\nRecent · file not found"
    assert bool(second.flags() & Qt.ItemFlag.ItemIsEnabled) is False
    assert dialog.files_list.count() == 2 + 4  # recent + bundled samples


def test_selecting_an_existing_row_enables_open(settings: QSettings, lab_file: Path) -> None:
    RecentLabFiles(settings).add(lab_file)
    dialog = ImportLabDialog(FakeApiClient(), settings)

    dialog.files_list.setCurrentRow(0)

    assert dialog.open_button.isEnabled() is True
    assert dialog.selected_entry().path == lab_file.resolve()


def test_browse_cancelled_leaves_dialog_on_chooser(settings: QSettings, monkeypatch) -> None:
    _pick_file(monkeypatch, None)
    dialog = ImportLabDialog(FakeApiClient(), settings)

    dialog.browse_button.click()

    assert dialog.stack.currentIndex() == 0
    assert dialog.outcome is None


def test_browse_uses_system_picker_with_json_filter(
    settings: QSettings, lab_file: Path, monkeypatch, immediate
) -> None:
    calls = _pick_file(monkeypatch, lab_file)
    dialog = ImportLabDialog(FakeApiClient(), settings)

    dialog.browse_button.click()

    caption, directory, filter_ = calls[0]
    assert caption == "Open Lab File"
    assert directory == str(Path.home())
    assert "*.json" in filter_
    assert dialog.stack.currentIndex() == 1


def test_dialog_blocks_import_when_api_unavailable(settings: QSettings, lab_file: Path) -> None:
    RecentLabFiles(settings).add(lab_file)
    dialog = ImportLabDialog(FakeApiClient(), settings, api_available=False)

    dialog.files_list.setCurrentRow(0)

    assert dialog.api_banner.isHidden() is False
    assert dialog.api_banner.text() == API_UNAVAILABLE_MESSAGE
    assert dialog.browse_button.isEnabled() is False
    assert dialog.open_button.isEnabled() is False


# ----- the staged flow --------------------------------------------------------------------


def test_conflict_free_import_starts_lab_and_accepts(
    settings: QSettings, lab_file: Path, monkeypatch, immediate
) -> None:
    _pick_file(monkeypatch, lab_file)
    api = FakeApiClient()
    dialog = ImportLabDialog(api, settings)

    dialog.browse_button.click()

    assert api.import_calls == [VALID_LAB]
    assert api.ports_calls == ["lab-1"]
    assert api.networks_calls == ["lab-1"]
    assert api.start_calls == ["lab-1"]
    assert dialog.outcome is not None
    assert dialog.outcome.lab_id == "lab-1"
    assert dialog.outcome.lab_name == "Static Routing"
    assert dialog.outcome.source_path == lab_file
    assert dialog.outcome.started is True
    assert dialog.outcome.gate_required is False
    assert dialog.result() == QDialog.DialogCode.Accepted
    assert dialog.stage_label.text() == STAGE_DONE
    assert dialog.progress_bar.value() == 100
    assert RecentLabFiles(settings).paths() == [lab_file.resolve()]


def test_open_button_imports_selected_recent_file(
    settings: QSettings, lab_file: Path, immediate
) -> None:
    RecentLabFiles(settings).add(lab_file)
    api = FakeApiClient()
    dialog = ImportLabDialog(api, settings)

    dialog.files_list.setCurrentRow(0)
    dialog.open_button.click()

    assert api.import_calls == [VALID_LAB]
    assert dialog.outcome is not None and dialog.outcome.started is True


def test_import_with_conflicts_stops_for_the_gate_without_starting(
    settings: QSettings, lab_file: Path, monkeypatch, immediate
) -> None:
    _pick_file(monkeypatch, lab_file)
    conflict = PortConflict(
        node_id="a",
        host_port=80,
        container_port=80,
        protocol="tcp",
        reason="in_use_on_host",
        recommended_port=8080,
    )
    api = FakeApiClient(
        ports=PortCheckResult(success=True, has_conflicts=True, conflicts=[conflict])
    )
    dialog = ImportLabDialog(api, settings)

    dialog.browse_button.click()

    assert api.start_calls == []
    assert dialog.outcome is not None
    assert dialog.outcome.gate_required is True
    assert dialog.outcome.started is False
    assert dialog.result() == QDialog.DialogCode.Accepted


def test_subnet_conflict_stops_for_the_gate_without_starting(
    settings: QSettings, lab_file: Path, monkeypatch, immediate
) -> None:
    _pick_file(monkeypatch, lab_file)
    conflict = SubnetConflict(
        network_id="lan",
        subnet="10.0.0.0/24",
        reason="overlaps_leftover",
        owner_network_name="practicum-deadbeef-lan",
        owner_subnet="10.0.0.0/24",
        owner_lab_id="deadbeef",
        owner_container_count=1,
        recommended_subnet="10.90.0.0/24",
    )
    api = FakeApiClient(
        networks=NetworkCheckResult(success=True, has_conflicts=True, conflicts=[conflict])
    )
    dialog = ImportLabDialog(api, settings)

    dialog.browse_button.click()

    assert api.networks_calls == ["lab-1"]
    assert api.start_calls == []
    assert dialog.outcome is not None and dialog.outcome.gate_required is True
    assert dialog.result() == QDialog.DialogCode.Accepted


def test_unanswerable_network_check_defers_to_the_gate(
    settings: QSettings, lab_file: Path, monkeypatch, immediate
) -> None:
    _pick_file(monkeypatch, lab_file)
    api = FakeApiClient(networks=NetworkCheckResult(success=False, detail="Docker is down"))
    dialog = ImportLabDialog(api, settings)

    dialog.browse_button.click()

    assert api.start_calls == []
    assert dialog.outcome is not None and dialog.outcome.gate_required is True


def test_failed_port_check_defers_to_the_gate(
    settings: QSettings, lab_file: Path, monkeypatch, immediate
) -> None:
    _pick_file(monkeypatch, lab_file)
    api = FakeApiClient(ports=PortCheckResult(success=False, detail="Could not check ports"))
    dialog = ImportLabDialog(api, settings)

    dialog.browse_button.click()

    assert api.start_calls == []
    assert dialog.outcome is not None and dialog.outcome.gate_required is True
    assert dialog.result() == QDialog.DialogCode.Accepted


def test_windows_lab_on_a_linux_engine_defers_to_the_gate_instead_of_starting(
    settings: QSettings, lab_file: Path, monkeypatch, immediate
) -> None:
    _pick_file(monkeypatch, lab_file)
    api = FakeApiClient(
        import_result=ImportLabResult(
            success=True, lab_id="lab-w", lab_name="Windows Quick Start", container_os="windows"
        )
    )
    dialog = ImportLabDialog(api, settings)

    dialog.browse_button.click()

    assert api.engine_calls == 1
    assert api.start_calls == []  # never a blind start that fails with a Docker error
    assert dialog.outcome is not None
    assert dialog.outcome.container_os == "windows"
    assert dialog.outcome.gate_required is True
    assert dialog.result() == QDialog.DialogCode.Accepted


def test_matching_engine_mode_starts_the_imported_lab(
    settings: QSettings, lab_file: Path, monkeypatch, immediate
) -> None:
    _pick_file(monkeypatch, lab_file)
    api = FakeApiClient(
        import_result=ImportLabResult(
            success=True, lab_id="lab-w", lab_name="Windows Quick Start", container_os="windows"
        )
    )
    api.engine = DockerEngineResult(success=True, available=True, os_type="windows")
    dialog = ImportLabDialog(api, settings)

    dialog.browse_button.click()

    assert api.start_calls == ["lab-w"]
    assert dialog.outcome is not None and dialog.outcome.started is True


def test_unreachable_docker_at_import_defers_to_the_gate(
    settings: QSettings, lab_file: Path, monkeypatch, immediate
) -> None:
    _pick_file(monkeypatch, lab_file)
    api = FakeApiClient()
    api.engine = DockerEngineResult(success=True, available=False, detail="Docker is not running.")
    dialog = ImportLabDialog(api, settings)

    dialog.browse_button.click()

    assert api.start_calls == []
    assert dialog.outcome is not None and dialog.outcome.gate_required is True


def test_malformed_file_shows_specific_error_and_never_reaches_api(
    settings: QSettings, tmp_path: Path, monkeypatch, immediate
) -> None:
    broken = tmp_path / "broken.json"
    broken.write_text('{"name": ', encoding="utf-8")
    _pick_file(monkeypatch, broken)
    api = FakeApiClient()
    dialog = ImportLabDialog(api, settings)

    dialog.browse_button.click()

    assert api.import_calls == []
    assert dialog.outcome is None
    assert dialog.result() != QDialog.DialogCode.Accepted
    assert dialog.stage_label.text() == STAGE_FAILED
    assert "broken.json" in dialog.detail_label.text()
    assert "not valid JSON" in dialog.detail_label.text()
    assert dialog.errors_box.isHidden() is True
    assert dialog.back_button.isHidden() is False
    assert dialog.close_button.isEnabled() is True
    assert RecentLabFiles(settings).paths() == []


def test_zip_file_is_rejected_with_guidance(
    settings: QSettings, tmp_path: Path, monkeypatch, immediate
) -> None:
    bundle = tmp_path / "python-api-lab.zip"
    bundle.write_bytes(b"PK\x03\x04")
    _pick_file(monkeypatch, bundle)
    api = FakeApiClient()
    dialog = ImportLabDialog(api, settings)

    dialog.browse_button.click()

    assert api.import_calls == []
    assert "Bundles aren't supported yet" in dialog.detail_label.text()


def test_schema_errors_from_api_are_listed_inline(
    settings: QSettings, lab_file: Path, monkeypatch, immediate
) -> None:
    _pick_file(monkeypatch, lab_file)
    api = FakeApiClient(
        import_result=ImportLabResult(
            success=False,
            errors=[
                FieldIssue(
                    location=["nodes", "0", "image"], message="Field required", issue_type="missing"
                ),
                FieldIssue(
                    location=[],
                    message="Value error, node ids must be unique",
                    issue_type="value_error",
                ),
            ],
            detail="The lab file is not a valid Practicum lab.",
        )
    )
    dialog = ImportLabDialog(api, settings)

    dialog.browse_button.click()

    assert api.ports_calls == []
    assert api.start_calls == []
    assert dialog.outcome is None
    assert "not a valid Practicum lab" in dialog.detail_label.text()
    assert dialog.errors_box.isHidden() is False
    assert dialog.errors_box.toPlainText() == (
        "• nodes[0].image: Field required\n• node ids must be unique"
    )
    assert dialog.back_button.isHidden() is False
    assert RecentLabFiles(settings).paths() == []


def test_api_transport_failure_is_explained(
    settings: QSettings, lab_file: Path, monkeypatch, immediate
) -> None:
    _pick_file(monkeypatch, lab_file)
    api = FakeApiClient(
        import_result=ImportLabResult(
            success=False, detail="Could not connect to the Practicum API to import the lab."
        )
    )
    dialog = ImportLabDialog(api, settings)

    dialog.browse_button.click()

    assert dialog.outcome is None
    assert "Could not connect to the Practicum API" in dialog.detail_label.text()
    assert dialog.errors_box.isHidden() is True


def test_start_failure_keeps_imported_lab_and_explains(
    settings: QSettings, lab_file: Path, monkeypatch, immediate
) -> None:
    _pick_file(monkeypatch, lab_file)
    api = FakeApiClient(start=StartResult(success=False, detail="Docker is not running."))
    dialog = ImportLabDialog(api, settings)

    dialog.browse_button.click()

    assert api.start_calls == ["lab-1"]
    assert dialog.outcome is not None
    assert dialog.outcome.lab_id == "lab-1"
    assert dialog.outcome.started is False
    assert dialog.outcome.gate_required is False
    assert dialog.result() != QDialog.DialogCode.Accepted
    assert "could not be started: Docker is not running." in dialog.detail_label.text()
    assert "use Start on its card" in dialog.detail_label.text()
    assert dialog.back_button.isHidden() is True
    assert dialog.close_button.isEnabled() is True
    assert RecentLabFiles(settings).paths() == [lab_file.resolve()]


def test_import_passes_the_file_name_and_starts_without_waiting(
    settings: QSettings, lab_file: Path, monkeypatch, immediate
) -> None:
    _pick_file(monkeypatch, lab_file)
    api = FakeApiClient()
    dialog = ImportLabDialog(api, settings)

    dialog.browse_button.click()

    assert api.source_files == ["static-routing.json"]
    assert api.start_waits == [False]


def test_pending_start_polls_status_and_renders_real_progress(
    settings: QSettings, lab_file: Path, monkeypatch, immediate
) -> None:
    _pick_file(monkeypatch, lab_file)
    api = FakeApiClient(start=StartResult(success=True, detail="Start requested.", pending=True))
    pulling = StatusResult(
        success=True,
        lab_status="starting",
        progress=[
            NodeProgressInfo(
                "a", "alpine:3.21", "pulling_image", percent=50, detail="2 of 4 layers"
            )
        ],
    )
    done = StatusResult(
        success=True,
        lab_status="running",
        progress=[NodeProgressInfo("a", "alpine:3.21", "ready")],
    )
    api._statuses = [pulling, done]
    dialog = ImportLabDialog(api, settings)

    dialog.browse_button.click()  # start → pending → first poll (pulling) → timer armed

    assert api.status_calls == ["lab-1"]
    assert "Downloading alpine:3.21" in dialog.stage_label.text()
    assert "50%" in dialog.stage_label.text()
    assert 60 < dialog.progress_bar.value() < 100
    assert dialog.close_button.isEnabled() is False  # still busy
    assert dialog.outcome.started is False

    dialog._poll_start_status()  # what the timer would do next

    assert api.status_calls == ["lab-1", "lab-1"]
    assert dialog.outcome.started is True
    assert dialog.result() == QDialog.DialogCode.Accepted
    assert dialog.progress_bar.value() == 100


def test_pending_start_failure_is_attributed_to_the_node(
    settings: QSettings, lab_file: Path, monkeypatch, immediate
) -> None:
    _pick_file(monkeypatch, lab_file)
    api = FakeApiClient(start=StartResult(success=True, detail="Start requested.", pending=True))
    api._statuses = [
        StatusResult(
            success=True,
            lab_status="error",
            last_error="node 'a' (alpine:3.21): could not pull image 'alpine:3.21': not found",
            progress=[NodeProgressInfo("a", "alpine:3.21", "failed", detail="could not pull")],
        )
    ]
    dialog = ImportLabDialog(api, settings)

    dialog.browse_button.click()

    assert dialog.outcome.started is False
    assert dialog.result() != QDialog.DialogCode.Accepted
    assert "could not pull image 'alpine:3.21'" in dialog.detail_label.text()
    assert dialog.close_button.isEnabled() is True


def test_choose_another_file_returns_to_chooser(
    settings: QSettings, tmp_path: Path, monkeypatch, immediate
) -> None:
    broken = tmp_path / "broken.json"
    broken.write_text("nope", encoding="utf-8")
    _pick_file(monkeypatch, broken)
    dialog = ImportLabDialog(FakeApiClient(), settings)
    dialog.browse_button.click()

    dialog.back_button.click()

    assert dialog.stack.currentIndex() == 0
    assert dialog.open_button.isEnabled() is False


def test_dialog_cannot_be_closed_while_a_stage_is_in_flight(
    settings: QSettings, lab_file: Path, monkeypatch
) -> None:
    monkeypatch.setattr(import_lab, "CallableWorker", StalledWorker)
    StalledWorker.instances.clear()
    _pick_file(monkeypatch, lab_file)
    dialog = ImportLabDialog(FakeApiClient(), settings)
    dialog.show()

    dialog.browse_button.click()  # read stage is now pending
    dialog.reject()
    dialog.close()

    assert dialog.isVisible() is True
    assert dialog.close_button.isEnabled() is False

    # Let every pending stage complete: read -> import -> ports -> start.
    while StalledWorker.instances:
        StalledWorker.instances.pop(0).finish()

    assert dialog.outcome is not None and dialog.outcome.started is True
    assert dialog.isVisible() is False
