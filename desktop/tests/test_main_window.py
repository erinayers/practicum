from __future__ import annotations

from pathlib import Path
from typing import ClassVar

import pytest
from PySide6.QtCore import QObject, QSettings, Signal
from PySide6.QtWidgets import QDialog
from qt_helpers import ImmediateWorker

from practicum_desktop import main_window
from practicum_desktop.api_client import (
    HealthStatus,
    LabsResult,
    LabSummary,
    PortCheckResult,
    PreviewResult,
    ResourceStatusInfo,
    StatusResult,
)
from practicum_desktop.app_status import AppStatus
from practicum_desktop.docker_status import DockerStatus
from practicum_desktop.import_lab import ImportOutcome
from practicum_desktop.main_window import MainWindow
from practicum_desktop.node_shell import ShellLaunchResult


def _ready_status() -> AppStatus:
    return AppStatus(
        readiness="ready",
        api=HealthStatus(reachable=True, healthy=True, detail="The Practicum API is healthy."),
        docker=DockerStatus(available=True, detail="Docker is available."),
        next_action="Ready.",
    )


class FakeApiClient:
    """Serves a mutable lab list so tests can make a lab 'appear' after an import."""

    def __init__(self) -> None:
        self.labs: list[LabSummary] = []
        self.base_url = "http://127.0.0.1:8000"

    def list_labs(self) -> LabsResult:
        return LabsResult(success=True, labs=list(self.labs))

    def check_ports(self, lab_id: str) -> PortCheckResult:
        return PortCheckResult(success=True, has_conflicts=False)

    def get_preview(self, lab_id: str) -> PreviewResult:
        return PreviewResult(success=True, name=f"Lab {lab_id}")

    def get_status(self, lab_id: str) -> StatusResult:
        lab = next((lab for lab in self.labs if lab.id == lab_id), None)
        running = lab is not None and lab.status == "running"
        return StatusResult(
            success=True,
            lab_status=lab.status if lab else "",
            resources=[
                ResourceStatusInfo(
                    kind="network",
                    id="lan",
                    name=f"practicum-{lab_id}-lan",
                    exists=running,
                    status="present",
                ),
                ResourceStatusInfo(
                    kind="container",
                    id="host-a",
                    name=f"practicum-{lab_id}-host-a",
                    exists=running,
                    status="running" if running else None,
                ),
                ResourceStatusInfo(
                    kind="container",
                    id="host-b",
                    name=f"practicum-{lab_id}-host-b",
                    exists=running,
                    status="running" if running else None,
                ),
            ],
        )


class FakeStartupWorker(QObject):
    finished_check = Signal(object, object)

    def __init__(self, api_client, parent=None) -> None:
        super().__init__()
        self._api_client = api_client

    def start(self) -> None:
        self.finished_check.emit(_ready_status(), self._api_client.list_labs())


class FakeImportDialog:
    """Stands in for ImportLabDialog: yields a preset outcome without any UI."""

    outcome_to_return: ImportOutcome | None = None
    last_kwargs: ClassVar[dict] = {}

    def __init__(self, api_client, settings, parent=None, api_available=True) -> None:
        FakeImportDialog.last_kwargs = {"api_available": api_available}
        self.outcome = FakeImportDialog.outcome_to_return

    def exec(self) -> int:
        return int(QDialog.DialogCode.Accepted if self.outcome else QDialog.DialogCode.Rejected)


class FakeGateDialog:
    result_to_return = QDialog.DialogCode.Accepted
    opened_for: ClassVar[list[str]] = []
    DialogCode = QDialog.DialogCode

    def __init__(self, api_client, lab_id, parent=None) -> None:
        FakeGateDialog.opened_for.append(lab_id)

    def exec(self) -> int:
        return int(FakeGateDialog.result_to_return)


@pytest.fixture
def window(monkeypatch, tmp_path: Path):
    api = FakeApiClient()
    monkeypatch.setattr(main_window, "ApiClient", lambda base_url: api)
    monkeypatch.setattr(
        main_window,
        "QSettings",
        lambda org, app: QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat),
    )
    monkeypatch.setattr(main_window, "StartupWorker", FakeStartupWorker)
    monkeypatch.setattr(main_window, "CallableWorker", ImmediateWorker)
    monkeypatch.setattr(main_window, "ImportLabDialog", FakeImportDialog)
    monkeypatch.setattr(main_window, "PreStartGateDialog", FakeGateDialog)
    FakeImportDialog.outcome_to_return = None
    FakeGateDialog.opened_for = []
    FakeGateDialog.result_to_return = QDialog.DialogCode.Accepted

    win = MainWindow()
    win.api = api
    return win


def _lab_added(window: MainWindow, lab_id: str, name: str, status: str = "running") -> None:
    window.api.labs.append(LabSummary(id=lab_id, name=name, status=status))


def test_window_has_import_button_next_to_new_lab(window: MainWindow) -> None:
    assert window.import_button.text() == "Import Lab File…"
    assert window.import_button.isEnabled() is True


def test_cancelled_import_changes_nothing(window: MainWindow) -> None:
    FakeImportDialog.outcome_to_return = None

    window.import_button.click()

    assert window.labs_list.count() == 1  # "No labs defined yet." placeholder
    assert FakeGateDialog.opened_for == []
    assert window.start_result_label.text() == ""


