from __future__ import annotations

import webbrowser

from PySide6.QtCore import QSettings, Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QMainWindow,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from practicum_desktop.api_client import (
    DEFAULT_BASE_URL,
    PORT_CONFLICT_REASONS,
    ApiClient,
    CreateLabResult,
    LabsResult,
    PortCheckResult,
    PortConflict,
    PortMappingInfo,
    PreviewResult,
    ResourceStatusInfo,
    StatusResult,
)
from practicum_desktop.app_status import AppStatus
from practicum_desktop.designer import DesignerDialog
from practicum_desktop.import_lab import ImportLabDialog
from practicum_desktop.manual import NO_LAB_SELECTED_MESSAGE, ManualFlyout
from practicum_desktop.node_shell import ShellLaunchResult, open_node_shell
from practicum_desktop.prestart_gate import PreStartGateDialog
from practicum_desktop.quickstart import UBUNTU_QUICK_START_LAB
from practicum_desktop.startup import StartupWorker
from practicum_desktop.workers import CallableWorker

ORG_NAME = "Practicum"
APP_NAME = "Practicum Desktop"

READINESS_LABELS = {
    "ready": "Ready",
    "degraded": "Degraded",
    "blocked": "Blocked",
}

COPYABLE_TEXT_FLAGS = (
    Qt.TextInteractionFlag.TextSelectableByMouse | Qt.TextInteractionFlag.TextSelectableByKeyboard
)


def _copyable_label(text: str = "") -> QLabel:
    label = QLabel(text)
    label.setWordWrap(True)
    label.setTextInteractionFlags(COPYABLE_TEXT_FLAGS)
    return label


