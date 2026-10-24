"""Custom Lab designer screen (designer-create-new-lab, designer-add-nodes,
designer-add-networks, designer-connect-nodes-networks, designer-visual-topology-builder).

The mockup's `screen-custom`: a Machines panel (cards with icon / id / image and a remove
action), a Network topology panel (the schematic `TopologyView` plus the interfaces table)
and a Networks panel, over a bottom bar with the draft status pill and Validate / Cancel /
Save Lab / Save & Start. All three panels render the same in-memory draft
(`_nodes` / `_networks` / `_interfaces`); validation rules and the API calls
(`POST /labs/validate`, `POST /labs`) are unchanged from the earlier table-based dialog.
No drag-and-drop - positions follow the order things were added (D-6).

Machines are added from a catalogue of presets (`node_catalog.py`: Ubuntu host, Alpine host,
Router, Web server, Ubuntu Desktop, Custom image) so a working host — router — host chain
needs no Docker knowledge; the connect form suggests the next free address on the chosen
network and the Networks panel lists who has which address. `load_lab()` turns the screen
into an editor for an existing lab (incl. quick-start ones); Save then uses `PUT /labs/{id}`.
"""

from __future__ import annotations

import re
from ipaddress import AddressValueError, IPv4Interface, IPv4Network, NetmaskValueError

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
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
from practicum_desktop.api_client import ApiClient, CreateLabResult, ValidateLabResult
from practicum_desktop.node_catalog import (
    PRESETS,
    NodePreset,
    next_node_id,
    preset_by_key,
    preset_for_node,
    suggest_address,
)
from practicum_desktop.widgets import (
    NODE_GATEWAY_GLYPH,
    NODE_HOST_GLYPH,
    BackLink,
    Panel,
    StatusPill,
    TopologyCanvas,
    TopologyLink,
    TopologyNetwork,
    TopologyNode,
    bind,
    bottom_bar,
    copyable_label,
    discard,
    edge_frame,
    make_button,
    node_role,
    page_container,
    payload_of,
    role_label,
    style_frame,
)
from practicum_desktop.workers import CallableWorker

ID_PATTERN = re.compile(r"^[a-z][a-z0-9-]*$")
ID_HINT = (
    "IDs must start with a lowercase letter and contain only lowercase letters, digits, or hyphens."
)
SUGGESTED_IMAGES = ["alpine:3.21", "ubuntu:22.04", "nginx:latest", "frrouting/frr:latest"]
DEFAULT_NAME = "Static routing topology"
# Spec fields the designer does not edit but must carry through when editing an existing lab.
PASS_THROUGH_FIELDS = ("schema_version", "manual")


class MachineRow(QFrame):
    """.machine-row: glyph, id, preset + image (mono), role, remove."""

    removed = Signal(str)

    def __init__(self, node: dict[str, object], link_count: int, parent=None) -> None:
        super().__init__(parent)
        style_frame(self, f"border-bottom: 1px solid {theme.LINE_SOFT};")
        preset = preset_by_key(str(node["preset"])) if node.get("preset") else preset_for_node(node)
        row = QHBoxLayout(self)
        row.setContentsMargins(12, 8, 8, 8)
        row.setSpacing(10)
        glyph = preset.glyph
        if preset.key == "custom":
            glyph = NODE_GATEWAY_GLYPH if link_count >= 2 else NODE_HOST_GLYPH
        icon = QLabel(glyph)
        icon.setFixedSize(30, 30)
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon.setStyleSheet(f"background: {theme.LINE_SOFT}; border-radius: 8px; font-size: 14px;")
        row.addWidget(icon)
        texts = QVBoxLayout()
        texts.setSpacing(0)
        texts.addWidget(role_label(str(node["id"]), "label"))
        image = role_label(str(node["image"]), "mono")
        image.setToolTip(str(node["image"]))
        texts.addWidget(image)
        role_text = preset.title if preset.key != "custom" else "custom image"
        texts.addWidget(role_label(f"{role_text} \u00b7 {node_role(link_count)}", "hint"))
        row.addLayout(texts, 1)
        remove = make_button("\u2715", kind="ghost")
        remove.setToolTip(f"Remove machine '{node['id']}' and its connections")
        remove.setStyleSheet("padding: 2px 6px;")
        bind(remove, self._on_remove_clicked, node["id"])
        row.addWidget(remove, 0, Qt.AlignmentFlag.AlignTop)

    def _on_remove_clicked(self) -> None:
        self.removed.emit(payload_of(self.sender()))


