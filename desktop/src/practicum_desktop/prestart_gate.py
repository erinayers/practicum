from __future__ import annotations

from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from practicum_desktop.api_client import (
    PORT_CONFLICT_REASONS,
    ApiClient,
    NetworkCheckResult,
    PortCheckResult,
    PortConflict,
    PreviewResult,
    StartResult,
    SubnetConflict,
)
from practicum_desktop.dialogs import COPYABLE_TEXT_FLAGS, confirm
from practicum_desktop.workers import CallableWorker


def _copyable_label(text: str = "") -> QLabel:
    label = QLabel(text)
    label.setWordWrap(True)
    label.setTextInteractionFlags(COPYABLE_TEXT_FLAGS)
    return label


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
        self.resize(720, 820)

        self._api_client = api_client
        self._lab_id = lab_id
        self._conflicts: list[PortConflict] = []
        self._subnet_conflicts: list[SubnetConflict] = []
        self._ports_known = False
        self._networks_known = False
        self._preview_worker: CallableWorker | None = None
        self._ports_worker: CallableWorker | None = None
        self._networks_worker: CallableWorker | None = None
        self._apply_worker: CallableWorker | None = None
        self._network_fix_worker: CallableWorker | None = None
        self._start_worker: CallableWorker | None = None
        self._subnet_moved_note = ""

        self._build_ui()
        self._load()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        self.name_label = QLabel("Loading…")
        self.name_label.setStyleSheet("font-size: 16px; font-weight: 600;")
        layout.addWidget(self.name_label)

        self.description_label = _copyable_label()
        layout.addWidget(self.description_label)

        self.author_label = _copyable_label()
        layout.addWidget(self.author_label)

        layout.addWidget(QLabel("Required images:"))
        self.images_label = _copyable_label()
        layout.addWidget(self.images_label)

        resources_row = QHBoxLayout()
        resources_row.addWidget(QLabel("CPU:"))
        self.cpu_label = _copyable_label()
        resources_row.addWidget(self.cpu_label)
        resources_row.addWidget(QLabel("Memory:"))
        self.memory_label = _copyable_label()
        resources_row.addWidget(self.memory_label)
        resources_row.addStretch(1)
        layout.addLayout(resources_row)

        topology_group = QGroupBox("Topology (read-only)")
        topology_layout = QVBoxLayout(topology_group)
        self.topology_table = QTableWidget(0, 3)
        self.topology_table.setHorizontalHeaderLabels(["Node", "Network", "Address"])
        self.topology_table.horizontalHeader().setStretchLastSection(True)
        self.topology_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        topology_layout.addWidget(self.topology_table)
        layout.addWidget(topology_group)

        self.manual_label = _copyable_label()
        layout.addWidget(self.manual_label)

        conflicts_group = QGroupBox("Port Conflicts")
        conflicts_layout = QVBoxLayout(conflicts_group)
        self.conflicts_banner = _copyable_label()
        conflicts_layout.addWidget(self.conflicts_banner)
        self.conflicts_table = QTableWidget(0, 4)
        self.conflicts_table.setHorizontalHeaderLabels(["Node", "Port", "Issue", ""])
        self.conflicts_table.horizontalHeader().setStretchLastSection(True)
        self.conflicts_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        conflicts_layout.addWidget(self.conflicts_table)
        layout.addWidget(conflicts_group)

        networks_group = QGroupBox("Network Conflicts")
        networks_layout = QVBoxLayout(networks_group)
        self.networks_banner = _copyable_label()
        networks_layout.addWidget(self.networks_banner)
        self.networks_table = QTableWidget(0, 4)
        self.networks_table.setHorizontalHeaderLabels(["Network", "Subnet", "Issue", "Fix"])
        header = self.networks_table.horizontalHeader()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.networks_table.setWordWrap(True)
        self.networks_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        networks_layout.addWidget(self.networks_table)
        layout.addWidget(networks_group)

        self.status_label = _copyable_label()
        layout.addWidget(self.status_label)

        buttons_row = QHBoxLayout()
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self.reject)
        buttons_row.addWidget(self.cancel_button)

        self.start_button = QPushButton("Start Lab")
        self.start_button.setEnabled(False)
        self.start_button.clicked.connect(self._on_start_clicked)
        buttons_row.addWidget(self.start_button)
        layout.addLayout(buttons_row)

    def _load(self) -> None:
        self.status_label.setText("Loading lab details…")

        self._preview_worker = CallableWorker(self._api_client.get_preview, self._lab_id)
        self._preview_worker.finished_call.connect(self._on_preview_loaded)
        self._preview_worker.start()

        self._ports_worker = CallableWorker(self._api_client.check_ports, self._lab_id)
        self._ports_worker.finished_call.connect(self._on_ports_checked)
        self._ports_worker.start()

        self.networks_banner.setText("Checking Docker networks…")
        self._networks_worker = CallableWorker(self._api_client.check_networks, self._lab_id)
        self._networks_worker.finished_call.connect(self._on_networks_checked)
        self._networks_worker.start()

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
        if self.status_label.text() == "Loading lab details…":
            self.status_label.setText("")

        author_parts = [part for part in (result.author, result.version) if part]
        self.author_label.setText(" · ".join(author_parts))

        self.images_label.setText(
            ", ".join(result.required_images) if result.required_images else "None"
        )

        cpu = result.estimated_resources.total_cpu
        self.cpu_label.setText(f"{cpu} vCPU" if cpu is not None else "Unknown")
        memory = result.estimated_resources.total_memory_mb
        self.memory_label.setText(f"{memory} MB" if memory is not None else "Unknown")

        self._render_topology(result)

        step_count = sum(len(section.tasks) for section in result.manual_sections)
        if result.manual_sections:
            plural = "" if step_count == 1 else "s"
            self.manual_label.setText(
                f"Includes instructor manual with {step_count} step{plural}, shown once "
                "the lab is running."
            )
        else:
            self.manual_label.setText("This lab has no manual.")

    def _render_topology(self, result: PreviewResult) -> None:
        self.topology_table.setRowCount(len(result.topology.interfaces))
        for row, interface in enumerate(result.topology.interfaces):
            self.topology_table.setItem(row, 0, QTableWidgetItem(interface.node))
            self.topology_table.setItem(row, 1, QTableWidgetItem(interface.network))
            self.topology_table.setItem(row, 2, QTableWidgetItem(interface.address))

    def _update_start_enabled(self) -> None:
        """Start is allowed only once both checks have answered and neither found anything."""
        self.start_button.setEnabled(
            self._ports_known
            and self._networks_known
            and not self._conflicts
            and not self._subnet_conflicts
        )

    def _on_ports_checked(self, result: PortCheckResult) -> None:
        if not result.success:
            self._ports_known = False
            self.conflicts_banner.setText(result.detail)
            self._update_start_enabled()
            return

        self._ports_known = True
        self._conflicts = result.conflicts
        self._render_conflicts()

    def _render_conflicts(self) -> None:
        self.conflicts_table.setRowCount(len(self._conflicts))
        for row, conflict in enumerate(self._conflicts):
            self.conflicts_table.setItem(row, 0, QTableWidgetItem(conflict.node_id))
            self.conflicts_table.setItem(
                row, 1, QTableWidgetItem(f"{conflict.host_port}/{conflict.protocol}")
            )
            reason_text = PORT_CONFLICT_REASONS.get(conflict.reason, conflict.reason)
            self.conflicts_table.setItem(row, 2, QTableWidgetItem(reason_text))

            if conflict.recommended_port is not None:
                apply_button = QPushButton(f"Use {conflict.recommended_port}")
                apply_button.clicked.connect(
                    lambda _checked=False, c=conflict: self._on_apply_recommendation(c)
                )
                self.conflicts_table.setCellWidget(row, 3, apply_button)
            else:
                self.conflicts_table.setItem(row, 3, QTableWidgetItem("No port available"))

        if not self._conflicts:
            self.conflicts_banner.setText("No port conflicts detected.")
        else:
            plural = "s" if len(self._conflicts) != 1 else ""
            self.conflicts_banner.setText(
                f"{len(self._conflicts)} port conflict{plural} must be resolved before "
                "starting."
            )
        self._update_start_enabled()

    # ----- subnet conflicts -------------------------------------------------------------

    def _on_networks_checked(self, result: NetworkCheckResult) -> None:
        if not result.success:
            self._networks_known = False
            self.networks_banner.setText(
                f"Could not check Docker networks: {result.detail} "
                "Start stays disabled until this can be verified."
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

        if not self._subnet_conflicts:
            self.networks_banner.setText("No subnet conflicts with existing Docker networks.")
        else:
            plural = "s" if len(self._subnet_conflicts) != 1 else ""
            self.networks_banner.setText(
                f"{len(self._subnet_conflicts)} network{plural} overlap{'' if plural else 's'} "
                "address space already in use on this machine. Docker refuses to create such "
                "networks, so the lab cannot start until each one is fixed."
            )
        self._update_start_enabled()

    def _subnet_fix_widget(self, conflict: SubnetConflict) -> QWidget:
        container = QWidget()
        row = QHBoxLayout(container)
        row.setContentsMargins(2, 2, 2, 2)

        if conflict.reason == "overlaps_leftover":
            remove_button = QPushButton("Remove leftover")
            remove_button.clicked.connect(
                lambda _checked=False, c=conflict: self._on_remove_leftover(c)
            )
            row.addWidget(remove_button)
        elif conflict.reason == "overlaps_other_lab" and conflict.owner_lab_id:
            reset_button = QPushButton(f"Reset '{conflict.owner_lab_name}'")
            reset_button.clicked.connect(
                lambda _checked=False, c=conflict: self._on_reset_owner_lab(c)
            )
            row.addWidget(reset_button)

        if conflict.recommended_subnet:
            use_button = QPushButton(f"Use {conflict.recommended_subnet}")
            use_button.clicked.connect(
                lambda _checked=False, c=conflict: self._on_apply_subnet_recommendation(c)
            )
            row.addWidget(use_button)

        if row.count() == 0:
            row.addWidget(QLabel("No automatic fix available"))
        row.addStretch(1)
        return container

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
        self.networks_banner.setText(progress_text)
        self.start_button.setEnabled(False)
        self._network_fix_worker = CallableWorker(func, *args)
        self._network_fix_worker.finished_call.connect(self._on_network_fix_done)
        self._network_fix_worker.start()

    def _on_network_fix_done(self, result: NetworkCheckResult) -> None:
        if not result.success:
            # Keep the previous conflict list visible; just explain what went wrong.
            self.networks_banner.setText(f"❌ {result.detail}")
            self._update_start_enabled()
            return
        self._on_networks_checked(result)
        if self._subnet_moved_note:
            self.networks_banner.setText(
                f"{self.networks_banner.text()} {self._subnet_moved_note}"
            )
            self._subnet_moved_note = ""
            self._reload_preview()  # topology addresses changed

    def _on_apply_recommendation(self, conflict: PortConflict) -> None:
        self.conflicts_banner.setText("Applying recommended port…")
        self.start_button.setEnabled(False)
        self._apply_worker = CallableWorker(
            self._api_client.apply_port_recommendation,
            self._lab_id,
            conflict.node_id,
            conflict.host_port,
            conflict.protocol,
        )
        self._apply_worker.finished_call.connect(self._on_ports_checked)
        self._apply_worker.start()

    def _on_start_clicked(self) -> None:
        self.start_button.setEnabled(False)
        self.cancel_button.setEnabled(False)
        self.status_label.setText("Starting lab…")
        self._start_worker = CallableWorker(self._api_client.start_lab, self._lab_id)
        self._start_worker.finished_call.connect(self._on_start_finished)
        self._start_worker.start()

    def _on_start_finished(self, result: StartResult) -> None:
        self.cancel_button.setEnabled(True)
        if result.success:
            self.accept()
            return
        self.status_label.setText(f"❌ {result.detail}")
        self._update_start_enabled()