def test_started_import_selects_lab_and_opens_manual(window: MainWindow, tmp_path: Path) -> None:
    FakeImportDialog.outcome_to_return = ImportOutcome(
        lab_id="lab-9", lab_name="Static Routing", source_path=tmp_path / "s.json", started=True
    )
    _lab_added(window, "lab-9", "Static Routing")

    window.import_button.click()

    assert FakeGateDialog.opened_for == []
    assert window.labs_list.currentRow() == 0
    assert window.labs_list.item(0).text() == "Static Routing (running)"
    assert window._selected_lab_id == "lab-9"
    assert window.start_result_label.text() == "✅ 'Static Routing' imported and started."
    assert window.manual_flyout.isHidden() is False
    assert FakeImportDialog.last_kwargs == {"api_available": True}


def test_import_with_conflicts_opens_gate_and_reports_start(
    window: MainWindow, tmp_path: Path
) -> None:
    FakeImportDialog.outcome_to_return = ImportOutcome(
        lab_id="lab-2", lab_name="Web Lab", source_path=tmp_path / "w.json", gate_required=True
    )
    _lab_added(window, "other", "Other Lab", status="defined")
    _lab_added(window, "lab-2", "Web Lab")

    window.import_button.click()

    assert FakeGateDialog.opened_for == ["lab-2"]
    assert window.labs_list.currentRow() == 1
    assert window.start_result_label.text() == "✅ 'Web Lab' imported and started."


def test_import_with_conflicts_cancelled_at_gate_keeps_lab_listed(
    window: MainWindow, tmp_path: Path
) -> None:
    FakeImportDialog.outcome_to_return = ImportOutcome(
        lab_id="lab-2", lab_name="Web Lab", source_path=tmp_path / "w.json", gate_required=True
    )
    FakeGateDialog.result_to_return = QDialog.DialogCode.Rejected
    _lab_added(window, "lab-2", "Web Lab", status="defined")

    window.import_button.click()

    assert FakeGateDialog.opened_for == ["lab-2"]
    assert window.labs_list.item(0).text() == "Web Lab (defined)"
    assert window.labs_list.currentRow() == 0
    assert window.start_result_label.text() == (
        "'Web Lab' imported. Select it below and use Start when ready."
    )
    assert window.manual_flyout.isHidden() is True


def test_imported_but_not_started_lab_is_listed_and_selected(
    window: MainWindow, tmp_path: Path
) -> None:
    FakeImportDialog.outcome_to_return = ImportOutcome(
        lab_id="lab-3", lab_name="", source_path=tmp_path / "from-disk.json"
    )
    _lab_added(window, "lab-3", "From Disk", status="error")

    window.import_button.click()

    assert FakeGateDialog.opened_for == []
    assert window.labs_list.currentRow() == 0
    assert "'from-disk.json' imported." in window.start_result_label.text()


def test_import_dialog_is_told_when_api_is_unavailable(window: MainWindow) -> None:
    window._last_status = AppStatus(
        readiness="blocked",
        api=HealthStatus(reachable=False, healthy=False, detail="down"),
        docker=DockerStatus(available=True, detail="ok"),
        next_action="Start the API.",
    )

    window.import_button.click()

    assert FakeImportDialog.last_kwargs == {"api_available": False}


# ----- Lab Nodes / Open shell ---------------------------------------------------------------


def test_selecting_running_lab_lists_nodes_with_open_shell(window: MainWindow) -> None:
    _lab_added(window, "lab-1", "Routing", status="running")
    window.check_status()

    window.labs_list.setCurrentRow(0)

    table = window.nodes_table
    assert table.rowCount() == 2  # containers only, the network is not listed
    assert table.item(0, 0).text() == "host-a"
    assert table.item(0, 1).text() == "practicum-lab-1-host-a"
    assert table.item(0, 2).text() == "running"
    assert table.cellWidget(0, 3).text() == "Open shell"
    assert table.cellWidget(0, 3).isEnabled() is True
    assert "2 of 2 nodes running" in window.nodes_status_label.text()


def test_selecting_stopped_lab_disables_open_shell(window: MainWindow) -> None:
    _lab_added(window, "lab-1", "Routing", status="defined")
    window.check_status()

    window.labs_list.setCurrentRow(0)

    assert window.nodes_table.item(0, 2).text() == "not created"
    assert window.nodes_table.cellWidget(0, 3).isEnabled() is False
    assert "Start the lab" in window.nodes_status_label.text()


def test_open_shell_launches_for_that_container(window: MainWindow, monkeypatch) -> None:
    launched: list[tuple[str, str]] = []
    monkeypatch.setattr(
        main_window,
        "open_node_shell",
        lambda name, node: launched.append((name, node)) or ShellLaunchResult(True, "Opened."),
    )
    _lab_added(window, "lab-1", "Routing", status="running")
    window.check_status()
    window.labs_list.setCurrentRow(0)

    window.nodes_table.cellWidget(1, 3).click()

    assert launched == [("practicum-lab-1-host-b", "host-b")]
    assert window.nodes_status_label.text() == "Opened."


def test_open_shell_failure_shows_copyable_command(window: MainWindow, monkeypatch) -> None:
    monkeypatch.setattr(
        main_window,
        "open_node_shell",
        lambda name, node: ShellLaunchResult(
            False, "No terminal found.", command=["docker", "exec", "-it", name, "sh"]
        ),
    )
    _lab_added(window, "lab-1", "Routing", status="running")
    window.check_status()
    window.labs_list.setCurrentRow(0)

    window.nodes_table.cellWidget(0, 3).click()

    assert window.nodes_status_label.text() == (
        "No terminal found.\ndocker exec -it practicum-lab-1-host-a sh"
    )