def _container_state_text(container: ResourceStatusInfo) -> str:
    if container.error:
        return f"unknown ({container.error})"
    if not container.exists:
        return "not created"
    return container.status or "unknown"


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Practicum")
        self.resize(560, 760)

        self._settings = QSettings(ORG_NAME, APP_NAME)
        base_url = self._settings.value("api_base_url", DEFAULT_BASE_URL)
        self._api_client = ApiClient(base_url=base_url)
        self._worker: StartupWorker | None = None
        self._port_worker: CallableWorker | None = None
        self._apply_worker: CallableWorker | None = None
        self._manual_worker: CallableWorker | None = None
        self._status_worker: CallableWorker | None = None
        self._shell_worker: CallableWorker | None = None
        self._quick_start_worker: CallableWorker | None = None
        self._lab_ids: list[str] = []
        self._selected_lab_id: str | None = None
        self._last_status: AppStatus | None = None
        # (lab_id, message, show_manual) to apply once the next lab-list refresh lands.
        self._pending_selection: tuple[str, str, bool] | None = None

        self._build_ui(base_url)
        self.check_status()

    def _build_ui(self, base_url: str) -> None:
        central = QWidget()
        layout = QVBoxLayout(central)

        self.readiness_label = QLabel("Checking Practicum status…")
        layout.addWidget(self.readiness_label)

        self.api_status_label = QLabel("Practicum API: checking…")
        layout.addWidget(self.api_status_label)

        self.docker_status_label = QLabel("Docker: checking…")
        layout.addWidget(self.docker_status_label)

        self.next_action_label = _copyable_label()
        layout.addWidget(self.next_action_label)

        url_row = QHBoxLayout()
        url_row.addWidget(QLabel("API base URL:"))
        self.base_url_field = QLineEdit(base_url)
        url_row.addWidget(self.base_url_field)
        layout.addLayout(url_row)

        self.retry_button = QPushButton("Retry")
        self.retry_button.clicked.connect(self._on_retry_clicked)
        layout.addWidget(self.retry_button)

        layout.addWidget(QLabel("Labs:"))
        self.labs_list = QListWidget()
        self.labs_list.currentRowChanged.connect(self._on_lab_row_changed)
        layout.addWidget(self.labs_list)

        lab_actions_row = QHBoxLayout()
        self.new_lab_button = QPushButton("New Lab…")
        self.new_lab_button.clicked.connect(self._on_new_lab_clicked)
        lab_actions_row.addWidget(self.new_lab_button)

        self.import_button = QPushButton("Import Lab File…")
        self.import_button.clicked.connect(self._on_import_clicked)
        lab_actions_row.addWidget(self.import_button)
        layout.addLayout(lab_actions_row)

        self.quick_start_button = QPushButton("Quick Start: Ubuntu")
        self.quick_start_button.clicked.connect(self._on_quick_start_clicked)
        layout.addWidget(self.quick_start_button)

        self.quick_start_status_label = _copyable_label()
        layout.addWidget(self.quick_start_status_label)

        self.view_manual_button = QPushButton("View Manual")
        self.view_manual_button.setEnabled(False)
        self.view_manual_button.clicked.connect(self._on_view_manual_clicked)
        layout.addWidget(self.view_manual_button)

        layout.addWidget(QLabel("Port Conflicts:"))
        self.port_conflicts_table = QTableWidget(0, 4)
        self.port_conflicts_table.setHorizontalHeaderLabels(
            ["Node", "Host Port", "Issue", "Recommended"]
        )
        self.port_conflicts_table.horizontalHeader().setStretchLastSection(True)
        self.port_conflicts_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        layout.addWidget(self.port_conflicts_table)

        self.port_check_status_label = _copyable_label()
        layout.addWidget(self.port_check_status_label)

        layout.addWidget(QLabel("Browser Access:"))
        self.browser_access_table = QTableWidget(0, 3)
        self.browser_access_table.setHorizontalHeaderLabels(
            ["Host Port", "Maps To", ""]
        )
        self.browser_access_table.horizontalHeader().setStretchLastSection(True)
        self.browser_access_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        layout.addWidget(self.browser_access_table)

        layout.addWidget(QLabel("Lab Nodes:"))
        self.nodes_table = QTableWidget(0, 4)
        self.nodes_table.setHorizontalHeaderLabels(["Node", "Container", "State", ""])
        self.nodes_table.horizontalHeader().setStretchLastSection(True)
        self.nodes_table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.ResizeToContents
        )
        self.nodes_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        layout.addWidget(self.nodes_table)

        self.nodes_status_label = _copyable_label()
        layout.addWidget(self.nodes_status_label)

        self.start_button = QPushButton("Start Selected Lab…")
        self.start_button.setEnabled(False)
        self.start_button.clicked.connect(self._on_start_clicked)
        layout.addWidget(self.start_button)

        self.start_result_label = _copyable_label()
        layout.addWidget(self.start_result_label)

        self.setCentralWidget(central)

        self.manual_flyout = ManualFlyout(self._settings, self)
        self.addDockWidget(Qt.DockWidgetArea.RightDockWidgetArea, self.manual_flyout)

    def _on_retry_clicked(self) -> None:
        new_base_url = self.base_url_field.text().strip() or DEFAULT_BASE_URL
        self._settings.setValue("api_base_url", new_base_url)
        self._api_client = ApiClient(base_url=new_base_url)
        self.check_status()

    def _on_new_lab_clicked(self) -> None:
        dialog = DesignerDialog(self._api_client, parent=self)
        if dialog.exec() == DesignerDialog.DialogCode.Accepted:
            self.check_status()

    def _on_import_clicked(self) -> None:
        api_available = self._last_status is not None and self._last_status.api.healthy
        dialog = ImportLabDialog(
            self._api_client, self._settings, parent=self, api_available=api_available
        )
        dialog.exec()
        outcome = dialog.outcome
        if outcome is None:
            return  # cancelled, or the file never became a lab; the dialog already said why

        started = outcome.started
        if outcome.gate_required:
            # Conflicts (or an unanswered port check): the gate owns the Start decision.
            gate = PreStartGateDialog(self._api_client, outcome.lab_id, parent=self)
            started = gate.exec() == PreStartGateDialog.DialogCode.Accepted

        name = outcome.lab_name or outcome.source_path.name
        if started:
            message = f"✅ '{name}' imported and started."
        else:
            message = f"'{name}' imported. Select it below and use Start when ready."
        self._pending_selection = (outcome.lab_id, message, started)
        self.check_status()

    def _on_quick_start_clicked(self) -> None:
        self.quick_start_button.setEnabled(False)
        self.quick_start_status_label.setText("Creating the Ubuntu quick-start lab…")
        self._quick_start_worker = CallableWorker(
            self._api_client.create_lab, UBUNTU_QUICK_START_LAB
        )
        self._quick_start_worker.finished_call.connect(self._on_quick_start_created)
        self._quick_start_worker.start()

    def _on_quick_start_created(self, result: CreateLabResult) -> None:
        self.quick_start_button.setEnabled(True)
        if not result.success:
            self.quick_start_status_label.setText(
                result.detail or "Could not create the quick-start lab."
            )
            return
        self.check_status()
        self.quick_start_status_label.setText("Ubuntu quick-start lab created. Select it below to start it.")

    def _on_view_manual_clicked(self) -> None:
        self.manual_flyout.setVisible(not self.manual_flyout.isVisible())

    def check_status(self) -> None:
        self.retry_button.setEnabled(False)
        self.readiness_label.setText("Checking Practicum status…")
        self.api_status_label.setText("Practicum API: checking…")
        self.docker_status_label.setText("Docker: checking…")
        self.next_action_label.setText("")
        self.labs_list.clear()
        self._lab_ids = []
        self._selected_lab_id = None
        self.port_conflicts_table.setRowCount(0)
        self.port_check_status_label.setText("")
        self.start_button.setEnabled(False)
        self.start_result_label.setText("")
        self.view_manual_button.setEnabled(False)
        self.manual_flyout.show_empty(NO_LAB_SELECTED_MESSAGE)
        self.browser_access_table.setRowCount(0)
        self.nodes_table.setRowCount(0)
        self.nodes_status_label.setText("")

        self._worker = StartupWorker(self._api_client)
        self._worker.finished_check.connect(self._on_status_checked)
        self._worker.start()

    def _on_status_checked(self, status: AppStatus, labs_result: LabsResult | None) -> None:
        self._last_status = status
        self.retry_button.setEnabled(True)
        self.readiness_label.setText(f"Status: {READINESS_LABELS[status.readiness]}")

        api_icon = "✅" if status.api.healthy else "❌"
        self.api_status_label.setText(f"Practicum API: {api_icon} {status.api.detail}")

        docker_icon = "✅" if status.docker.available else "❌"
        self.docker_status_label.setText(f"Docker: {docker_icon} {status.docker.detail}")

        self.next_action_label.setText(status.next_action)

        pending, self._pending_selection = self._pending_selection, None
        if labs_result is None:
            return
        if labs_result.success:
            if not labs_result.labs:
                self.labs_list.addItem("No labs defined yet.")
            for lab in labs_result.labs:
                self.labs_list.addItem(f"{lab.name} ({lab.status})")
                self._lab_ids.append(lab.id)
        else:
            self.labs_list.addItem(labs_result.detail)

        if pending is not None:
            self._apply_pending_selection(*pending)

    def _apply_pending_selection(self, lab_id: str, message: str, show_manual: bool) -> None:
        """Selects a just-created/imported lab once the refreshed list contains it, so the
        user lands on that lab (ports, browser access, manual) without hunting for it."""
        if lab_id not in self._lab_ids:
            return
        self.labs_list.setCurrentRow(self._lab_ids.index(lab_id))
        # Selecting a row clears the result label; set the message after the selection.
        self.start_result_label.setText(message)
        if show_manual:
            self.manual_flyout.setVisible(True)

    def _on_lab_row_changed(self, row: int) -> None:
        self.port_conflicts_table.setRowCount(0)
        self.port_check_status_label.setText("")
        self.start_button.setEnabled(False)
        self.start_result_label.setText("")
        self.view_manual_button.setEnabled(False)
        self.manual_flyout.show_empty(NO_LAB_SELECTED_MESSAGE)
        self.browser_access_table.setRowCount(0)
        self.nodes_table.setRowCount(0)
        self.nodes_status_label.setText("")

        if row < 0 or row >= len(self._lab_ids):
            self._selected_lab_id = None
            return

        self._selected_lab_id = self._lab_ids[row]
        self.port_check_status_label.setText("Checking ports…")
        self._port_worker = CallableWorker(self._api_client.check_ports, self._selected_lab_id)
        self._port_worker.finished_call.connect(self._on_ports_checked)
        self._port_worker.start()

        self.view_manual_button.setEnabled(True)
        self._manual_worker = CallableWorker(self._api_client.get_preview, self._selected_lab_id)
        self._manual_worker.finished_call.connect(self._on_manual_loaded)
        self._manual_worker.start()

        self._refresh_nodes()

    def _refresh_nodes(self) -> None:
        """Loads the selected lab's containers (GET /status) into the Lab Nodes table."""
        if self._selected_lab_id is None:
            return
        self.nodes_status_label.setText("Checking lab nodes…")
        self._status_worker = CallableWorker(self._api_client.get_status, self._selected_lab_id)
        self._status_worker.finished_call.connect(self._on_status_loaded)
        self._status_worker.start()

    def _on_status_loaded(self, result: StatusResult) -> None:
        if self._selected_lab_id is None:
            return
        if not result.success:
            self.nodes_table.setRowCount(0)
            self.nodes_status_label.setText(result.detail)
            return

        containers = result.containers
        self.nodes_table.setRowCount(len(containers))
        running = 0
        for row, container in enumerate(containers):
            self.nodes_table.setItem(row, 0, QTableWidgetItem(container.id))
            self.nodes_table.setItem(row, 1, QTableWidgetItem(container.name))
            self.nodes_table.setItem(row, 2, QTableWidgetItem(_container_state_text(container)))
            shell_button = QPushButton("Open shell")
            is_running = container.exists and container.status == "running"
            shell_button.setEnabled(is_running)
            shell_button.setToolTip(
                "Opens a terminal window inside this node"
                if is_running
                else "Start the lab to open a shell on this node"
            )
            shell_button.clicked.connect(
                lambda _checked=False, c=container: self._on_open_shell_clicked(c)
            )
            self.nodes_table.setCellWidget(row, 3, shell_button)
            running += int(is_running)

        if result.detail:
            self.nodes_status_label.setText(result.detail)
        elif not containers:
            self.nodes_status_label.setText("This lab has no nodes.")
        elif running == 0:
            self.nodes_status_label.setText(
                "No node is running. Start the lab, then use Open shell to work inside a node."
            )
        else:
            self.nodes_status_label.setText(
                f"{running} of {len(containers)} node{'s' if len(containers) != 1 else ''} "
                "running. Open shell gives you a terminal inside a node (node addresses are "
                "only reachable from inside the lab, not from this computer)."
            )

    def _on_open_shell_clicked(self, container: ResourceStatusInfo) -> None:
        self.nodes_status_label.setText(f"Opening a shell on '{container.id}'…")
        self._shell_worker = CallableWorker(open_node_shell, container.name, container.id)
        self._shell_worker.finished_call.connect(self._on_shell_opened)
        self._shell_worker.start()

    def _on_shell_opened(self, result: ShellLaunchResult) -> None:
        text = result.detail
        if not result.success and result.command:
            text = f"{text}\n{' '.join(result.command)}"
        self.nodes_status_label.setText(text)

    def _on_manual_loaded(self, result: PreviewResult) -> None:
        if self._selected_lab_id is None:
            return
        if not result.success:
            self.manual_flyout.show_empty(result.detail)
            self.browser_access_table.setRowCount(0)
            return
        self.manual_flyout.show_lab(self._selected_lab_id, result.name, result.manual_sections)
        self._render_browser_access(result.port_mappings)

    def _render_browser_access(self, port_mappings: list[PortMappingInfo]) -> None:
        self.browser_access_table.setRowCount(len(port_mappings))
        for row, mapping in enumerate(port_mappings):
            self.browser_access_table.setItem(row, 0, QTableWidgetItem(str(mapping.host)))
            self.browser_access_table.setItem(
                row, 1, QTableWidgetItem(f"{mapping.container}/{mapping.protocol}")
            )
            open_button = QPushButton("Open in Browser")
            open_button.clicked.connect(
                lambda _checked=False, port=mapping.host: self._on_open_in_browser_clicked(port)
            )
            self.browser_access_table.setCellWidget(row, 2, open_button)

    def _on_open_in_browser_clicked(self, host_port: int) -> None:
        webbrowser.open(f"http://localhost:{host_port}")

    def _on_ports_checked(self, result: PortCheckResult) -> None:
        if not result.success:
            self.port_check_status_label.setText(result.detail)
            self.start_button.setEnabled(False)
            return

        self._render_port_conflicts(result)
        self.start_button.setEnabled(True)
        self.port_check_status_label.setText(
            "No port conflicts."
            if not result.has_conflicts
            else "Port conflicts exist; Start will let you resolve them before launching."
        )

    def _render_port_conflicts(self, result: PortCheckResult) -> None:
        self.port_conflicts_table.setRowCount(len(result.conflicts))
        for row, conflict in enumerate(result.conflicts):
            self.port_conflicts_table.setItem(row, 0, QTableWidgetItem(conflict.node_id))
            self.port_conflicts_table.setItem(
                row, 1, QTableWidgetItem(f"{conflict.host_port}/{conflict.protocol}")
            )
            reason_text = PORT_CONFLICT_REASONS.get(conflict.reason, conflict.reason)
            self.port_conflicts_table.setItem(row, 2, QTableWidgetItem(reason_text))

            if conflict.recommended_port is not None:
                apply_button = QPushButton(f"Use {conflict.recommended_port}")
                apply_button.clicked.connect(
                    lambda _checked=False, c=conflict: self._on_apply_recommendation(c)
                )
                self.port_conflicts_table.setCellWidget(row, 3, apply_button)
            else:
                self.port_conflicts_table.setItem(row, 3, QTableWidgetItem("No port available"))

    def _on_apply_recommendation(self, conflict: PortConflict) -> None:
        if self._selected_lab_id is None:
            return

        self.port_check_status_label.setText("Applying recommended port…")
        self._apply_worker = CallableWorker(
            self._api_client.apply_port_recommendation,
            self._selected_lab_id,
            conflict.node_id,
            conflict.host_port,
            conflict.protocol,
        )
        self._apply_worker.finished_call.connect(self._on_ports_checked)
        self._apply_worker.start()

    def _on_start_clicked(self) -> None:
        if self._selected_lab_id is None:
            return

        dialog = PreStartGateDialog(self._api_client, self._selected_lab_id, parent=self)
        if dialog.exec() == PreStartGateDialog.DialogCode.Accepted:
            self.start_result_label.setText("✅ Lab started.")
        else:
            self.start_result_label.setText("")

        # Conditions (e.g. port availability, node state) may have changed while the gate
        # was open.
        self._port_worker = CallableWorker(self._api_client.check_ports, self._selected_lab_id)
        self._port_worker.finished_call.connect(self._on_ports_checked)
        self._port_worker.start()
        self._refresh_nodes()
