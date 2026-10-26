"""Pre-start readiness gate (windows-desktop-prestart-lab-gate, runtime-subnet-conflicts,
runtime-image-pull-progress on the desktop side, windows-desktop-windows-container-readiness).

Laid out like the mockup's `screen-preview`: title + status badge + description, a main
column (Required images as chips, the read-only schematic topology, the manual preview) and
a side column (Estimated resources tiles, Container engine, Port conflicts, Network
conflicts), over a bottom bar with a status pill and Cancel / Start Lab. Start asks the API
to start without waiting (`wait=False`) and then polls GET /status, turning the bottom of
the dialog into the real per-node progress (image downloads, container creation) until the
lab is running or failed.

The Container engine check compares what the lab is built for (the preview's
`container_os`) with what the Docker daemon serves right now (`GET /docker/engine`): a
Windows lab while Docker Desktop is in Linux-container mode - or the other way round -
keeps Start disabled with the switch instructions and a Retry, because the start would
only fail later with a less friendly Docker error.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QIntValidator
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from practicum_desktop import theme
from practicum_desktop.api_client import (
    PORT_CONFLICT_REASONS,
    ApiClient,
    DockerEngineResult,
    NetworkCheckResult,
    PortCheckResult,
    PortConflict,
    PreviewResult,
    StartResult,
    StatusResult,
    SubnetConflict,
)
from practicum_desktop.dialogs import confirm
from practicum_desktop.progress_panel import StartProgressPanel
from practicum_desktop.widgets import (
    AutoSizeStack,
    Badge,
    Chip,
    FlowLayout,
    MessageBanner,
    Panel,
    StatTile,
    StatusPill,
    TopologyCanvas,
    TopologyLink,
    TopologyNetwork,
    TopologyNode,
    bind,
    bottom_bar,
    copyable_label,
    discard,
    make_button,
    payload_of,
    role_label,
)
from practicum_desktop.workers import CallableWorker

START_POLL_MS = 1000
MACHINES_RESET_NOTE = (
    "This lab had run before, so its machines were removed and will start fresh with the new "
    "setting; anything saved inside them from earlier sessions is gone."
)
OS_LABELS = {"linux": "Linux", "windows": "Windows"}
SWITCH_HINTS = {
    "windows": "right-click the Docker whale icon and choose 'Switch to Windows containers...'",
    "linux": "right-click the Docker whale icon and choose 'Switch to Linux containers...'",
}

_copyable_label = copyable_label


def engine_verdict(container_os: str, engine: DockerEngineResult) -> tuple[bool, str, str]:
    """(ok, text, banner kind) comparing the lab's OS with the daemon's engine mode."""
    needed = OS_LABELS.get(container_os, container_os)
    if not engine.success:
        return False, f"Could not check the Docker engine: {engine.detail}", "error"
    if not engine.available:
        return (
            False,
            f"Docker is not reachable: {engine.detail} Start Docker Desktop, then Retry.",
            "error",
        )
    if engine.os_type == container_os:
        return True, f"Docker Desktop serves {needed} containers, as this lab needs.", "ok"
    serving = OS_LABELS.get(engine.os_type or "", engine.os_type or "unknown")
    hint = SWITCH_HINTS.get(container_os, "switch the engine mode")
    text = (
        f"This lab needs {needed} containers, but Docker Desktop is serving {serving} "
        f"containers. To run it, {hint}, wait for Docker to restart, then select Retry. "
        "Practicum never switches the mode for you."
    )
    return False, text, "warn"


def _fit_table_height(table: QTableWidget, max_rows: int = 5) -> None:
    """Sizes a small table to its rows instead of leaving a large empty area."""
    header = table.horizontalHeader().height()
    rows = sum(table.rowHeight(row) for row in range(min(table.rowCount(), max_rows)))
    table.setFixedHeight(header + rows + 4 if table.rowCount() else 0)


def _subnet_issue_text(conflict: SubnetConflict) -> str:
    if conflict.reason == "overlaps_other_lab":
        status = f", {conflict.owner_lab_status}" if conflict.owner_lab_status else ""
        return f"Used by lab '{conflict.owner_lab_name}' ({conflict.owner_subnet}{status})"
    if conflict.reason == "overlaps_leftover":
        plural = "s" if conflict.owner_container_count != 1 else ""
        return (
            f"Left over from an earlier session: '{conflict.owner_network_name}' "
            f"({conflict.owner_subnet}, {conflict.owner_container_count} container{plural})"
        )
    return (
        f"Used by Docker network '{conflict.owner_network_name}' ({conflict.owner_subnet}), "
        "not created by Practicum"
    )


class PreStartGateDialog(QDialog):
    """The mandatory screen between selecting a lab and actually starting it.

    Shows what will run on the student's machine (required images, estimated
    resources, read-only topology, manual step count) and blocks Start until any host
    port conflicts and subnet conflicts (a Docker network already using the lab's
    address space) are resolved. See windows-desktop-prestart-lab-gate.md.

    Every entry point capable of starting a lab should route through this same dialog
    rather than re-implementing the gate; today that's the main window's Start button,
    with the Labs Dashboard and Import-and-launch flows expected to reuse it once built.
    """

    def __init__(self, api_client: ApiClient, lab_id: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Review Before Starting")
        self.resize(980, 760)

        self._api_client = api_client
        self._lab_id = lab_id
        self._conflicts: list[PortConflict] = []
        self._subnet_conflicts: list[SubnetConflict] = []
        self._ports_known = False
        self._networks_known = False
        self._container_os: str | None = None  # from the preview
        self._engine: DockerEngineResult | None = None  # from GET /docker/engine
        self._engine_ok = False
        self._starting = False
        self._engine_worker: CallableWorker | None = None
        self._preview_worker: CallableWorker | None = None
        self._ports_worker: CallableWorker | None = None
        self._networks_worker: CallableWorker | None = None
        self._apply_worker: CallableWorker | None = None
        self._network_fix_worker: CallableWorker | None = None
        self._start_worker: CallableWorker | None = None
        self._poll_worker: CallableWorker | None = None
        self._poll_timer = QTimer(self)
        self._poll_timer.setSingleShot(True)
        self._poll_timer.timeout.connect(self._poll_status)
        self._subnet_moved_note = ""
        self.image_chips: list[Chip] = []

        self._build_ui()
        self._load()

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        page = QWidget()
        page.setObjectName("screen")
        layout = QVBoxLayout(page)
        layout.setContentsMargins(32, 22, 32, 10)
        layout.setSpacing(10)
        outer.addWidget(page, 1)

        title_row = QHBoxLayout()
        title_row.setSpacing(10)
        self.name_label = QLabel("Loading\u2026")
        self.name_label.setProperty("role", "h1")
        self.name_label.setStyleSheet("font-size: 24px;")
        title_row.addWidget(self.name_label)
        self.badge = Badge("defined")
        title_row.addWidget(self.badge)
        title_row.addStretch(1)
        layout.addLayout(title_row)
        self.description_label = copyable_label("", role="subtitle")
        layout.addWidget(self.description_label)
        self.author_label = copyable_label("", role="hint")
        layout.addWidget(self.author_label)

        columns_scroll = QScrollArea()
        columns_scroll.setWidgetResizable(True)
        columns_scroll.setFrameShape(QFrame.Shape.NoFrame)
        columns_host = QWidget()
        columns = QHBoxLayout(columns_host)
        columns.setContentsMargins(0, 6, 4, 6)
        columns.setSpacing(20)

        main_column = QVBoxLayout()
        main_column.setSpacing(16)
        images_panel = Panel("Required images")
        chips_host = QWidget()
        self.images_layout = FlowLayout(chips_host)
        images_panel.body_layout.addWidget(chips_host)
        self.images_label = role_label("", "muted")  # shown only when there are none
        self.images_label.hide()
        images_panel.body_layout.addWidget(self.images_label)
        main_column.addWidget(images_panel)

        topology_panel = Panel("Topology (read-only)")
        self.topology_canvas = TopologyCanvas()
        self.topology_canvas.setMinimumHeight(150)
        topology_panel.body_layout.addWidget(self.topology_canvas)
        main_column.addWidget(topology_panel)

        manual_panel = Panel(padding=14)
        toggle_row = QHBoxLayout()
        toggle_row.setSpacing(6)
        self.manual_toggle = make_button("\u25be", kind="ghost")
        self.manual_toggle.setCheckable(True)
        self.manual_toggle.setChecked(True)
        self.manual_toggle.setStyleSheet("padding: 0 6px; font-size: 13px;")
        self.manual_toggle.toggled.connect(self._on_manual_toggled)
        toggle_row.addWidget(self.manual_toggle)
        self.manual_label = copyable_label("")
        toggle_row.addWidget(self.manual_label, 1)
        manual_panel.body_layout.addLayout(toggle_row)
        self.manual_steps_host = QWidget()
        self.manual_steps_layout = QVBoxLayout(self.manual_steps_host)
        self.manual_steps_layout.setContentsMargins(26, 4, 0, 0)
        self.manual_steps_layout.setSpacing(4)
        manual_panel.body_layout.addWidget(self.manual_steps_host)
        main_column.addWidget(manual_panel)
        main_column.addStretch(1)
        columns.addLayout(main_column, 13)

        side_column = QVBoxLayout()
        side_column.setSpacing(16)
        resources_panel = Panel(padding=14)
        resources_panel.body_layout.addWidget(role_label("Estimated resources", "h3"))
        tiles = QHBoxLayout()
        tiles.setSpacing(10)
        self.cpu_tile = StatTile("CPU")
        self.cpu_label = self.cpu_tile.value_label
        tiles.addWidget(self.cpu_tile)
        self.memory_tile = StatTile("Memory")
        self.memory_label = self.memory_tile.value_label
        tiles.addWidget(self.memory_tile)
        resources_panel.body_layout.addLayout(tiles)
        side_column.addWidget(resources_panel)

        engine_panel = Panel(padding=14)
        engine_head = QHBoxLayout()
        engine_head.setSpacing(8)
        engine_head.addWidget(role_label("Container engine", "h3"), 1)
        self.engine_retry_button = make_button("Retry", small=True)
        self.engine_retry_button.setToolTip(
            "Check again which containers Docker Desktop serves (after switching its mode)"
        )
        self.engine_retry_button.clicked.connect(self._check_engine)
        engine_head.addWidget(self.engine_retry_button)
        engine_panel.body_layout.addLayout(engine_head)
        self.engine_banner = MessageBanner("info")
        engine_panel.body_layout.addWidget(self.engine_banner)
        side_column.addWidget(engine_panel)

        conflicts_panel = Panel(padding=14)
        conflicts_panel.body_layout.addWidget(role_label("Port conflicts", "h3"))
        self.conflicts_banner = MessageBanner("info")
        conflicts_panel.body_layout.addWidget(self.conflicts_banner)
        # One card per conflict (what clashes, then the fix controls underneath): a table
        # cannot fit "Use <port>" + a port field + Apply in this narrow column.
        self.conflicts_host = QWidget()
        self.conflicts_layout = QVBoxLayout(self.conflicts_host)
        self.conflicts_layout.setContentsMargins(0, 0, 0, 0)
        self.conflicts_layout.setSpacing(6)
        self.conflict_rows: list[QWidget] = []
        self.conflicts_host.hide()
        conflicts_panel.body_layout.addWidget(self.conflicts_host)
        side_column.addWidget(conflicts_panel)

        networks_panel = Panel(padding=14)
        networks_panel.body_layout.addWidget(role_label("Network conflicts", "h3"))
        self.networks_banner = MessageBanner("info")
        networks_panel.body_layout.addWidget(self.networks_banner)
        self.networks_table = QTableWidget(0, 4)
        self.networks_table.setHorizontalHeaderLabels(["Network", "Subnet", "Issue", "Fix"])
        header = self.networks_table.horizontalHeader()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.networks_table.verticalHeader().hide()
        self.networks_table.verticalHeader().setDefaultSectionSize(36)
        self.networks_table.setWordWrap(True)
        self.networks_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.networks_table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.networks_table.hide()
        networks_panel.body_layout.addWidget(self.networks_table)
        side_column.addWidget(networks_panel)
        side_column.addStretch(1)
        columns.addLayout(side_column, 11)
        columns_scroll.setWidget(columns_host)
        layout.addWidget(columns_scroll, 1)

        # bottom: status pill (idle) or the live start progress (starting)
        self.footer_stack = AutoSizeStack()
        self.footer_stack.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)
        idle = QWidget()
        idle_layout = QVBoxLayout(idle)
        idle_layout.setContentsMargins(0, 0, 0, 0)
        self.status_pill = StatusPill("Loading lab details\u2026", theme.AMBER)
        idle_layout.addWidget(self.status_pill)
        self.status_label = MessageBanner("error")
        self.status_label.hide()
        idle_layout.addWidget(self.status_label)
        self.footer_stack.addWidget(idle)
        self.progress_panel = StartProgressPanel()
        self.footer_stack.addWidget(self.progress_panel)

        bar, bar_row = bottom_bar()
        bar_row.setContentsMargins(32, 12, 32, 12)
        bar_row.addWidget(self.footer_stack, 1)
        self.cancel_button = make_button("Cancel")
        self.cancel_button.clicked.connect(self.reject)
        bar_row.addWidget(self.cancel_button, 0, Qt.AlignmentFlag.AlignBottom)
        self.start_button = make_button("Start Lab", kind="primary", icon="play")
        self.start_button.setEnabled(False)
        self.start_button.clicked.connect(self._on_start_clicked)
        bar_row.addWidget(self.start_button, 0, Qt.AlignmentFlag.AlignBottom)
        outer.addWidget(bar)

    def _on_manual_toggled(self, checked: bool) -> None:
        self.manual_toggle.setText("\u25be" if checked else "\u25b8")
        self.manual_steps_host.setVisible(checked)

    def _load(self) -> None:
        self.status_pill.set_state("Loading lab details\u2026", theme.AMBER)

        self._preview_worker = CallableWorker(self._api_client.get_preview, self._lab_id)
        self._preview_worker.finished_call.connect(self._on_preview_loaded)
        self._preview_worker.start()

        self._ports_worker = CallableWorker(self._api_client.check_ports, self._lab_id)
        self._ports_worker.finished_call.connect(self._on_ports_checked)
        self._ports_worker.start()

        self._banner(self.networks_banner, "Checking Docker networks\u2026", "info")
        self._networks_worker = CallableWorker(self._api_client.check_networks, self._lab_id)
        self._networks_worker.finished_call.connect(self._on_networks_checked)
        self._networks_worker.start()

        self._check_engine()

    # ----- container engine -------------------------------------------------------------

    def _check_engine(self) -> None:
        if self._engine_worker is not None and self._engine_worker.isRunning():
            return
        self._banner(self.engine_banner, "Checking which containers Docker serves\u2026", "info")
        self.engine_retry_button.setEnabled(False)
        self._engine_worker = CallableWorker(self._api_client.get_docker_engine)
        self._engine_worker.finished_call.connect(self._on_engine_checked)
        self._engine_worker.start()

    def _on_engine_checked(self, result: DockerEngineResult) -> None:
        self._engine = result
        self.engine_retry_button.setEnabled(True)
        self._render_engine()

    def _render_engine(self) -> None:
        """Needs both answers (preview for the lab's OS, engine for Docker's mode)."""
        if self._engine is None or self._container_os is None:
            self._engine_ok = False
            return
        ok, text, kind = engine_verdict(self._container_os, self._engine)
        self._engine_ok = ok
        self._banner(self.engine_banner, text, kind)
        self._update_start_enabled()

    def _reload_preview(self) -> None:
        self._preview_worker = CallableWorker(self._api_client.get_preview, self._lab_id)
        self._preview_worker.finished_call.connect(self._on_preview_loaded)
        self._preview_worker.start()

    def _on_preview_loaded(self, result: PreviewResult) -> None:
        if not result.success:
            self.name_label.setText("Could not load this lab.")
            self.description_label.setText(result.detail)
            return

        self.name_label.setText(result.name)
        self.description_label.setText(result.description or "No description provided.")
        if result.status:
            self.badge.set_status(result.status)
        self._container_os = result.container_os or "linux"
        self._render_engine()
        self._update_start_enabled()

        author_parts = [part for part in (result.author, result.version) if part]
        self.author_label.setText(" \u00b7 ".join(author_parts))

        self.images_layout.clear()
        self.image_chips = []
        for image in result.required_images:
            chip = Chip(image)
            chip.setToolTip("Pulled by Docker on first start if it is not on this computer yet")
            self.images_layout.addWidget(chip)
            self.image_chips.append(chip)
        self.images_label.setVisible(not result.required_images)
        self.images_label.setText("None" if not result.required_images else "")

        cpu = result.estimated_resources.total_cpu
        self.cpu_tile.set_value(f"{cpu} vCPU" if cpu is not None else "Unknown")
        memory = result.estimated_resources.total_memory_mb
        self.memory_tile.set_value(f"{memory} MB" if memory is not None else "Unknown")

        self._render_topology(result)
        self._render_manual(result)

    def _render_topology(self, result: PreviewResult) -> None:
        topology = result.topology
        self.topology_canvas.set_topology(
            [TopologyNode(node.id, node.image) for node in topology.nodes],
            [TopologyNetwork(network.id, network.subnet) for network in topology.networks],
            [
                TopologyLink(interface.node, interface.network, interface.address)
                for interface in topology.interfaces
            ],
        )

    def _render_manual(self, result: PreviewResult) -> None:
        while self.manual_steps_layout.count():
            item = self.manual_steps_layout.takeAt(0)
            discard(item.widget())
        step_count = sum(len(section.tasks) for section in result.manual_sections)
        if not result.manual_sections:
            self.manual_label.setText("This lab has no manual.")
            self.manual_toggle.hide()
            return
        self.manual_toggle.show()
        plural = "" if step_count == 1 else "s"
        self.manual_label.setText(
            f"Includes instructor manual with {step_count} step{plural}, shown once the "
            "lab is running."
        )
        for number, section in enumerate(result.manual_sections, start=1):
            row = QHBoxLayout()
            row.setSpacing(8)
            marker = QLabel(str(number))
            marker.setFixedSize(18, 18)
            marker.setAlignment(Qt.AlignmentFlag.AlignCenter)
            marker.setStyleSheet(
                f"background: {theme.LINE_SOFT}; color: {theme.MUTED}; border-radius: 9px;"
                " font-size: 10px;"
            )
            row.addWidget(marker, 0, Qt.AlignmentFlag.AlignTop)
            texts = QVBoxLayout()
            texts.setSpacing(0)
            texts.addWidget(role_label(section.title, "label"))
            tasks = "; ".join(task.text for task in section.tasks)
            if tasks:
                texts.addWidget(role_label(tasks, "muted", wrap=True))
            row.addLayout(texts, 1)
            host = QWidget()
            host.setLayout(row)
            self.manual_steps_layout.addWidget(host)

    def _update_start_enabled(self) -> None:
        """Start is allowed only once every check has answered and none found anything:
        host ports, Docker subnets, and the engine mode matching the lab's OS."""
        ready = (
            self._ports_known
            and self._networks_known
            and self._engine_ok
            and not self._conflicts
            and not self._subnet_conflicts
        )
        self.start_button.setEnabled(ready and not self._starting)
        if self._starting:
            return
        if ready:
            self.status_pill.set_state("Ready to start", theme.GREEN)
        elif not self._ports_known or not self._networks_known or self._engine is None:
            self.status_pill.set_state("Checking this computer\u2026", theme.AMBER)
        elif not self._engine_ok:
            self.status_pill.set_state(
                "Switch Docker Desktop's container mode to continue", theme.AMBER
            )
        else:
            self.status_pill.set_state("Resolve conflicts to continue", theme.AMBER)

    def _on_ports_checked(self, result: PortCheckResult) -> None:
        if not result.success:
            self._ports_known = False
            self._banner(self.conflicts_banner, result.detail, "error")
            self._update_start_enabled()
            return

        self._ports_known = True
        self._conflicts = result.conflicts
        self._render_conflicts()

    def _render_conflicts(self) -> None:
        for row_widget in self.conflict_rows:
            self.conflicts_layout.removeWidget(row_widget)
            discard(row_widget)
        self.conflict_rows = []
        for conflict in self._conflicts:
            card = self._conflict_card(conflict)
            self.conflicts_layout.addWidget(card)
            self.conflict_rows.append(card)
        self.conflicts_host.setVisible(bool(self._conflicts))
        if not self._conflicts:
            self._banner(self.conflicts_banner, "No port conflicts detected.", "ok")
        else:
            plural = "s" if len(self._conflicts) != 1 else ""
            self._banner(
                self.conflicts_banner,
                f"{len(self._conflicts)} port conflict{plural} must be resolved before "
                "starting.",
                "warn",
            )
        self._update_start_enabled()

    def _conflict_card(self, conflict: PortConflict) -> QWidget:
        """'web-1 8080/tcp · Already in use on this machine' over its fix controls."""
        card = QFrame()
        card.setProperty("panel", "soft")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(10, 8, 10, 8)
        layout.setSpacing(6)
        reason_text = PORT_CONFLICT_REASONS.get(conflict.reason, conflict.reason)
        title = role_label(
            f"{conflict.node_id} \u00b7 host port {conflict.host_port}/{conflict.protocol}",
            "label",
        )
        title.setToolTip(
            f"Container port {conflict.container_port}/{conflict.protocol} of "
            f"'{conflict.node_id}' is published on host port {conflict.host_port}"
        )
        layout.addWidget(title)
        layout.addWidget(role_label(reason_text, "muted", wrap=True))
        layout.addWidget(self._port_fix_widget(conflict))
        return card

    def _port_fix_widget(self, conflict: PortConflict) -> QWidget:
        """'Use <recommended>' plus a field for a port of the user's own choosing."""
        container = QWidget()
        row = QHBoxLayout(container)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(6)
        if conflict.recommended_port is not None:
            use_button = QPushButton(f"Use {conflict.recommended_port}")
            use_button.setProperty("small", True)
            use_button.setToolTip("Move this mapping to the next free port Practicum found")
            bind(use_button, self._on_apply_recommendation_clicked, conflict)
            row.addWidget(use_button)
        port_field = QLineEdit()
        port_field.setPlaceholderText("port")
        port_field.setValidator(QIntValidator(1, 65535, port_field))
        port_field.setFixedWidth(84)
        port_field.setToolTip(
            f"Or type a host port (1-65535) for {conflict.node_id}'s {conflict.host_port}/"
            f"{conflict.protocol} and press Enter or Apply"
        )
        port_field.setAccessibleName(
            f"Other host port for {conflict.node_id} {conflict.host_port}/{conflict.protocol}"
        )
        row.addWidget(port_field)
        apply_button = QPushButton("Apply")
        apply_button.setProperty("small", True)
        apply_button.setToolTip("Use the port typed on the left")
        bind(apply_button, self._on_apply_custom_port_clicked, (conflict, port_field))
        port_field.returnPressed.connect(apply_button.click)
        row.addWidget(apply_button)
        row.addStretch(1)
        return container

    def _on_apply_custom_port_clicked(self) -> None:
        conflict, port_field = payload_of(self.sender())
        self._on_apply_custom_port(conflict, port_field.text())

    def _on_apply_custom_port(self, conflict: PortConflict, text: str) -> None:
        """Applies a port the user typed; obvious mistakes are caught here, the API checks
        that the port is really usable (free, not its own, not elsewhere in the lab)."""
        try:
            port = int(text.strip())
        except ValueError:
            port = 0
        if not 1 <= port <= 65535:
            self._banner(
                self.conflicts_banner, "Type a host port between 1 and 65535, then Apply.", "warn"
            )
            return
        if port == conflict.host_port:
            self._banner(
                self.conflicts_banner,
                f"{port}/{conflict.protocol} is the port that is in conflict; choose another.",
                "warn",
            )
            return
        self._banner(self.conflicts_banner, f"Moving to port {port}\u2026", "info")
        self.start_button.setEnabled(False)
        self._apply_worker = CallableWorker(
            self._api_client.apply_port_recommendation,
            self._lab_id,
            conflict.node_id,
            conflict.host_port,
            conflict.protocol,
            port,
        )
        self._apply_worker.finished_call.connect(self._on_port_fix_done)
        self._apply_worker.start()

    def _on_port_fix_done(self, result: PortCheckResult) -> None:
        if not result.success:
            # The conflict list is unchanged; say why the port was refused and keep the rows.
            self._banner(self.conflicts_banner, f"{result.detail}", "error")
            self._update_start_enabled()
            return
        self._on_ports_checked(result)
        if result.machines_reset:
            self._note_machines_reset(self.conflicts_banner)

    def _note_machines_reset(self, banner: MessageBanner) -> None:
        """The fix removed machines that had run before (D-48): say so, and refresh the
        preview so the badge shows the lab is back to Ready."""
        self._banner(
            banner,
            f"{banner.text()} {MACHINES_RESET_NOTE}",
            "info" if banner.property("banner") in ("ok", "info") else banner.property("banner"),
        )
        self._reload_preview()

    @staticmethod
    def _banner(banner: MessageBanner, text: str, kind: str) -> None:
        banner.set_message(text, kind)

    # ----- subnet conflicts -------------------------------------------------------------

    def _on_networks_checked(self, result: NetworkCheckResult) -> None:
        if not result.success:
            self._networks_known = False
            self._banner(
                self.networks_banner,
                f"Could not check Docker networks: {result.detail} "
                "Start stays disabled until this can be verified.",
                "error",
            )
            self._update_start_enabled()
            return

        self._networks_known = True
        self._subnet_conflicts = result.conflicts
        self._render_subnet_conflicts()

    def _render_subnet_conflicts(self) -> None:
        self.networks_table.setRowCount(len(self._subnet_conflicts))
        for row, conflict in enumerate(self._subnet_conflicts):
            self.networks_table.setItem(row, 0, QTableWidgetItem(conflict.network_id))
            self.networks_table.setItem(row, 1, QTableWidgetItem(conflict.subnet))
            self.networks_table.setItem(row, 2, QTableWidgetItem(_subnet_issue_text(conflict)))
            self.networks_table.setCellWidget(row, 3, self._subnet_fix_widget(conflict))
        self.networks_table.resizeRowsToContents()
        self.networks_table.setVisible(bool(self._subnet_conflicts))
        _fit_table_height(self.networks_table)

        if not self._subnet_conflicts:
            self._banner(
                self.networks_banner, "No subnet conflicts with existing Docker networks.", "ok"
            )
        else:
            plural = "s" if len(self._subnet_conflicts) != 1 else ""
            self._banner(
                self.networks_banner,
                f"{len(self._subnet_conflicts)} network{plural} overlap{'' if plural else 's'} "
                "address space already in use on this machine. Docker refuses to create such "
                "networks, so the lab cannot start until each one is fixed.",
                "warn",
            )
        self._update_start_enabled()

    def _subnet_fix_widget(self, conflict: SubnetConflict) -> QWidget:
        container = QWidget()
        row = QHBoxLayout(container)
        row.setContentsMargins(2, 2, 2, 2)

        if conflict.reason == "overlaps_leftover":
            remove_button = QPushButton("Remove leftover")
            remove_button.setProperty("small", True)
            bind(remove_button, self._on_remove_leftover_clicked, conflict)
            row.addWidget(remove_button)
        elif conflict.reason == "overlaps_other_lab" and conflict.owner_lab_id:
            reset_button = QPushButton(f"Reset '{conflict.owner_lab_name}'")
            reset_button.setProperty("small", True)
            reset_button.setProperty("kind", "danger")
            bind(reset_button, self._on_reset_owner_lab_clicked, conflict)
            row.addWidget(reset_button)

        if conflict.recommended_subnet:
            use_button = QPushButton(f"Use {conflict.recommended_subnet}")
            use_button.setProperty("small", True)
            bind(use_button, self._on_apply_subnet_recommendation_clicked, conflict)
            row.addWidget(use_button)

        if row.count() == 0:
            row.addWidget(QLabel("No automatic fix available"))
        row.addStretch(1)
        return container

    def _on_remove_leftover_clicked(self) -> None:
        self._on_remove_leftover(payload_of(self.sender()))

    def _on_reset_owner_lab_clicked(self) -> None:
        self._on_reset_owner_lab(payload_of(self.sender()))

    def _on_apply_subnet_recommendation_clicked(self) -> None:
        self._on_apply_subnet_recommendation(payload_of(self.sender()))

    def _on_apply_recommendation_clicked(self) -> None:
        self._on_apply_recommendation(payload_of(self.sender()))

    def _on_remove_leftover(self, conflict: SubnetConflict) -> None:
        plural = "s" if conflict.owner_container_count != 1 else ""
        if not confirm(
            self,
            "Remove leftover lab resources?",
            f"This deletes the Docker network '{conflict.owner_network_name}' and its "
            f"{conflict.owner_container_count} container{plural}, left behind by an earlier "
            "Practicum session that is no longer in your lab list. Anything inside those "
            "containers is lost. This cannot be undone.",
            confirm_label="Remove",
            destructive=True,
        ):
            return
        self._run_network_fix(
            "Removing leftover resources…",
            self._api_client.remove_leftover_network,
            self._lab_id,
            conflict.owner_network_name,
        )

    def _on_reset_owner_lab(self, conflict: SubnetConflict) -> None:
        if not confirm(
            self,
            f"Reset '{conflict.owner_lab_name}'?",
            f"'{conflict.owner_lab_name}' owns the address space this lab needs. Resetting "
            "it removes its containers and networks and returns it to its original state; "
            "any work inside it is lost. Its manual progress on this computer is kept.",
            confirm_label="Reset",
            destructive=True,
        ):
            return
        self._run_network_fix(
            f"Resetting '{conflict.owner_lab_name}'…",
            self._reset_owner_then_recheck,
            conflict.owner_lab_id,
        )

    def _reset_owner_then_recheck(self, owner_lab_id: str) -> NetworkCheckResult:
        """Runs on the worker thread: reset the other lab, then re-check this one."""
        reset = self._api_client.reset_lab(owner_lab_id)
        if not reset.success:
            return NetworkCheckResult(success=False, detail=reset.detail)
        return self._api_client.check_networks(self._lab_id)

    def _on_apply_subnet_recommendation(self, conflict: SubnetConflict) -> None:
        self._run_network_fix(
            f"Moving '{conflict.network_id}' to {conflict.recommended_subnet}…",
            self._apply_subnet_then_note,
            conflict,
        )

    def _apply_subnet_then_note(self, conflict: SubnetConflict) -> NetworkCheckResult:
        result = self._api_client.apply_subnet_recommendation(self._lab_id, conflict.network_id)
        if result.success:
            self._subnet_moved_note = (
                f"Network '{conflict.network_id}' now uses {conflict.recommended_subnet}; "
                "addresses on it were remapped. The lab manual may still mention the "
                "original addresses."
            )
        return result

    def _run_network_fix(self, progress_text: str, func, *args) -> None:
        self._banner(self.networks_banner, progress_text, "info")
        self.start_button.setEnabled(False)
        self._network_fix_worker = CallableWorker(func, *args)
        self._network_fix_worker.finished_call.connect(self._on_network_fix_done)
        self._network_fix_worker.start()

    def _on_network_fix_done(self, result: NetworkCheckResult) -> None:
        if not result.success:
            # Keep the previous conflict list visible; just explain what went wrong.
            self._banner(self.networks_banner, f"{result.detail}", "error")
            self._update_start_enabled()
            return
        self._on_networks_checked(result)
        if self._subnet_moved_note:
            self._banner(
                self.networks_banner,
                f"{self.networks_banner.text()} {self._subnet_moved_note}",
                "info",
            )
            self._subnet_moved_note = ""
            self._reload_preview()  # topology addresses changed
        if result.machines_reset:
            self._note_machines_reset(self.networks_banner)

    def _on_apply_recommendation(self, conflict: PortConflict) -> None:
        self._banner(self.conflicts_banner, "Applying recommended port\u2026", "info")
        self.start_button.setEnabled(False)
        self._apply_worker = CallableWorker(
            self._api_client.apply_port_recommendation,
            self._lab_id,
            conflict.node_id,
            conflict.host_port,
            conflict.protocol,
        )
        self._apply_worker.finished_call.connect(self._on_port_fix_done)
        self._apply_worker.start()

    def _on_start_clicked(self) -> None:
        self._starting = True
        self.start_button.setEnabled(False)
        self.cancel_button.setEnabled(False)
        self.status_label.hide()
        self.progress_panel.set_title("Starting containers\u2026")
        self.progress_panel.set_progress([])
        self.footer_stack.setCurrentIndex(1)
        self._start_worker = CallableWorker(self._api_client.start_lab, self._lab_id, wait=False)
        self._start_worker.finished_call.connect(self._on_start_finished)
        self._start_worker.start()

    def _on_start_finished(self, result: StartResult) -> None:
        if result.success and result.pending:
            # The API is working in the background; follow its progress until it settles.
            self._poll_status()
            return
        self._finish_start(result.success, result.detail)

    def _poll_status(self) -> None:
        if self._poll_worker is not None and self._poll_worker.isRunning():
            self._poll_timer.start(START_POLL_MS)  # Docker is slow today; don't pile up
            return
        self._poll_worker = CallableWorker(self._api_client.get_status, self._lab_id)
        self._poll_worker.finished_call.connect(self._on_status_polled)
        self._poll_worker.start()

    def _on_status_polled(self, result: StatusResult) -> None:
        if not self._starting:
            return
        if result.success:
            self.progress_panel.set_progress(result.progress)
        if not result.success or result.lab_status == "starting":
            self._poll_timer.start(START_POLL_MS)
            return
        if result.lab_status == "running":
            self._finish_start(True, "Lab started.")
            return
        failed = next((p for p in result.progress if p.step == "failed"), None)
        detail = (
            result.last_error
            or (failed.detail if failed else None)
            or "The lab failed to start."
        )
        self._finish_start(False, detail)

    def _finish_start(self, success: bool, detail: str) -> None:
        self._starting = False
        self._poll_timer.stop()
        self.cancel_button.setEnabled(True)
        if success:
            self.accept()
            return
        self.footer_stack.setCurrentIndex(0)
        self.status_label.setText(f"{detail}")
        self.status_label.show()
        self._update_start_enabled()

    def reject(self) -> None:
        if self._starting:
            return  # the API is mid-start; closing now would hide the outcome
        super().reject()
