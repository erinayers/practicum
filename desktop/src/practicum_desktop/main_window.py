from __future__ import annotations

import webbrowser

from PySide6.QtCore import Qt, QSettings
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
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
    ApiClient,
    CreateLabResult,
    LabsResult,
    PortCheckResult,
    PortConflict,
    PortMappingInfo,
    PreviewResult,
    StartResult,
)
from practicum_desktop.app_status import AppStatus
from practicum_desktop.designer import DesignerDialog
from practicum_desktop.manual import NO_LAB_SELECTED_MESSAGE, ManualFlyout
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

PORT_CONFLICT_REASONS = {
    "duplicate_in_spec": "Duplicate port in this lab",
    "reserved_by_practicum_api": "Reserved by the Practicum API",
    "in_use_on_host": "Already in use on this machine",
}

COPYABLE_TEXT_FLAGS = (
    Qt.TextInteractionFlag.TextSelectableByMouse | Qt.TextInteractionFlag.TextSelectableByKeyboard
)


def _copyable_label(text: str = "") -> QLabel:
    label = QLabel(text)
    label.setWordWrap(True)
    label.setTextInteractionFlags(COPYABLE_TEXT_FLAGS)
    return label


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Practicum")
        self.resize(480, 420)

        self._settings = QSettings(ORG_NAME, APP_NAME)
        base_url = self._settings.value("api_base_url", DEFAULT_BASE_URL)
        self._api_client = ApiClient(base_url=base_url)
        self._worker: StartupWorker | None = None
        self._port_worker: CallableWorker | None = None
        self._apply_worker: CallableWorker | None = None
        self._start_worker: CallableWorker | None = None
        self._manual_worker: CallableWorker | None = None
        self._quick_start_worker: CallableWorker | None = None
        self._lab_ids: list[str] = []
        self._selected_lab_id: str | None = None

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

        self.new_lab_button = QPushButton("New Lab…")
        self.new_lab_button.clicked.connect(self._on_new_lab_clicked)
        layout.addWidget(self.new_lab_button)

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

        self.start_button = QPushButton("Start Selected Lab")
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

        self._worker = StartupWorker(self._api_client)
        self._worker.finished_check.connect(self._on_status_checked)
        self._worker.start()

    def _on_status_checked(self, status: AppStatus, labs_result: LabsResult | None) -> None:
        self.retry_button.setEnabled(True)
        self.readiness_label.setText(f"Status: {READINESS_LABELS[status.readiness]}")

        api_icon = "✅" if status.api.healthy else "❌"
        self.api_status_label.setText(f"Practicum API: {api_icon} {status.api.detail}")

        docker_icon = "✅" if status.docker.available else "❌"
        self.docker_status_label.setText(f"Docker: {docker_icon} {status.docker.detail}")

        self.next_action_label.setText(status.next_action)

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

    def _on_lab_row_changed(self, row: int) -> None:
        self.port_conflicts_table.setRowCount(0)
        self.port_check_status_label.setText("")
        self.start_button.setEnabled(False)
        self.start_result_label.setText("")
        self.view_manual_button.setEnabled(False)
        self.manual_flyout.show_empty(NO_LAB_SELECTED_MESSAGE)
        self.browser_access_table.setRowCount(0)

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
        self.start_button.setEnabled(not result.has_conflicts)
        self.port_check_status_label.setText(
            "No port conflicts."
            if not result.has_conflicts
            else "Resolve the port conflicts below before starting."
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

        self.start_button.setEnabled(False)
        self.start_result_label.setText("Starting lab…")
        self._start_worker = CallableWorker(self._api_client.start_lab, self._selected_lab_id)
        self._start_worker.finished_call.connect(self._on_start_finished)
        self._start_worker.start()

    def _on_start_finished(self, result: StartResult) -> None:
        icon = "✅" if result.success else "❌"
        self.start_result_label.setText(f"{icon} {result.detail}")
        self.start_button.setEnabled(True)