class NetworkRow(QFrame):
    removed = Signal(str)

    def __init__(
        self, network: dict[str, str], attached: list[tuple[str, str]], parent=None
    ) -> None:
        """`attached` = (node id, address) pairs - the address reference instructors asked for."""
        super().__init__(parent)
        style_frame(self, f"border-bottom: 1px solid {theme.LINE_SOFT};")
        row = QHBoxLayout(self)
        row.setContentsMargins(12, 8, 8, 8)
        texts = QVBoxLayout()
        texts.setSpacing(0)
        texts.addWidget(role_label(network["id"], "label"))
        texts.addWidget(role_label(network["subnet"], "mono"))
        if attached:
            for node_id, address in attached:
                texts.addWidget(role_label(f"{node_id} \u00b7 {address.split('/')[0]}", "hint"))
        else:
            texts.addWidget(role_label("no machines yet", "hint"))
        row.addLayout(texts, 1)
        remove = make_button("\u2715", kind="ghost")
        remove.setToolTip(f"Remove network '{network['id']}' and its connections")
        remove.setStyleSheet("padding: 2px 6px;")
        bind(remove, self._on_remove_clicked, network["id"])
        row.addWidget(remove, 0, Qt.AlignmentFlag.AlignTop)

    def _on_remove_clicked(self) -> None:
        self.removed.emit(payload_of(self.sender()))


