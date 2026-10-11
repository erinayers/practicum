from __future__ import annotations

from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QGroupBox,
    QHBoxLayout,
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
    PortCheckResult,
    PortConflict,
    PreviewResult,
    StartResult,
)
from practicum_desktop.dialogs import COPYABLE_TEXT_FLAGS
from practicum_desktop.workers import CallableWorker


def _copyable_label(text: str = "") -> QLabel:
    label = QLabel(text)
    label.setWordWrap(True)
    label.setTextInteractionFlags(COPYABLE_TEXT_FLAGS)
    return label


class PreStartGateDialog(QDialog):
    """The mandatory screen between selecting a lab and actually starting it.

    Shows what will run on the student's machine (required images, estimated
    resources, read-only topology, manual step count) and blocks Start until any host
    port conflicts are resolved. See windows-desktop-prestart-lab-gate.md.

    Every entry point capable of starting a lab should route through this same dialog
    rather than re-implementing the gate; today that's the main window's Start button,
    with the Labs Dashboard and Import-and-launch flows expected to reuse it once built.
    """

    def __init__(self, api_client: ApiClient, lab_id: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Review Before Starting")
        self.resize(640, 680)

        self._api_client = api_client
        self._lab_id = lab_id
        self._conflicts: list[PortConflict] = []
        self._preview_worker: CallableWorker | None = None
        self._ports_worker: CallableWorker | None = None
        self._apply_worker: CallableWorker | None = None
        self._start_worker: CallableWorker | None = None

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

    def _on_preview_loaded(self, result: PreviewResult) -> None:
        if not result.success:
            self.name_label.setText("Could not load this lab.")
            self.description_label.setText(result.detail)
            return

        self.name_label.setText(result.name)
        self.description_label.setText(result.description or "No description provided.")

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

    def _on_ports_checked(self, result: PortCheckResult) -> None:
        if not result.success:
            self.conflicts_banner.setText(result.detail)
            self.start_button.setEnabled(False)
            return

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
            self.start_button.setEnabled(True)
        else:
            plural = "s" if len(self._conflicts) != 1 else ""
            self.conflicts_banner.setText(
                f"{len(self._conflicts)} port conflict{plural} must be resolved before "
                "starting."
            )
            self.start_button.setEnabled(False)

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
        self.start_button.setEnabled(not self._conflicts)
