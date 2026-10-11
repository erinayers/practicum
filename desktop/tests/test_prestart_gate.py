from __future__ import annotations

from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QDialog

from practicum_desktop import prestart_gate
from practicum_desktop.api_client import (
    EstimatedResourcesInfo,
    ManualSectionInfo,
    ManualTaskInfo,
    PortCheckResult,
    PortConflict,
    PreviewResult,
    StartResult,
    TopologyInfo,
    TopologyInterfaceInfo,
)
from practicum_desktop.prestart_gate import PreStartGateDialog


class ImmediateWorker(QObject):
    """Runs the callable synchronously instead of on a QThread, so dialog tests don't
    need to wait on real background threads."""

    finished_call = Signal(object)

    def __init__(self, func, *args, **kwargs) -> None:
        super().__init__()
        self._func = func
        self._args = args
        self._kwargs = kwargs

    def start(self) -> None:
        self.finished_call.emit(self._func(*self._args, **self._kwargs))


class FakeApiClient:
    def __init__(self, preview=None, ports=None, start=None) -> None:
        self._preview = preview
        self._ports = ports
        self._start = start
        self.apply_calls: list[tuple[str, str, int, str]] = []
        self.start_calls: list[str] = []

    def get_preview(self, lab_id: str) -> PreviewResult:
        return self._preview

    def check_ports(self, lab_id: str) -> PortCheckResult:
        return self._ports

    def apply_port_recommendation(
        self, lab_id: str, node_id: str, host_port: int, protocol: str
    ) -> PortCheckResult:
        self.apply_calls.append((lab_id, node_id, host_port, protocol))
        return self._ports

    def start_lab(self, lab_id: str) -> StartResult:
        self.start_calls.append(lab_id)
        return self._start


def _preview(
    images: tuple[str, ...] = (), cpu: float | None = None, memory: int | None = None, manual_tasks: int = 0
) -> PreviewResult:
    sections = []
    if manual_tasks:
        sections = [
            ManualSectionInfo(
                id="s1",
                title="Section",
                content_markdown="",
                tasks=[
                    ManualTaskInfo(id=f"t{i}", text=f"Task {i}") for i in range(manual_tasks)
                ],
            )
        ]
    return PreviewResult(
        success=True,
        name="Static Routing",
        description="A 3-host topology.",
        author="You",
        version="0.1.0",
        required_images=list(images),
        estimated_resources=EstimatedResourcesInfo(total_cpu=cpu, total_memory_mb=memory),
        topology=TopologyInfo(
            interfaces=[TopologyInterfaceInfo(node="client", network="lan", address="10.0.1.10/24")]
        ),
        manual_sections=sections,
    )


def test_dialog_shows_preview_details(monkeypatch) -> None:
    monkeypatch.setattr(prestart_gate, "CallableWorker", ImmediateWorker)
    api = FakeApiClient(
        preview=_preview(images=("ubuntu:22.04",), cpu=1.0, memory=512, manual_tasks=2),
        ports=PortCheckResult(success=True, has_conflicts=False, conflicts=[]),
    )

    dialog = PreStartGateDialog(api, "lab-1")

    assert dialog.name_label.text() == "Static Routing"
    assert "ubuntu:22.04" in dialog.images_label.text()
    assert dialog.cpu_label.text() == "1.0 vCPU"
    assert dialog.memory_label.text() == "512 MB"
    assert dialog.topology_table.rowCount() == 1
    assert "2 steps" in dialog.manual_label.text()


def test_dialog_shows_no_manual_message_when_lab_has_none(monkeypatch) -> None:
    monkeypatch.setattr(prestart_gate, "CallableWorker", ImmediateWorker)
    api = FakeApiClient(
        preview=_preview(),
        ports=PortCheckResult(success=True, has_conflicts=False, conflicts=[]),
    )

    dialog = PreStartGateDialog(api, "lab-1")

    assert dialog.manual_label.text() == "This lab has no manual."


def test_start_disabled_with_conflicts_and_enabled_once_resolved(monkeypatch) -> None:
    monkeypatch.setattr(prestart_gate, "CallableWorker", ImmediateWorker)
    conflict = PortConflict(
        node_id="server",
        host_port=80,
        container_port=80,
        protocol="tcp",
        reason="in_use_on_host",
        recommended_port=8080,
    )
    api = FakeApiClient(
        preview=_preview(),
        ports=PortCheckResult(success=True, has_conflicts=True, conflicts=[conflict]),
    )

    dialog = PreStartGateDialog(api, "lab-1")

    assert dialog.start_button.isEnabled() is False
    assert dialog.conflicts_table.rowCount() == 1
    assert "1 port conflict" in dialog.conflicts_banner.text()

    api._ports = PortCheckResult(success=True, has_conflicts=False, conflicts=[])
    dialog._on_apply_recommendation(conflict)

    assert api.apply_calls == [("lab-1", "server", 80, "tcp")]
    assert dialog.start_button.isEnabled() is True
    assert dialog.conflicts_banner.text() == "No port conflicts detected."


def test_start_button_enabled_immediately_with_no_conflicts(monkeypatch) -> None:
    monkeypatch.setattr(prestart_gate, "CallableWorker", ImmediateWorker)
    api = FakeApiClient(
        preview=_preview(),
        ports=PortCheckResult(success=True, has_conflicts=False, conflicts=[]),
    )

    dialog = PreStartGateDialog(api, "lab-1")

    assert dialog.start_button.isEnabled() is True


def test_start_clicked_accepts_dialog_on_success(monkeypatch) -> None:
    monkeypatch.setattr(prestart_gate, "CallableWorker", ImmediateWorker)
    api = FakeApiClient(
        preview=_preview(),
        ports=PortCheckResult(success=True, has_conflicts=False, conflicts=[]),
        start=StartResult(success=True, detail="Lab started."),
    )

    dialog = PreStartGateDialog(api, "lab-1")
    dialog._on_start_clicked()

    assert api.start_calls == ["lab-1"]
    assert dialog.result() == QDialog.DialogCode.Accepted


def test_start_clicked_shows_error_and_stays_open_on_failure(monkeypatch) -> None:
    monkeypatch.setattr(prestart_gate, "CallableWorker", ImmediateWorker)
    api = FakeApiClient(
        preview=_preview(),
        ports=PortCheckResult(success=True, has_conflicts=False, conflicts=[]),
        start=StartResult(success=False, detail="Docker is not running."),
    )

    dialog = PreStartGateDialog(api, "lab-1")
    dialog._on_start_clicked()

    assert dialog.result() != QDialog.DialogCode.Accepted
    assert "Docker is not running." in dialog.status_label.text()
    assert dialog.start_button.isEnabled() is True
    assert dialog.cancel_button.isEnabled() is True


def test_cancel_rejects_dialog(monkeypatch) -> None:
    monkeypatch.setattr(prestart_gate, "CallableWorker", ImmediateWorker)
    api = FakeApiClient(
        preview=_preview(),
        ports=PortCheckResult(success=True, has_conflicts=False, conflicts=[]),
    )

    dialog = PreStartGateDialog(api, "lab-1")
    dialog.cancel_button.click()

    assert dialog.result() == QDialog.DialogCode.Rejected