class DesignerView(QWidget):
    """Lets an instructor build a new lab draft and save it via the Practicum API."""

    back_requested = Signal()
    cancel_requested = Signal()
    saved = Signal(str, bool)  # lab_id, start_after_save

    def __init__(self, api_client: ApiClient, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._api_client = api_client
        self._nodes: list[dict[str, object]] = []
        self._networks: list[dict[str, str]] = []
        self._interfaces: list[dict[str, str]] = []
        self._editing_lab_id: str | None = None
        self._pass_through: dict[str, object] = {}
        self._validate_worker: CallableWorker | None = None
        self._save_worker: CallableWorker | None = None
        self._start_after_save = False
        self._machine_rows: list[QWidget] = []
        self._network_rows: list[QWidget] = []
        self._build_ui()
        self.reset()

    # ----- UI --------------------------------------------------------------------------

    def _build_ui(self) -> None:
        self.setObjectName("screen")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        page, layout = page_container((44, 20, 44, 14))
        outer.addWidget(page, 1)

        self.back_button = BackLink("Back to lab selection")
        self.back_button.clicked.connect(self.back_requested.emit)
        layout.addWidget(self.back_button)
        self.title_label = role_label("Build your Custom Lab", "h1")
        layout.addWidget(self.title_label)
        self.subtitle_label = role_label(
            "Add machines, connect them into networks, and define each host's role.",
            "subtitle",
        )
        layout.addWidget(self.subtitle_label)

        details = QHBoxLayout()
        details.setSpacing(12)
        name_block = QVBoxLayout()
        name_block.setSpacing(4)
        name_block.addWidget(role_label("Lab name", "label"))
        self.name_field = QLineEdit()
        self.name_field.setMinimumWidth(240)
        self.name_field.setMaxLength(120)
        self.name_field.setPlaceholderText(DEFAULT_NAME)
        self.name_field.textChanged.connect(self._on_name_changed)
        name_block.addWidget(self.name_field)
        details.addLayout(name_block, 2)
        description_block = QVBoxLayout()
        description_block.setSpacing(4)
        description_block.addWidget(role_label("Description", "label"))
        self.description_field = QLineEdit()
        self.description_field.setMaxLength(2000)
        self.description_field.setPlaceholderText("One line students see before starting")
        description_block.addWidget(self.description_field)
        details.addLayout(description_block, 3)
        author_block = QVBoxLayout()
        author_block.setSpacing(4)
        author_block.addWidget(role_label("Author", "label"))
        self.author_field = QLineEdit()
        self.author_field.setMaxLength(120)
        self.author_field.setPlaceholderText("optional")
        author_block.addWidget(self.author_field)
        details.addLayout(author_block, 1)
        version_block = QVBoxLayout()
        version_block.setSpacing(4)
        version_block.addWidget(role_label("Version", "label"))
        self.version_field = QLineEdit()
        self.version_field.setMaxLength(40)
        self.version_field.setPlaceholderText("e.g. 1.0")
        self.version_field.setMaximumWidth(110)
        version_block.addWidget(self.version_field)
        details.addLayout(version_block, 0)
        layout.addLayout(details)

        body = QHBoxLayout()
        body.setSpacing(18)
        body.addWidget(self._build_machines_panel())
        body.addWidget(self._build_topology_panel(), 1)
        body.addWidget(self._build_networks_panel())
        layout.addLayout(body, 1)

        self.status_label = copyable_label("")
        self.status_label.setProperty("banner", "info")
        self.status_label.hide()
        layout.addWidget(self.status_label)

        bar, bar_row = bottom_bar()
        self.status_pill = StatusPill("")
        bar_row.addWidget(self.status_pill, 1)
        self.validate_button = make_button("Validate")
        self.validate_button.clicked.connect(self._on_validate_clicked)
        bar_row.addWidget(self.validate_button)
        self.cancel_button = make_button("Cancel")
        self.cancel_button.clicked.connect(self.cancel_requested.emit)
        bar_row.addWidget(self.cancel_button)
        self.save_button = make_button("Save Lab", kind="primary")
        self.save_button.setToolTip("Store the lab and return to your labs")
        bind(self.save_button, self._on_save_button_clicked, False)
        bar_row.addWidget(self.save_button)
        self.save_start_button = make_button("Save && Start", kind="primary")
        self.save_start_button.setToolTip("Store the lab and review it before starting")
        bind(self.save_start_button, self._on_save_button_clicked, True)
        bar_row.addWidget(self.save_start_button)
        outer.addWidget(bar)

    def _build_machines_panel(self) -> QWidget:
        self.machines_panel = Panel("Machines", padding=0)
        self.machines_panel.setFixedWidth(250)
        self.machines_panel.set_count(0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        host = QWidget()
        self.machines_layout = QVBoxLayout(host)
        self.machines_layout.setContentsMargins(0, 0, 0, 0)
        self.machines_layout.setSpacing(0)
        self.machines_layout.addStretch(1)
        scroll.setWidget(host)
        self.machines_panel.body_layout.addWidget(scroll, 1)

        form = edge_frame("top", theme.LINE, "dashed")
        form_layout = QVBoxLayout(form)
        form_layout.setContentsMargins(12, 10, 12, 12)
        form_layout.setSpacing(6)
        form_layout.addWidget(role_label("+ Add machine", "label"))
        self.preset_combo = QComboBox()
        for preset in PRESETS:
            self.preset_combo.addItem(f"{preset.glyph}  {preset.title}", preset.key)
        self.preset_combo.setToolTip("Ready-made machine types; pick Custom image to type your own")
        self.preset_combo.currentIndexChanged.connect(self._on_preset_changed)
        form_layout.addWidget(self.preset_combo)
        self.preset_description = role_label("", "hint", wrap=True)
        form_layout.addWidget(self.preset_description)
        self.node_id_field = QLineEdit()
        self.node_id_field.setPlaceholderText("id, e.g. router")
        form_layout.addWidget(self.node_id_field)
        self.node_image_field = QComboBox()
        self.node_image_field.setEditable(True)
        self.node_image_field.addItems(SUGGESTED_IMAGES)
        self.node_image_field.setCurrentText("")
        self.node_image_field.lineEdit().setPlaceholderText("Docker image, e.g. alpine:3.21")
        form_layout.addWidget(self.node_image_field)
        self.node_error_label = copyable_label("", role="error")
        self.node_error_label.setStyleSheet("font-size: 11px;")
        self.node_error_label.hide()
        form_layout.addWidget(self.node_error_label)
        add_node_button = make_button("Add machine", small=True)
        add_node_button.clicked.connect(self._on_add_node_clicked)
        self.node_id_field.returnPressed.connect(self._on_add_node_clicked)
        form_layout.addWidget(add_node_button)
        self.machines_panel.body_layout.addWidget(form)
        return self.machines_panel

    def _build_topology_panel(self) -> QWidget:
        self.topology_panel = Panel("Network topology", padding=0)
        self.topology_canvas = TopologyCanvas()
        self.topology_canvas.setMinimumHeight(150)
        self.topology_canvas.setMaximumHeight(190)
        self.topology_canvas.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding
        )
        canvas_wrap = QWidget()
        canvas_layout = QVBoxLayout(canvas_wrap)
        canvas_layout.setContentsMargins(14, 14, 14, 8)
        canvas_layout.addWidget(self.topology_canvas)
        self.topology_panel.body_layout.addWidget(canvas_wrap, 1)

        self.connections_table = QTableWidget(0, 4)
        self.connections_table.setHorizontalHeaderLabels(["Node", "Network", "Address", ""])
        header = self.connections_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setStretchLastSection(False)
        self.connections_table.setColumnWidth(3, 48)
        self.connections_table.verticalHeader().hide()
        self.connections_table.verticalHeader().setDefaultSectionSize(30)
        self.connections_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.connections_table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.connections_table.setMinimumHeight(120)
        table_wrap = QWidget()
        table_layout = QVBoxLayout(table_wrap)
        table_layout.setContentsMargins(14, 0, 14, 6)
        table_layout.addWidget(self.connections_table)
        self.topology_panel.body_layout.addWidget(table_wrap)

        connect_form = edge_frame("top", theme.LINE, "dashed")
        connect_layout = QVBoxLayout(connect_form)
        connect_layout.setContentsMargins(14, 8, 14, 12)
        connect_layout.setSpacing(6)
        connect_layout.addWidget(role_label("+ Connect a machine to a network", "label"))
        entry_row = QHBoxLayout()
        entry_row.setSpacing(8)
        self.connection_node_combo = QComboBox()
        self.connection_node_combo.setPlaceholderText("machine")
        self.connection_node_combo.currentIndexChanged.connect(self._on_connection_target_changed)
        entry_row.addWidget(self.connection_node_combo, 1)
        self.connection_network_combo = QComboBox()
        self.connection_network_combo.setPlaceholderText("network")
        self.connection_network_combo.currentIndexChanged.connect(
            self._on_connection_target_changed
        )
        entry_row.addWidget(self.connection_network_combo, 1)
        self.connection_address_field = QLineEdit()
        self.connection_address_field.setPlaceholderText("address, e.g. 10.0.1.10/24")
        self.connection_address_field.setToolTip(
            "Pre-filled with the next free address on the chosen network; change it if you like"
        )
        self.connection_address_field.returnPressed.connect(self._on_add_connection_clicked)
        entry_row.addWidget(self.connection_address_field, 1)
        connect_button = make_button("Connect", small=True)
        connect_button.clicked.connect(self._on_add_connection_clicked)
        entry_row.addWidget(connect_button)
        connect_layout.addLayout(entry_row)
        self.address_reference_label = role_label("", "hint", wrap=True)
        connect_layout.addWidget(self.address_reference_label)
        self.connection_error_label = copyable_label("", role="error")
        self.connection_error_label.setStyleSheet("font-size: 11px;")
        self.connection_error_label.hide()
        connect_layout.addWidget(self.connection_error_label)
        self.topology_panel.body_layout.addWidget(connect_form)
        return self.topology_panel

    def _build_networks_panel(self) -> QWidget:
        self.networks_panel = Panel("Networks", padding=0)
        self.networks_panel.setFixedWidth(230)
        self.networks_panel.set_count(0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        host = QWidget()
        self.networks_layout = QVBoxLayout(host)
        self.networks_layout.setContentsMargins(0, 0, 0, 0)
        self.networks_layout.setSpacing(0)
        self.networks_layout.addStretch(1)
        scroll.setWidget(host)
        self.networks_panel.body_layout.addWidget(scroll, 1)

        form = edge_frame("top", theme.LINE, "dashed")
        form_layout = QVBoxLayout(form)
        form_layout.setContentsMargins(12, 10, 12, 12)
        form_layout.setSpacing(6)
        form_layout.addWidget(role_label("+ Add network", "label"))
        self.network_id_field = QLineEdit()
        self.network_id_field.setPlaceholderText("id, e.g. lan")
        form_layout.addWidget(self.network_id_field)
        self.network_subnet_field = QLineEdit()
        self.network_subnet_field.setPlaceholderText("subnet, e.g. 10.0.1.0/24")
        self.network_subnet_field.returnPressed.connect(self._on_add_network_clicked)
        form_layout.addWidget(self.network_subnet_field)
        self.network_error_label = copyable_label("", role="error")
        self.network_error_label.setStyleSheet("font-size: 11px;")
        self.network_error_label.hide()
        form_layout.addWidget(self.network_error_label)
        add_network_button = make_button("Add network", small=True)
        add_network_button.clicked.connect(self._on_add_network_clicked)
        form_layout.addWidget(add_network_button)
        self.networks_panel.body_layout.addWidget(form)
        return self.networks_panel

    # ----- draft state ---------------------------------------------------------------------

    def reset(self) -> None:
        """Empties the draft (a fresh 'New Lab')."""
        self._nodes = []
        self._networks = []
        self._interfaces = []
        self._start_after_save = False
        self._editing_lab_id = None
        self._pass_through = {}
        self.title_label.setText("Build your Custom Lab")
        self.subtitle_label.setText(
            "Add machines, connect them into networks, and define each host's role."
        )
        self.save_button.setText("Save Lab")
        self.name_field.clear()
        self.description_field.clear()
        self.author_field.clear()
        self.version_field.clear()
        self.node_id_field.clear()
        self.node_image_field.setCurrentText("")
        self.preset_combo.setCurrentIndex(0)
        self._on_preset_changed(0)
        self.network_id_field.clear()
        self.network_subnet_field.clear()
        self.connection_address_field.clear()
        for label in (self.node_error_label, self.network_error_label, self.connection_error_label):
            label.hide()
        self.status_label.hide()
        self.validate_button.setEnabled(True)
        self.save_button.setEnabled(True)
        self.save_start_button.setEnabled(True)
        self._refresh_all()

    def load_lab(self, lab_id: str, lab: dict[str, object]) -> None:
        """Turns the screen into an editor for an existing lab (any origin, incl. quick start).
        Fields the designer does not edit (manual, schema_version) are carried through."""
        self.reset()
        self._editing_lab_id = lab_id
        self._pass_through = {k: lab[k] for k in PASS_THROUGH_FIELDS if lab.get(k) is not None}
        self.title_label.setText("Edit your lab")
        self.subtitle_label.setText(
            "Change machines, networks and connections; the lab's manual is kept as it is. "
            "Saving returns the lab to Ready, so Start it again afterwards."
        )
        self.save_button.setText("Save changes")
        self.name_field.setText(str(lab.get("name") or ""))
        self.description_field.setText(str(lab.get("description") or ""))
        self.author_field.setText(str(lab.get("author") or ""))
        self.version_field.setText(str(lab.get("version") or ""))
        for node in lab.get("nodes") or []:
            node_copy = {k: v for k, v in dict(node).items() if v is not None or k == "command"}
            node_copy["preset"] = preset_for_node(node_copy).key
            self._nodes.append(node_copy)
        self._networks = [
            {"id": str(n["id"]), "subnet": str(n["subnet"])} for n in lab.get("networks") or []
        ]
        self._interfaces = [
            {"node": str(i["node"]), "network": str(i["network"]), "address": str(i["address"])}
            for i in lab.get("interfaces") or []
        ]
        self._refresh_all()
        self._on_preset_changed(self.preset_combo.currentIndex())

    @property
    def editing_lab_id(self) -> str | None:
        return self._editing_lab_id

    @property
    def nodes(self) -> list[dict[str, object]]:
        return [dict(node) for node in self._nodes]

    @property
    def networks(self) -> list[dict[str, str]]:
        return [dict(network) for network in self._networks]

    @property
    def interfaces(self) -> list[dict[str, str]]:
        return [dict(interface) for interface in self._interfaces]

    def _links_of(self, node_id: str) -> int:
        return sum(1 for interface in self._interfaces if interface["node"] == node_id)

    def _refresh_all(self) -> None:
        self._refresh_machines()
        self._refresh_networks()
        self._refresh_connections()
        self._refresh_connection_combos()
        self._refresh_topology()
        self._update_status()

    # -- Machines ---------------------------------------------------------------------

    def _set_error(self, label: QLabel, text: str) -> None:
        label.setText(text)
        label.setVisible(bool(text))

    def selected_preset(self) -> NodePreset:
        return preset_by_key(self.preset_combo.currentData())

    def _on_preset_changed(self, _index: int) -> None:
        preset = self.selected_preset()
        self.preset_description.setText(preset.description)
        self.node_image_field.setVisible(preset.editable_image)
        if not preset.editable_image:
            self.node_image_field.setCurrentText(preset.image)
        elif self.node_image_field.currentText() in {p.image for p in PRESETS}:
            self.node_image_field.setCurrentText("")
        self.node_id_field.setText(
            next_node_id(preset.id_prefix, [str(n["id"]) for n in self._nodes])
        )
        self.node_id_field.selectAll()

    def _on_add_node_clicked(self) -> None:
        preset = self.selected_preset()
        node_id = self.node_id_field.text().strip()
        image = (
            self.node_image_field.currentText().strip() if preset.editable_image else preset.image
        )

        if not node_id or not ID_PATTERN.match(node_id):
            self._set_error(self.node_error_label, f"Invalid machine ID. {ID_HINT}")
            return
        if any(node["id"] == node_id for node in self._nodes):
            self._set_error(self.node_error_label, f"A machine with ID '{node_id}' already exists.")
            return
        if not image:
            self._set_error(self.node_error_label, "A Docker image is required.")
            return

        node = preset.node(node_id, image)
        node["preset"] = preset.key
        self._nodes.append(node)
        self._set_error(self.node_error_label, "")
        if preset.editable_image:
            self.node_image_field.setCurrentText("")
        self._refresh_all()
        self.node_id_field.setText(
            next_node_id(preset.id_prefix, [str(n["id"]) for n in self._nodes])
        )

    def _on_remove_node_clicked(self, node_id: str) -> None:
        self._nodes = [node for node in self._nodes if node["id"] != node_id]
        self._interfaces = [i for i in self._interfaces if i["node"] != node_id]
        self._refresh_all()

    def _refresh_machines(self) -> None:
        for row in self._machine_rows:
            self.machines_layout.removeWidget(row)
            discard(row)
        self._machine_rows = []
        for node in self._nodes:
            row = MachineRow(node, self._links_of(node["id"]))
            row.removed.connect(self._on_remove_node_clicked)
            self.machines_layout.insertWidget(self.machines_layout.count() - 1, row)
            self._machine_rows.append(row)
        self.machines_panel.set_count(len(self._nodes))

    # -- Networks ---------------------------------------------------------------------

    def _on_add_network_clicked(self) -> None:
        network_id = self.network_id_field.text().strip()
        subnet_text = self.network_subnet_field.text().strip()

        if not network_id or not ID_PATTERN.match(network_id):
            self._set_error(self.network_error_label, f"Invalid network ID. {ID_HINT}")
            return
        if any(network["id"] == network_id for network in self._networks):
            self._set_error(
                self.network_error_label, f"A network with ID '{network_id}' already exists."
            )
            return

        try:
            subnet = IPv4Network(subnet_text, strict=True)
        except (AddressValueError, NetmaskValueError, ValueError):
            self._set_error(
                self.network_error_label,
                f"'{subnet_text}' is not a valid IPv4 CIDR subnet (e.g. 10.0.0.0/24).",
            )
            return
        overlapping = next(
            (n for n in self._networks if IPv4Network(n["subnet"]).overlaps(subnet)), None
        )
        if overlapping is not None:
            self._set_error(
                self.network_error_label,
                f"'{subnet_text}' overlaps network '{overlapping['id']}' "
                f"({overlapping['subnet']}).",
            )
            return

        self._networks.append({"id": network_id, "subnet": subnet_text})
        self._set_error(self.network_error_label, "")
        self.network_id_field.clear()
        self.network_subnet_field.clear()
        self._refresh_all()

    def _on_remove_network_clicked(self, network_id: str) -> None:
        self._networks = [network for network in self._networks if network["id"] != network_id]
        self._interfaces = [i for i in self._interfaces if i["network"] != network_id]
        self._refresh_all()

    def _refresh_networks(self) -> None:
        for row in self._network_rows:
            self.networks_layout.removeWidget(row)
            discard(row)
        self._network_rows = []
        for network in self._networks:
            attached = sorted(
                (i["node"], i["address"]) for i in self._interfaces if i["network"] == network["id"]
            )
            row = NetworkRow(network, attached)
            row.removed.connect(self._on_remove_network_clicked)
            self.networks_layout.insertWidget(self.networks_layout.count() - 1, row)
            self._network_rows.append(row)
        self.networks_panel.set_count(len(self._networks))

    # -- Connections ---------------------------------------------------------------

    def _refresh_connection_combos(self) -> None:
        node = self.connection_node_combo.currentText()
        network = self.connection_network_combo.currentText()
        self.connection_node_combo.clear()
        self.connection_node_combo.addItems([n["id"] for n in self._nodes])
        self.connection_network_combo.clear()
        self.connection_network_combo.addItems([n["id"] for n in self._networks])
        if node:
            self.connection_node_combo.setCurrentText(node)
        if network:
            self.connection_network_combo.setCurrentText(network)
        self._on_connection_target_changed()

    def _on_connection_target_changed(self, _index: int = 0) -> None:
        """Pre-fills the next free address on the chosen network and lists who already has one."""
        network_id = self.connection_network_combo.currentText()
        node_id = self.connection_node_combo.currentText()
        network = next((n for n in self._networks if n["id"] == network_id), None)
        if network is None:
            self.connection_address_field.clear()
            self.address_reference_label.setText("")
            return
        on_network = [i for i in self._interfaces if i["network"] == network_id]
        node = next((n for n in self._nodes if n["id"] == node_id), None)
        role = preset_by_key(str(node.get("preset") or "")).role if node else "host"
        suggestion = suggest_address(network["subnet"], [i["address"] for i in on_network], role)
        self.connection_address_field.setText(suggestion)
        taken = ", ".join(f"{i['node']} {i['address'].split('/')[0]}" for i in on_network)
        gateway = IPv4Network(network["subnet"], strict=False).broadcast_address - 1
        self.address_reference_label.setText(
            f"{network_id} ({network['subnet']}): "
            + (f"{taken} \u00b7 " if taken else "no machines yet \u00b7 ")
            + f"next free {suggestion.split('/')[0] if suggestion else '-'} "
            f"\u00b7 Docker gateway {gateway} (reserved)"
        )

    def _on_add_connection_clicked(self) -> None:
        node_id = self.connection_node_combo.currentText()
        network_id = self.connection_network_combo.currentText()
        address_text = self.connection_address_field.text().strip()

        if not node_id or not network_id:
            self._set_error(
                self.connection_error_label, "Add at least one machine and one network first."
            )
            return

        if any(i["node"] == node_id and i["network"] == network_id for i in self._interfaces):
            self._set_error(
                self.connection_error_label,
                f"'{node_id}' already has an interface on '{network_id}'.",
            )
            return

        try:
            address = IPv4Interface(address_text)
        except (AddressValueError, NetmaskValueError, ValueError):
            self._set_error(
                self.connection_error_label,
                f"'{address_text}' is not a valid IPv4 address (e.g. 10.0.0.1/24).",
            )
            return

        subnet_text = next((n["subnet"] for n in self._networks if n["id"] == network_id), None)
        subnet = IPv4Network(subnet_text, strict=True) if subnet_text else None
        if subnet is None or address.ip not in subnet:
            self._set_error(
                self.connection_error_label,
                f"'{address_text}' is not part of network '{network_id}' ({subnet_text}).",
            )
            return
        if address.ip in (subnet.network_address, subnet.broadcast_address):
            self._set_error(
                self.connection_error_label,
                f"'{address.ip}' is the network or broadcast address of '{network_id}'; "
                "pick a host address.",
            )
            return

        if any(IPv4Interface(i["address"]).ip == address.ip for i in self._interfaces):
            self._set_error(
                self.connection_error_label, f"Address '{address.ip}' is already assigned."
            )
            return

        self._interfaces.append({"node": node_id, "network": network_id, "address": address_text})
        self._set_error(self.connection_error_label, "")
        self.connection_address_field.clear()
        self._refresh_all()

    def _on_remove_connection_button(self) -> None:
        row = payload_of(self.sender())
        if row is not None:
            self._on_remove_connection_clicked(int(row))

    def _on_remove_connection_clicked(self, row: int) -> None:
        if 0 <= row < len(self._interfaces):
            del self._interfaces[row]
        self._refresh_all()

    def _refresh_connections(self) -> None:
        self.connections_table.setRowCount(0)  # drops old cell widgets before re-adding
        self.connections_table.setRowCount(len(self._interfaces))
        for row, interface in enumerate(self._interfaces):
            self.connections_table.setItem(row, 0, QTableWidgetItem(interface["node"]))
            self.connections_table.setItem(row, 1, QTableWidgetItem(interface["network"]))
            self.connections_table.setItem(row, 2, QTableWidgetItem(interface["address"]))
            remove_button = QPushButton("\u2715")
            remove_button.setProperty("kind", "ghost")
            remove_button.setToolTip("Remove this connection")
            remove_button.setStyleSheet("padding: 0 4px;")
            bind(remove_button, self._on_remove_connection_button, row)
            self.connections_table.setCellWidget(row, 3, remove_button)

    def _refresh_topology(self) -> None:
        self.topology_canvas.set_topology(
            [TopologyNode(n["id"], n["image"]) for n in self._nodes],
            [TopologyNetwork(n["id"], n["subnet"]) for n in self._networks],
            [TopologyLink(i["node"], i["network"], i["address"]) for i in self._interfaces],
        )

    # -- Build / Validate / Save ------------------------------------------------------

    def _build_definition(self) -> dict[str, object]:
        definition: dict[str, object] = dict(self._pass_through)
        definition["name"] = self.name_field.text().strip()
        for key, field in (
            ("description", self.description_field),
            ("author", self.author_field),
            ("version", self.version_field),
        ):
            value = field.text().strip()
            if value:
                definition[key] = value
        definition["nodes"] = [
            {k: v for k, v in node.items() if k != "preset"} for node in self._nodes
        ]
        definition["networks"] = [
            {"id": network["id"], "subnet": network["subnet"]} for network in self._networks
        ]
        definition["interfaces"] = [
            {
                "node": interface["node"],
                "network": interface["network"],
                "address": interface["address"],
            }
            for interface in self._interfaces
        ]
        return definition

    def draft_problems(self) -> list[str]:
        """Client-side checks mirrored from the server (the server stays authoritative)."""
        problems: list[str] = []
        if not self.name_field.text().strip():
            problems.append("a lab name")
        if not self._nodes:
            problems.append("at least one machine")
        if not self._networks:
            problems.append("at least one network")
        unconnected = [n["id"] for n in self._nodes if self._links_of(n["id"]) == 0]
        if unconnected:
            problems.append(f"a connection for {', '.join(unconnected)}")
        return problems

    def _update_status(self) -> None:
        problems = self.draft_problems()
        machines = f"{len(self._nodes)} machine{'s' if len(self._nodes) != 1 else ''}"
        networks = f"{len(self._networks)} network{'s' if len(self._networks) != 1 else ''}"
        if problems:
            self.status_pill.set_state(
                f"Draft needs {', '.join(problems)} \u00b7 {machines} \u00b7 {networks}",
                theme.AMBER,
            )
        else:
            self.status_pill.set_state(
                f"Draft valid \u00b7 {machines} \u00b7 {networks}", theme.GREEN
            )

    def _show_status(self, text: str, banner: str) -> None:
        self.status_label.setText(text)
        self.status_label.setProperty("banner", banner)
        theme.restyle(self.status_label)
        self.status_label.setVisible(bool(text))

    def _on_name_changed(self, _text: str) -> None:
        self._update_status()

    def _on_save_button_clicked(self) -> None:
        self._on_save_clicked(start=bool(payload_of(self.sender())))

    def _on_validate_clicked(self) -> None:
        self.validate_button.setEnabled(False)
        self._show_status("Validating\u2026", "info")
        self._validate_worker = CallableWorker(
            self._api_client.validate_lab, self._build_definition()
        )
        self._validate_worker.finished_call.connect(self._on_validated)
        self._validate_worker.start()

    def _on_validated(self, result: ValidateLabResult) -> None:
        self.validate_button.setEnabled(True)
        if not result.success:
            self._show_status(result.detail, "error")
            return
        if result.valid:
            self._show_status("\u2713 The lab is valid.", "ok")
            return
        messages = "; ".join(
            f"{'.'.join(error.location)}: {error.message}" for error in result.errors
        )
        self._show_status(messages, "error")

    def _on_save_clicked(self, start: bool) -> None:
        self._start_after_save = start
        self.save_button.setEnabled(False)
        self.save_start_button.setEnabled(False)
        self._show_status("Saving\u2026", "info")
        if self._editing_lab_id is not None:
            self._save_worker = CallableWorker(
                self._api_client.update_lab, self._editing_lab_id, self._build_definition()
            )
        else:
            self._save_worker = CallableWorker(
                self._api_client.create_lab, self._build_definition()
            )
        self._save_worker.finished_call.connect(self._on_saved)
        self._save_worker.start()

    def _on_saved(self, result: CreateLabResult) -> None:
        self.save_button.setEnabled(True)
        self.save_start_button.setEnabled(True)
        if result.success and result.lab_id:
            self._show_status("", "info")
            self.saved.emit(result.lab_id, self._start_after_save)
            return
        if result.errors:
            messages = "; ".join(
                f"{'.'.join(error.location)}: {error.message}" for error in result.errors
            )
            self._show_status(messages, "error")
        else:
            self._show_status(result.detail, "error")
