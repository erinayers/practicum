from __future__ import annotations

import re
from ipaddress import AddressValueError, IPv4Interface, IPv4Network, NetmaskValueError

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from practicum_desktop.api_client import ApiClient, CreateLabResult, ValidateLabResult
from practicum_desktop.workers import CallableWorker

ID_PATTERN = re.compile(r"^[a-z][a-z0-9-]*$")
ID_HINT = "IDs must start with a lowercase letter and contain only lowercase letters, digits, or hyphens."
SUGGESTED_IMAGES = ["alpine:3.21", "ubuntu:22.04", "nginx:latest"]
COPYABLE_TEXT_FLAGS = (
    Qt.TextInteractionFlag.TextSelectableByMouse | Qt.TextInteractionFlag.TextSelectableByKeyboard
)


def _copyable_label(text: str = "") -> QLabel:
    label = QLabel(text)
    label.setWordWrap(True)
    label.setTextInteractionFlags(COPYABLE_TEXT_FLAGS)
    return label


class DesignerDialog(QDialog):
    """Lets an instructor build a new lab draft and save it via the Practicum API."""

    def __init__(self, api_client: ApiClient, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("New Lab")
        self.resize(640, 640)

        self._api_client = api_client
        self._nodes: list[dict[str, str]] = []
        self._networks: list[dict[str, str]] = []
        self._interfaces: list[dict[str, str]] = []
        self._validate_worker: CallableWorker | None = None
        self._save_worker: CallableWorker | None = None

        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        name_row = QHBoxLayout()
        name_row.addWidget(QLabel("Lab name:"))
        self.name_field = QLineEdit()
        name_row.addWidget(self.name_field)
        layout.addLayout(name_row)

        layout.addWidget(self._build_nodes_group())
        layout.addWidget(self._build_networks_group())
        layout.addWidget(self._build_connections_group())

        self.status_label = _copyable_label()
        layout.addWidget(self.status_label)

        buttons_row = QHBoxLayout()
        self.validate_button = QPushButton("Validate")
        self.validate_button.clicked.connect(self._on_validate_clicked)
        buttons_row.addWidget(self.validate_button)

        self.save_button = QPushButton("Save")
        self.save_button.clicked.connect(self._on_save_clicked)
        buttons_row.addWidget(self.save_button)
        layout.addLayout(buttons_row)

        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def _build_nodes_group(self) -> QGroupBox:
        group = QGroupBox("Nodes")
        group_layout = QVBoxLayout(group)

        entry_row = QHBoxLayout()
        self.node_id_field = QLineEdit()
        self.node_id_field.setPlaceholderText("id")
        entry_row.addWidget(self.node_id_field)

        self.node_image_field = QComboBox()
        self.node_image_field.setEditable(True)
        self.node_image_field.addItems(SUGGESTED_IMAGES)
        self.node_image_field.setCurrentText("")
        entry_row.addWidget(self.node_image_field)

        add_node_button = QPushButton("Add Node")
        add_node_button.clicked.connect(self._on_add_node_clicked)
        entry_row.addWidget(add_node_button)
        group_layout.addLayout(entry_row)

        self.node_error_label = _copyable_label()
        group_layout.addWidget(self.node_error_label)

        self.nodes_table = QTableWidget(0, 3)
        self.nodes_table.setHorizontalHeaderLabels(["ID", "Image", ""])
        self.nodes_table.horizontalHeader().setStretchLastSection(True)
        self.nodes_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        group_layout.addWidget(self.nodes_table)

        return group

    def _build_networks_group(self) -> QGroupBox:
        group = QGroupBox("Networks")
        group_layout = QVBoxLayout(group)

        entry_row = QHBoxLayout()
        self.network_id_field = QLineEdit()
        self.network_id_field.setPlaceholderText("id")
        entry_row.addWidget(self.network_id_field)

        self.network_subnet_field = QLineEdit()
        self.network_subnet_field.setPlaceholderText("10.0.0.0/24")
        entry_row.addWidget(self.network_subnet_field)

        add_network_button = QPushButton("Add Network")
        add_network_button.clicked.connect(self._on_add_network_clicked)
        entry_row.addWidget(add_network_button)
        group_layout.addLayout(entry_row)

        self.network_error_label = _copyable_label()
        group_layout.addWidget(self.network_error_label)

        self.networks_table = QTableWidget(0, 4)
        self.networks_table.setHorizontalHeaderLabels(["ID", "Subnet", "Attached Nodes", ""])
        self.networks_table.horizontalHeader().setStretchLastSection(True)
        self.networks_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        group_layout.addWidget(self.networks_table)

        return group

    def _build_connections_group(self) -> QGroupBox:
        group = QGroupBox("Connections")
        group_layout = QVBoxLayout(group)

        entry_row = QHBoxLayout()
        self.connection_node_combo = QComboBox()
        entry_row.addWidget(self.connection_node_combo)

        self.connection_network_combo = QComboBox()
        entry_row.addWidget(self.connection_network_combo)

        self.connection_address_field = QLineEdit()
        self.connection_address_field.setPlaceholderText("10.0.0.1/24")
        entry_row.addWidget(self.connection_address_field)

        add_connection_button = QPushButton("Connect")
        add_connection_button.clicked.connect(self._on_add_connection_clicked)
        entry_row.addWidget(add_connection_button)
        group_layout.addLayout(entry_row)

        self.connection_error_label = _copyable_label()
        group_layout.addWidget(self.connection_error_label)

        self.connections_table = QTableWidget(0, 4)
        self.connections_table.setHorizontalHeaderLabels(["Node", "Network", "Address", ""])
        self.connections_table.horizontalHeader().setStretchLastSection(True)
        self.connections_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        group_layout.addWidget(self.connections_table)

        return group

    # -- Nodes -----------------------------------------------------------------

    def _on_add_node_clicked(self) -> None:
        node_id = self.node_id_field.text().strip()
        image = self.node_image_field.currentText().strip()

        if not node_id or not ID_PATTERN.match(node_id):
            self.node_error_label.setText(f"Invalid node ID. {ID_HINT}")
            return
        if any(node["id"] == node_id for node in self._nodes):
            self.node_error_label.setText(f"A node with ID '{node_id}' already exists.")
            return
        if not image:
            self.node_error_label.setText("A Docker image is required.")
            return

        self._nodes.append({"id": node_id, "image": image})
        self.node_error_label.setText("")
        self.node_id_field.clear()
        self.node_image_field.setCurrentText("")
        self._refresh_nodes_table()
        self._refresh_connection_combos()

    def _on_remove_node_clicked(self, node_id: str) -> None:
        self._nodes = [node for node in self._nodes if node["id"] != node_id]
        self._interfaces = [
            interface for interface in self._interfaces if interface["node"] != node_id
        ]
        self._refresh_nodes_table()
        self._refresh_networks_table()
        self._refresh_connections_table()
        self._refresh_connection_combos()

    def _refresh_nodes_table(self) -> None:
        self.nodes_table.setRowCount(len(self._nodes))
        for row, node in enumerate(self._nodes):
            self.nodes_table.setItem(row, 0, QTableWidgetItem(node["id"]))
            self.nodes_table.setItem(row, 1, QTableWidgetItem(node["image"]))
            remove_button = QPushButton("Remove")
            remove_button.clicked.connect(
                lambda _checked=False, node_id=node["id"]: self._on_remove_node_clicked(node_id)
            )
            self.nodes_table.setCellWidget(row, 2, remove_button)

    # -- Networks ----------------------------------------------------------------

    def _on_add_network_clicked(self) -> None:
        network_id = self.network_id_field.text().strip()
        subnet_text = self.network_subnet_field.text().strip()

        if not network_id or not ID_PATTERN.match(network_id):
            self.network_error_label.setText(f"Invalid network ID. {ID_HINT}")
            return
        if any(network["id"] == network_id for network in self._networks):
            self.network_error_label.setText(f"A network with ID '{network_id}' already exists.")
            return

        try:
            IPv4Network(subnet_text, strict=True)
        except (AddressValueError, NetmaskValueError, ValueError):
            self.network_error_label.setText(
                f"'{subnet_text}' is not a valid IPv4 CIDR subnet (e.g. 10.0.0.0/24)."
            )
            return

        self._networks.append({"id": network_id, "subnet": subnet_text})
        self.network_error_label.setText("")
        self.network_id_field.clear()
        self.network_subnet_field.clear()
        self._refresh_networks_table()
        self._refresh_connection_combos()

    def _on_remove_network_clicked(self, network_id: str) -> None:
        self._networks = [network for network in self._networks if network["id"] != network_id]
        self._interfaces = [
            interface for interface in self._interfaces if interface["network"] != network_id
        ]
        self._refresh_networks_table()
        self._refresh_connections_table()
        self._refresh_connection_combos()

    def _refresh_networks_table(self) -> None:
        self.networks_table.setRowCount(len(self._networks))
        for row, network in enumerate(self._networks):
            attached_nodes = sorted(
                {
                    interface["node"]
                    for interface in self._interfaces
                    if interface["network"] == network["id"]
                }
            )
            self.networks_table.setItem(row, 0, QTableWidgetItem(network["id"]))
            self.networks_table.setItem(row, 1, QTableWidgetItem(network["subnet"]))
            self.networks_table.setItem(row, 2, QTableWidgetItem(", ".join(attached_nodes) or "—"))
            remove_button = QPushButton("Remove")
            remove_button.clicked.connect(
                lambda _checked=False, network_id=network["id"]: self._on_remove_network_clicked(
                    network_id
                )
            )
            self.networks_table.setCellWidget(row, 3, remove_button)

    # -- Connections ---------------------------------------------------------

    def _refresh_connection_combos(self) -> None:
        self.connection_node_combo.clear()
        self.connection_node_combo.addItems([node["id"] for node in self._nodes])

        self.connection_network_combo.clear()
        self.connection_network_combo.addItems([network["id"] for network in self._networks])

    def _on_add_connection_clicked(self) -> None:
        node_id = self.connection_node_combo.currentText()
        network_id = self.connection_network_combo.currentText()
        address_text = self.connection_address_field.text().strip()

        if not node_id or not network_id:
            self.connection_error_label.setText("Add at least one node and one network first.")
            return

        if any(
            interface["node"] == node_id and interface["network"] == network_id
            for interface in self._interfaces
        ):
            self.connection_error_label.setText(
                f"'{node_id}' already has an interface on '{network_id}'."
            )
            return

        try:
            address = IPv4Interface(address_text)
        except (AddressValueError, NetmaskValueError, ValueError):
            self.connection_error_label.setText(
                f"'{address_text}' is not a valid IPv4 address (e.g. 10.0.0.1/24)."
            )
            return

        subnet_text = next(
            (network["subnet"] for network in self._networks if network["id"] == network_id), None
        )
        if subnet_text is None or address.ip not in IPv4Network(subnet_text, strict=True):
            self.connection_error_label.setText(
                f"'{address_text}' is not part of network '{network_id}' ({subnet_text})."
            )
            return

        if any(
            IPv4Interface(interface["address"]).ip == address.ip for interface in self._interfaces
        ):
            self.connection_error_label.setText(f"Address '{address.ip}' is already assigned.")
            return

        self._interfaces.append({"node": node_id, "network": network_id, "address": address_text})
        self.connection_error_label.setText("")
        self.connection_address_field.clear()
        self._refresh_connections_table()
        self._refresh_networks_table()

    def _on_remove_connection_clicked(self, row: int) -> None:
        del self._interfaces[row]
        self._refresh_connections_table()
        self._refresh_networks_table()

    def _refresh_connections_table(self) -> None:
        self.connections_table.setRowCount(len(self._interfaces))
        for row, interface in enumerate(self._interfaces):
            self.connections_table.setItem(row, 0, QTableWidgetItem(interface["node"]))
            self.connections_table.setItem(row, 1, QTableWidgetItem(interface["network"]))
            self.connections_table.setItem(row, 2, QTableWidgetItem(interface["address"]))
            remove_button = QPushButton("Remove")
            remove_button.clicked.connect(
                lambda _checked=False, row=row: self._on_remove_connection_clicked(row)
            )
            self.connections_table.setCellWidget(row, 3, remove_button)

    # -- Build / Validate / Save ------------------------------------------------

    def _build_definition(self) -> dict[str, object]:
        return {
            "name": self.name_field.text().strip(),
            "nodes": [{"id": node["id"], "image": node["image"]} for node in self._nodes],
            "networks": [
                {"id": network["id"], "subnet": network["subnet"]} for network in self._networks
            ],
            "interfaces": [
                {
                    "node": interface["node"],
                    "network": interface["network"],
                    "address": interface["address"],
                }
                for interface in self._interfaces
            ],
        }

    def _on_validate_clicked(self) -> None:
        self.validate_button.setEnabled(False)
        self.status_label.setText("Validating…")
        self._validate_worker = CallableWorker(
            self._api_client.validate_lab, self._build_definition()
        )
        self._validate_worker.finished_call.connect(self._on_validated)
        self._validate_worker.start()

    def _on_validated(self, result: ValidateLabResult) -> None:
        self.validate_button.setEnabled(True)
        if not result.success:
            self.status_label.setText(result.detail)
            return
        if result.valid:
            self.status_label.setText("The lab is valid.")
            return
        messages = "; ".join(f"{'.'.join(error.location)}: {error.message}" for error in result.errors)
        self.status_label.setText(f"{messages}")

    def _on_save_clicked(self) -> None:
        self.save_button.setEnabled(False)
        self.status_label.setText("Saving…")
        self._save_worker = CallableWorker(self._api_client.create_lab, self._build_definition())
        self._save_worker.finished_call.connect(self._on_saved)
        self._save_worker.start()

    def _on_saved(self, result: CreateLabResult) -> None:
        self.save_button.setEnabled(True)
        if result.success:
            self.accept()
            return
        if result.errors:
            messages = "; ".join(f"{'.'.join(error.location)}: {error.message}" for error in result.errors)
            self.status_label.setText(f"{messages}")
        else:
            self.status_label.setText(f"{result.detail}")
