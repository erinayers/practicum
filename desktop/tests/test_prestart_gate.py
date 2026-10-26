from __future__ import annotations

from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QDialog, QLineEdit, QPushButton

from practicum_desktop import prestart_gate
from practicum_desktop.api_client import (
    DockerEngineResult,
    EstimatedResourcesInfo,
    ManualSectionInfo,
    ManualTaskInfo,
    NetworkCheckResult,
    NodeProgressInfo,
    PortCheckResult,
    PortConflict,
    PreviewResult,
    StartResult,
    StatusResult,
    SubnetConflict,
    TopologyInfo,
    TopologyInterfaceInfo,
    TopologyNetworkInfo,
    TopologyNodeInfo,
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

    def isRunning(self) -> bool:
        return False


LINUX_ENGINE = DockerEngineResult(
    success=True, available=True, os_type="linux", server_version="27.3.1"
)
WINDOWS_ENGINE = DockerEngineResult(
    success=True, available=True, os_type="windows", server_version="27.3.1", host_build=22631
)
NO_ENGINE = DockerEngineResult(success=True, available=False, detail="Docker is not running.")


class FakeApiClient:
    def __init__(
        self, preview=None, ports=None, start=None, networks=None, engine=LINUX_ENGINE
    ) -> None:
        self._preview = preview
        self._ports = ports
        self._start = start
        self._networks = networks or NetworkCheckResult(success=True, has_conflicts=False)
        self.engine = engine
        self.engine_calls = 0
        self.custom_port_result: PortCheckResult | None = None
        self.apply_calls: list[tuple[str, str, int, str]] = []
        self.start_calls: list[str] = []
        self.subnet_apply_calls: list[tuple[str, str]] = []
        self.remove_leftover_calls: list[tuple[str, str]] = []
        self.reset_calls: list[str] = []
        self.reset_result = StartResult(success=True, detail="Lab reset.")
        self.start_waits: list[bool] = []
        self.status_calls: list[str] = []
        self.statuses: list[StatusResult] = []

    def check_networks(self, lab_id: str) -> NetworkCheckResult:
        return self._networks

    def get_docker_engine(self) -> DockerEngineResult:
        self.engine_calls += 1
        return self.engine

    def apply_subnet_recommendation(self, lab_id: str, network_id: str) -> NetworkCheckResult:
        self.subnet_apply_calls.append((lab_id, network_id))
        return self._networks

    def remove_leftover_network(self, lab_id: str, network_name: str) -> NetworkCheckResult:
        self.remove_leftover_calls.append((lab_id, network_name))
        return self._networks

    def reset_lab(self, lab_id: str) -> StartResult:
        self.reset_calls.append(lab_id)
        return self.reset_result

    def get_preview(self, lab_id: str) -> PreviewResult:
        return self._preview

    def check_ports(self, lab_id: str) -> PortCheckResult:
        return self._ports

    def apply_port_recommendation(
        self, lab_id: str, node_id: str, host_port: int, protocol: str, new_host_port=None
    ) -> PortCheckResult:
        self.apply_calls.append((lab_id, node_id, host_port, protocol, new_host_port))
        if new_host_port is not None and self.custom_port_result is not None:
            return self.custom_port_result
        return self._ports

    def start_lab(self, lab_id: str, wait: bool = True) -> StartResult:
        self.start_calls.append(lab_id)
        self.start_waits.append(wait)
        return self._start

    def get_status(self, lab_id: str) -> StatusResult:
        self.status_calls.append(lab_id)
        if self.statuses:
            return self.statuses.pop(0)
        return StatusResult(success=True, lab_status="running")


def _preview(
    images: tuple[str, ...] = (),
    cpu: float | None = None,
    memory: int | None = None,
    manual_tasks: int = 0,
    container_os: str = "linux",
) -> PreviewResult:
    sections = []
    if manual_tasks:
        sections = [
            ManualSectionInfo(
                id="s1",
                title="Section",
                content_markdown="",
                tasks=[ManualTaskInfo(id=f"t{i}", text=f"Task {i}") for i in range(manual_tasks)],
            )
        ]
    return PreviewResult(
        success=True,
        name="Static Routing",
        description="A 3-host topology.",
        author="You",
        version="0.1.0",
        container_os=container_os,
        required_images=list(images),
        estimated_resources=EstimatedResourcesInfo(total_cpu=cpu, total_memory_mb=memory),
        topology=TopologyInfo(
            nodes=[TopologyNodeInfo(id="client", image="alpine")],
            networks=[TopologyNetworkInfo(id="lan", subnet="10.0.1.0/24")],
            interfaces=[
                TopologyInterfaceInfo(node="client", network="lan", address="10.0.1.10/24")
            ],
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
    assert [chip.text() for chip in dialog.image_chips] == ["ubuntu:22.04"]
    assert dialog.cpu_label.text() == "1.0 vCPU"
    assert dialog.memory_label.text() == "512 MB"
    assert len(dialog.topology_canvas.view.links_of("client")) == 1
    assert dialog.topology_canvas.view.connector_network("client", "client").id == "lan"
    assert "2 steps" in dialog.manual_label.text()
    assert dialog.status_pill.text_label.text() == "Ready to start"
    assert (
        dialog.engine_banner.text() == "Docker Desktop serves Linux containers, as this lab needs."
    )
    assert dialog.engine_banner.property("banner") == "ok"
    assert api.engine_calls == 1


# ----- container engine mode (windows-desktop-windows-container-readiness) --------------------


def test_windows_lab_on_a_linux_engine_blocks_start_until_retry_sees_windows_mode(
    monkeypatch,
) -> None:
    monkeypatch.setattr(prestart_gate, "CallableWorker", ImmediateWorker)
    api = FakeApiClient(
        preview=_preview(
            images=("mcr.microsoft.com/windows/servercore:ltsc2022",), container_os="windows"
        ),
        ports=PortCheckResult(success=True, has_conflicts=False, conflicts=[]),
        engine=LINUX_ENGINE,
    )

    dialog = PreStartGateDialog(api, "lab-1")

    assert dialog.start_button.isEnabled() is False
    assert dialog.conflicts_banner.text() == "No port conflicts detected."  # not the reason
    banner = dialog.engine_banner.text()
    assert "needs Windows containers" in banner
    assert "serving Linux containers" in banner
    assert "Switch to Windows containers" in banner
    assert "never switches the mode" in banner
    assert dialog.engine_banner.property("banner") == "warn"
    assert (
        dialog.status_pill.text_label.text()
        == "Switch Docker Desktop's container mode to continue"
    )

    api.engine = WINDOWS_ENGINE  # the user switched Docker Desktop and presses Retry
    dialog.engine_retry_button.click()

    assert api.engine_calls == 2
    assert (
        dialog.engine_banner.text()
        == "Docker Desktop serves Windows containers, as this lab needs."
    )
    assert dialog.engine_banner.property("banner") == "ok"
    assert dialog.start_button.isEnabled() is True
    assert dialog.status_pill.text_label.text() == "Ready to start"


def test_linux_lab_on_a_windows_engine_is_blocked_with_the_switch_back_hint(monkeypatch) -> None:
    monkeypatch.setattr(prestart_gate, "CallableWorker", ImmediateWorker)
    api = FakeApiClient(
        preview=_preview(),
        ports=PortCheckResult(success=True, has_conflicts=False, conflicts=[]),
        engine=WINDOWS_ENGINE,
    )

    dialog = PreStartGateDialog(api, "lab-1")

    assert dialog.start_button.isEnabled() is False
    assert "needs Linux containers" in dialog.engine_banner.text()
    assert "Switch to Linux containers" in dialog.engine_banner.text()


def test_unreachable_docker_blocks_start_from_the_engine_check(monkeypatch) -> None:
    monkeypatch.setattr(prestart_gate, "CallableWorker", ImmediateWorker)
    api = FakeApiClient(
        preview=_preview(),
        ports=PortCheckResult(success=True, has_conflicts=False, conflicts=[]),
        engine=NO_ENGINE,
    )

    dialog = PreStartGateDialog(api, "lab-1")

    assert dialog.start_button.isEnabled() is False
    assert "Docker is not reachable: Docker is not running." in dialog.engine_banner.text()
    assert dialog.engine_banner.property("banner") == "error"

    api.engine = DockerEngineResult(success=False, detail="Could not check Docker: boom")
    dialog.engine_retry_button.click()
    assert "Could not check the Docker engine" in dialog.engine_banner.text()
    assert dialog.start_button.isEnabled() is False


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
    assert len(dialog.conflict_rows) == 1
    assert "1 port conflict" in dialog.conflicts_banner.text()

    api._ports = PortCheckResult(success=True, has_conflicts=False, conflicts=[])
    dialog._on_apply_recommendation(conflict)

    assert api.apply_calls == [("lab-1", "server", 80, "tcp", None)]
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


# ----- subnet conflicts -------------------------------------------------------------------

NO_PORT_CONFLICTS = PortCheckResult(success=True, has_conflicts=False, conflicts=[])


def _leftover_conflict(recommended: str | None = "10.90.0.0/24") -> SubnetConflict:
    return SubnetConflict(
        network_id="lab-net",
        subnet="10.50.0.0/24",
        reason="overlaps_leftover",
        owner_network_name="practicum-deadbeef-lab-net",
        owner_subnet="10.50.0.0/24",
        owner_lab_id="deadbeef-0000-0000-0000-000000000000",
        owner_container_count=1,
        recommended_subnet=recommended,
    )


def _other_lab_conflict() -> SubnetConflict:
    return SubnetConflict(
        network_id="lab-net",
        subnet="10.50.0.0/24",
        reason="overlaps_other_lab",
        owner_network_name="practicum-11111111-lab-net",
        owner_subnet="10.50.0.0/24",
        owner_lab_id="11111111-aaaa-bbbb-cccc-000000000001",
        owner_lab_name="Ubuntu Quick Start",
        owner_lab_status="stopped",
        owner_container_count=1,
        recommended_subnet="10.90.0.0/24",
    )


def _buttons(dialog: PreStartGateDialog, row: int) -> list[str]:
    widget = dialog.networks_table.cellWidget(row, 3)
    return [b.text() for b in widget.findChildren(QPushButton)]


def test_subnet_conflict_blocks_start_and_shows_owner(monkeypatch) -> None:
    monkeypatch.setattr(prestart_gate, "CallableWorker", ImmediateWorker)
    api = FakeApiClient(
        preview=_preview(),
        ports=NO_PORT_CONFLICTS,
        networks=NetworkCheckResult(
            success=True, has_conflicts=True, conflicts=[_leftover_conflict()]
        ),
    )

    dialog = PreStartGateDialog(api, "lab-1")

    assert dialog.start_button.isEnabled() is False
    assert dialog.conflicts_banner.text() == "No port conflicts detected."
    assert "1 network overlaps address space already in use" in dialog.networks_banner.text()
    assert dialog.networks_table.rowCount() == 1
    assert dialog.networks_table.item(0, 0).text() == "lab-net"
    assert dialog.networks_table.item(0, 1).text() == "10.50.0.0/24"
    assert "Left over from an earlier session" in dialog.networks_table.item(0, 2).text()
    assert "practicum-deadbeef-lab-net" in dialog.networks_table.item(0, 2).text()
    assert _buttons(dialog, 0) == ["Remove leftover", "Use 10.90.0.0/24"]


def test_remove_leftover_confirms_then_clears_conflict(monkeypatch) -> None:
    monkeypatch.setattr(prestart_gate, "CallableWorker", ImmediateWorker)
    prompts: list[tuple] = []
    monkeypatch.setattr(
        prestart_gate, "confirm", lambda *args, **kwargs: prompts.append((args, kwargs)) or True
    )
    api = FakeApiClient(
        preview=_preview(),
        ports=NO_PORT_CONFLICTS,
        networks=NetworkCheckResult(
            success=True, has_conflicts=True, conflicts=[_leftover_conflict()]
        ),
    )
    dialog = PreStartGateDialog(api, "lab-1")

    api._networks = NetworkCheckResult(success=True, has_conflicts=False)
    dialog._on_remove_leftover(_leftover_conflict())

    assert prompts[0][1]["destructive"] is True
    assert "practicum-deadbeef-lab-net" in prompts[0][0][2]
    assert api.remove_leftover_calls == [("lab-1", "practicum-deadbeef-lab-net")]
    assert dialog.networks_table.rowCount() == 0
    assert dialog.networks_banner.text() == "No subnet conflicts with existing Docker networks."
    assert dialog.start_button.isEnabled() is True


def test_remove_leftover_cancelled_changes_nothing(monkeypatch) -> None:
    monkeypatch.setattr(prestart_gate, "CallableWorker", ImmediateWorker)
    monkeypatch.setattr(prestart_gate, "confirm", lambda *args, **kwargs: False)
    api = FakeApiClient(
        preview=_preview(),
        ports=NO_PORT_CONFLICTS,
        networks=NetworkCheckResult(
            success=True, has_conflicts=True, conflicts=[_leftover_conflict()]
        ),
    )
    dialog = PreStartGateDialog(api, "lab-1")

    dialog._on_remove_leftover(_leftover_conflict())

    assert api.remove_leftover_calls == []
    assert dialog.networks_table.rowCount() == 1
    assert dialog.start_button.isEnabled() is False


def test_other_lab_conflict_offers_reset_and_resets_that_lab(monkeypatch) -> None:
    monkeypatch.setattr(prestart_gate, "CallableWorker", ImmediateWorker)
    monkeypatch.setattr(prestart_gate, "confirm", lambda *args, **kwargs: True)
    api = FakeApiClient(
        preview=_preview(),
        ports=NO_PORT_CONFLICTS,
        networks=NetworkCheckResult(
            success=True, has_conflicts=True, conflicts=[_other_lab_conflict()]
        ),
    )
    dialog = PreStartGateDialog(api, "lab-1")

    assert _buttons(dialog, 0) == ["Reset 'Ubuntu Quick Start'", "Use 10.90.0.0/24"]
    assert "Used by lab 'Ubuntu Quick Start'" in dialog.networks_table.item(0, 2).text()

    api._networks = NetworkCheckResult(success=True, has_conflicts=False)
    dialog._on_reset_owner_lab(_other_lab_conflict())

    assert api.reset_calls == ["11111111-aaaa-bbbb-cccc-000000000001"]
    assert dialog.start_button.isEnabled() is True


def test_failed_owner_reset_keeps_conflict_and_explains(monkeypatch) -> None:
    monkeypatch.setattr(prestart_gate, "CallableWorker", ImmediateWorker)
    monkeypatch.setattr(prestart_gate, "confirm", lambda *args, **kwargs: True)
    api = FakeApiClient(
        preview=_preview(),
        ports=NO_PORT_CONFLICTS,
        networks=NetworkCheckResult(
            success=True, has_conflicts=True, conflicts=[_other_lab_conflict()]
        ),
    )
    api.reset_result = StartResult(success=False, detail="Docker is unavailable")
    dialog = PreStartGateDialog(api, "lab-1")

    dialog._on_reset_owner_lab(_other_lab_conflict())

    assert dialog.networks_banner.text() == "Docker is unavailable"
    assert dialog.networks_banner.property("banner") == "error"  # colour, not an emoji
    assert dialog.networks_table.rowCount() == 1
    assert dialog.start_button.isEnabled() is False


def test_use_recommended_subnet_applies_and_notes_remap(monkeypatch) -> None:
    monkeypatch.setattr(prestart_gate, "CallableWorker", ImmediateWorker)
    api = FakeApiClient(
        preview=_preview(),
        ports=NO_PORT_CONFLICTS,
        networks=NetworkCheckResult(
            success=True, has_conflicts=True, conflicts=[_leftover_conflict()]
        ),
    )
    dialog = PreStartGateDialog(api, "lab-1")

    api._networks = NetworkCheckResult(success=True, has_conflicts=False)
    dialog._on_apply_subnet_recommendation(_leftover_conflict())

    assert api.subnet_apply_calls == [("lab-1", "lab-net")]
    assert "now uses 10.90.0.0/24" in dialog.networks_banner.text()
    assert "manual may still mention" in dialog.networks_banner.text()
    assert dialog.start_button.isEnabled() is True


def test_unanswerable_network_check_blocks_start(monkeypatch) -> None:
    monkeypatch.setattr(prestart_gate, "CallableWorker", ImmediateWorker)
    api = FakeApiClient(
        preview=_preview(),
        ports=NO_PORT_CONFLICTS,
        networks=NetworkCheckResult(success=False, detail="Docker Desktop is not running"),
    )

    dialog = PreStartGateDialog(api, "lab-1")

    assert dialog.start_button.isEnabled() is False
    assert "Docker Desktop is not running" in dialog.networks_banner.text()


def test_foreign_docker_network_only_offers_subnet_change(monkeypatch) -> None:
    monkeypatch.setattr(prestart_gate, "CallableWorker", ImmediateWorker)
    conflict = SubnetConflict(
        network_id="lan",
        subnet="10.0.1.0/24",
        reason="overlaps_docker_network",
        owner_network_name="compose_default",
        owner_subnet="10.0.0.0/16",
        recommended_subnet="10.90.0.0/24",
    )
    api = FakeApiClient(
        preview=_preview(),
        ports=NO_PORT_CONFLICTS,
        networks=NetworkCheckResult(success=True, has_conflicts=True, conflicts=[conflict]),
    )

    dialog = PreStartGateDialog(api, "lab-1")

    assert _buttons(dialog, 0) == ["Use 10.90.0.0/24"]
    assert "not created by Practicum" in dialog.networks_table.item(0, 2).text()


# ----- start with real progress (runtime-image-pull-progress) ------------------------------


def test_start_asks_for_a_background_start_and_polls_until_running(monkeypatch) -> None:
    monkeypatch.setattr(prestart_gate, "CallableWorker", ImmediateWorker)
    api = FakeApiClient(
        preview=_preview(),
        ports=PortCheckResult(success=True, has_conflicts=False, conflicts=[]),
        start=StartResult(success=True, detail="Start requested.", pending=True),
    )
    api.statuses = [
        StatusResult(
            success=True,
            lab_status="starting",
            progress=[
                NodeStartProgressFixture.pulling("client"),
            ],
        ),
        StatusResult(
            success=True,
            lab_status="running",
            progress=[NodeProgressInfo("client", "alpine", "ready")],
        ),
    ]
    dialog = PreStartGateDialog(api, "lab-1")

    dialog._on_start_clicked()  # start → pending → first poll → still starting

    assert api.start_waits == [False]
    assert api.status_calls == ["lab-1"]
    assert dialog.footer_stack.currentIndex() == 1  # progress panel replaces the pill
    assert "Downloading alpine" in dialog.progress_panel.summary_label.text()
    assert dialog.cancel_button.isEnabled() is False
    assert dialog.result() != QDialog.DialogCode.Accepted

    dialog._poll_status()  # the timer's next tick

    assert dialog.result() == QDialog.DialogCode.Accepted


def test_background_start_failure_shows_the_node_error_and_reenables_start(monkeypatch) -> None:
    monkeypatch.setattr(prestart_gate, "CallableWorker", ImmediateWorker)
    api = FakeApiClient(
        preview=_preview(),
        ports=PortCheckResult(success=True, has_conflicts=False, conflicts=[]),
        start=StartResult(success=True, detail="Start requested.", pending=True),
    )
    api.statuses = [
        StatusResult(
            success=True,
            lab_status="error",
            last_error="node 'client' (alpine): could not pull image 'alpine': not found",
            progress=[NodeProgressInfo("client", "alpine", "failed", detail="could not pull")],
        )
    ]
    dialog = PreStartGateDialog(api, "lab-1")

    dialog._on_start_clicked()

    assert dialog.result() != QDialog.DialogCode.Accepted
    assert "could not pull image 'alpine'" in dialog.status_label.text()
    assert dialog.footer_stack.currentIndex() == 0
    assert dialog.start_button.isEnabled() is True
    assert dialog.cancel_button.isEnabled() is True


def test_gate_cannot_be_closed_while_a_start_is_in_flight(monkeypatch) -> None:
    monkeypatch.setattr(prestart_gate, "CallableWorker", ImmediateWorker)
    api = FakeApiClient(
        preview=_preview(),
        ports=PortCheckResult(success=True, has_conflicts=False, conflicts=[]),
        start=StartResult(success=True, detail="Start requested.", pending=True),
    )
    api.statuses = [StatusResult(success=True, lab_status="starting")]
    dialog = PreStartGateDialog(api, "lab-1")
    dialog.show()
    dialog._on_start_clicked()

    dialog.reject()

    assert dialog.isVisible() is True  # still open: the outcome must not be lost
    assert dialog._starting is True
    dialog._finish_start(False, "stopped for the test")
    dialog.reject()
    assert dialog.isVisible() is False


class NodeStartProgressFixture:
    @staticmethod
    def pulling(node_id: str) -> NodeProgressInfo:
        return NodeProgressInfo(
            node_id, "alpine", "pulling_image", percent=40, detail="2 of 5 layers"
        )


def test_windows_lab_starts_through_the_same_gate_flow_with_pull_progress(monkeypatch) -> None:
    """designer-windows-quick-start: the Windows lab uses the normal gate - checks, Start with
    wait=false, real per-node progress for the (large) Server Core pull, accept when running."""
    monkeypatch.setattr(prestart_gate, "CallableWorker", ImmediateWorker)
    image = "mcr.microsoft.com/windows/servercore:ltsc2022"
    api = FakeApiClient(
        preview=_preview(
            images=(image,), cpu=2.0, memory=2048, manual_tasks=2, container_os="windows"
        ),
        ports=PortCheckResult(success=True, has_conflicts=False, conflicts=[]),
        start=StartResult(success=True, detail="Start requested.", pending=True),
        engine=WINDOWS_ENGINE,
    )
    api.statuses = [
        StatusResult(
            success=True,
            lab_status="starting",
            progress=[
                NodeProgressInfo(
                    "host", image, "pulling_image", percent=12, detail="3 of 9 layers"
                )
            ],
        ),
        StatusResult(
            success=True,
            lab_status="running",
            progress=[NodeProgressInfo("host", image, "ready")],
        ),
    ]
    dialog = PreStartGateDialog(api, "lab-w")

    assert [chip.text() for chip in dialog.image_chips] == [image]
    assert dialog.engine_banner.property("banner") == "ok"
    assert dialog.start_button.isEnabled() is True
    assert "2 steps" in dialog.manual_label.text()

    dialog._on_start_clicked()
    assert api.start_waits == [False]
    assert dialog.footer_stack.currentIndex() == 1
    assert "Downloading mcr.microsoft.com/windows/servercore:ltsc2022" in (
        dialog.progress_panel.summary_label.text()
    )
    assert "12%" in dialog.progress_panel.summary_label.text()

    dialog._poll_status()
    assert dialog.result() == QDialog.DialogCode.Accepted


# ----- choosing a port of one's own (user request 2026-10-25) ---------------------------------


def _conflict_row_widgets(dialog: PreStartGateDialog, row: int = 0):
    cell = dialog.conflict_rows[row]
    buttons = cell.findChildren(QPushButton)
    field = cell.findChildren(QLineEdit)[0]
    return buttons, field


def test_conflict_row_offers_the_recommendation_and_a_port_of_your_own(monkeypatch) -> None:
    monkeypatch.setattr(prestart_gate, "CallableWorker", ImmediateWorker)
    conflict = PortConflict("server", 80, 80, "tcp", "in_use_on_host", recommended_port=8080)
    api = FakeApiClient(
        preview=_preview(),
        ports=PortCheckResult(success=True, has_conflicts=True, conflicts=[conflict]),
    )
    dialog = PreStartGateDialog(api, "lab-1")

    buttons, field = _conflict_row_widgets(dialog)
    assert [b.text() for b in buttons] == ["Use 8080", "Apply"]
    assert field.placeholderText() == "port"
    assert "server" in field.accessibleName() and "80/tcp" in field.accessibleName()
    assert dialog.start_button.isEnabled() is False

    api._ports = PortCheckResult(success=True, has_conflicts=False, conflicts=[])
    field.setText("9090")
    buttons[1].click()

    assert api.apply_calls == [("lab-1", "server", 80, "tcp", 9090)]
    assert dialog.start_button.isEnabled() is True
    assert dialog.conflicts_banner.text() == "No port conflicts detected."


def test_enter_in_the_port_field_applies_too(monkeypatch) -> None:
    monkeypatch.setattr(prestart_gate, "CallableWorker", ImmediateWorker)
    conflict = PortConflict("server", 80, 80, "tcp", "in_use_on_host", recommended_port=None)
    api = FakeApiClient(
        preview=_preview(),
        ports=PortCheckResult(success=True, has_conflicts=True, conflicts=[conflict]),
    )
    dialog = PreStartGateDialog(api, "lab-1")
    buttons, field = _conflict_row_widgets(dialog)
    assert [b.text() for b in buttons] == ["Apply"]  # no recommendation: only your own port
    assert field.placeholderText() == "port"

    api._ports = PortCheckResult(success=True, has_conflicts=False, conflicts=[])
    field.setText("8088")
    field.returnPressed.emit()

    assert api.apply_calls[-1] == ("lab-1", "server", 80, "tcp", 8088)


def test_unusable_chosen_port_is_explained_and_the_conflict_stays(monkeypatch) -> None:
    monkeypatch.setattr(prestart_gate, "CallableWorker", ImmediateWorker)
    conflict = PortConflict("server", 80, 80, "tcp", "in_use_on_host", recommended_port=8080)
    api = FakeApiClient(
        preview=_preview(),
        ports=PortCheckResult(success=True, has_conflicts=True, conflicts=[conflict]),
    )
    api.custom_port_result = PortCheckResult(
        success=False, detail="Port 8000/tcp is reserved by the Practicum API"
    )
    dialog = PreStartGateDialog(api, "lab-1")
    buttons, field = _conflict_row_widgets(dialog)

    field.setText("8000")
    buttons[1].click()

    assert "reserved by the Practicum API" in dialog.conflicts_banner.text()
    assert dialog.conflicts_banner.property("banner") == "error"
    assert len(dialog.conflict_rows) == 1  # still there to fix
    assert dialog.start_button.isEnabled() is False

    # obvious mistakes never reach the API
    field.setText("")
    buttons[1].click()
    assert "between 1 and 65535" in dialog.conflicts_banner.text()
    field.setText("80")
    buttons[1].click()
    assert "is the port that is in conflict" in dialog.conflicts_banner.text()
    assert [c for c in api.apply_calls if c[4] in (None, 80)] == []
    assert len(api.apply_calls) == 1


def test_a_fix_that_recreated_the_machines_says_so(monkeypatch) -> None:
    """D-48: moving a port/subnet on a lab that has run removes its old containers; the
    gate tells the user the machines start fresh and refreshes the (now Ready) preview."""
    monkeypatch.setattr(prestart_gate, "CallableWorker", ImmediateWorker)
    conflict = PortConflict("server", 80, 80, "tcp", "in_use_on_host", recommended_port=8080)
    api = FakeApiClient(
        preview=_preview(),
        ports=PortCheckResult(success=True, has_conflicts=True, conflicts=[conflict]),
    )
    dialog = PreStartGateDialog(api, "lab-1")

    api._ports = PortCheckResult(
        success=True, has_conflicts=False, conflicts=[], machines_reset=True
    )
    dialog._on_apply_recommendation(conflict)

    text = dialog.conflicts_banner.text()
    assert text.startswith("No port conflicts detected.")
    assert "machines were removed and will start fresh" in text
    assert "from earlier sessions is gone" in text
    assert dialog.start_button.isEnabled() is True

    # a never-started lab gets no such note
    dialog2 = PreStartGateDialog(api, "lab-2")
    api._ports = PortCheckResult(success=True, has_conflicts=False, conflicts=[])
    dialog2._on_apply_recommendation(conflict)
    assert dialog2.conflicts_banner.text() == "No port conflicts detected."
