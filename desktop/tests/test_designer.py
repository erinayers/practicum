from __future__ import annotations

import pytest
from qt_helpers import ImmediateWorker

from practicum_desktop import designer
from practicum_desktop.api_client import CreateLabResult, FieldIssue, ValidateLabResult
from PySide6.QtWidgets import QLabel

from practicum_desktop.designer import DesignerView
from practicum_desktop.manual import StepMarker
from practicum_desktop.quickstart import QuickStartStep


class FakeApiClient:
    def __init__(self) -> None:
        self.validate_result = ValidateLabResult(success=True, valid=True)
        self.create_result = CreateLabResult(success=True, lab_id="lab-new")
        self.validated: list[dict] = []
        self.created: list[dict] = []
        self.updated: list[tuple[str, dict]] = []

    def validate_lab(self, definition: dict) -> ValidateLabResult:
        self.validated.append(definition)
        return self.validate_result

    def create_lab(self, definition: dict, origin: str = "designer") -> CreateLabResult:
        self.created.append(definition)
        return self.create_result

    def update_lab(self, lab_id: str, definition: dict) -> CreateLabResult:
        self.updated.append((lab_id, definition))
        return self.create_result


@pytest.fixture
def view(monkeypatch):
    monkeypatch.setattr(designer, "CallableWorker", ImmediateWorker)
    api = FakeApiClient()
    widget = DesignerView(api)
    widget.api = api
    return widget


def _select_preset(view: DesignerView, key: str) -> None:
    view.preset_combo.setCurrentIndex(view.preset_combo.findData(key))


def _add_node(view: DesignerView, node_id: str, image: str = "alpine:3.21") -> None:
    """Adds a machine the free-form way (Custom image preset), as the old table UI did."""
    _select_preset(view, "custom")
    view.node_id_field.setText(node_id)
    view.node_image_field.setCurrentText(image)
    view._on_add_node_clicked()


def _add_network(view: DesignerView, network_id: str, subnet: str) -> None:
    view.network_id_field.setText(network_id)
    view.network_subnet_field.setText(subnet)
    view._on_add_network_clicked()


def _connect(view: DesignerView, node_id: str, network_id: str, address: str) -> None:
    view.connection_node_combo.setCurrentText(node_id)
    view.connection_network_combo.setCurrentText(network_id)
    view.connection_address_field.setText(address)
    view._on_add_connection_clicked()


def _build_static_routing(view: DesignerView) -> None:
    view.name_field.setText("Static routing topology")
    _add_node(view, "client", "ubuntu:22.04")
    _add_node(view, "router", "frrouting/frr:latest")
    _add_node(view, "server", "nginx:latest")
    _add_network(view, "lan", "10.0.1.0/24")
    _add_network(view, "dmz", "10.0.2.0/24")
    _connect(view, "client", "lan", "10.0.1.10/24")
    _connect(view, "router", "lan", "10.0.1.1/24")
    _connect(view, "router", "dmz", "10.0.2.1/24")
    _connect(view, "server", "dmz", "10.0.2.10/24")


# ----- machines / networks / connections as panels + topology -----------------------------


def test_adding_a_machine_shows_a_card_with_id_image_and_role(view: DesignerView) -> None:
    _add_node(view, "client", "ubuntu:22.04")

    assert view.nodes == [{"id": "client", "image": "ubuntu:22.04", "preset": "custom"}]
    assert len(view._machine_rows) == 1
    assert view.machines_panel.count_label.text() == "1"
    assert view.node_id_field.text() == "node-1"  # next id suggested for the preset
    assert view.node_error_label.isHidden()


def test_machine_validation_errors_show_inline(view: DesignerView) -> None:
    _add_node(view, "Client")
    assert "Invalid machine ID" in view.node_error_label.text()

    _add_node(view, "client", "")
    assert view.node_error_label.text() == "A Docker image is required."

    _add_node(view, "client")
    _add_node(view, "client")
    assert "already exists" in view.node_error_label.text()
    assert len(view.nodes) == 1


def test_adding_a_network_shows_id_and_subnet_and_rejects_overlaps(view: DesignerView) -> None:
    _add_network(view, "lan", "10.0.1.0/24")

    assert view.networks == [{"id": "lan", "subnet": "10.0.1.0/24"}]
    assert view.networks_panel.count_label.text() == "1"

    _add_network(view, "dmz", "10.0.1.128/25")
    assert "overlaps network 'lan'" in view.network_error_label.text()
    _add_network(view, "dmz", "10.0.2.5/24")
    assert "not a valid IPv4 CIDR subnet" in view.network_error_label.text()
    assert len(view.networks) == 1


def test_connecting_updates_topology_interfaces_and_roles(view: DesignerView) -> None:
    _build_static_routing(view)

    topology = view.topology_canvas.view
    assert topology.connector_network("client", "router").id == "lan"
    assert topology.connector_network("router", "server").id == "dmz"
    assert topology.connector_network("client", "server") is None
    assert [link.address for link in topology.links_of("router")] == ["10.0.1.1/24", "10.0.2.1/24"]
    assert view.connections_table.rowCount() == 4
    assert view.connections_table.item(2, 2).text() == "10.0.2.1/24"
    assert view.status_pill.text_label.text() == "Draft valid \u00b7 3 machines \u00b7 2 networks"


def test_connection_validation_mirrors_the_server_rules(view: DesignerView) -> None:
    _connect(view, "", "", "10.0.1.10/24")
    assert "Add at least one machine and one network first." in view.connection_error_label.text()

    _add_node(view, "client")
    _add_network(view, "lan", "10.0.1.0/24")
    _connect(view, "client", "lan", "10.0.9.10/24")
    assert "not part of network 'lan'" in view.connection_error_label.text()
    _connect(view, "client", "lan", "10.0.1.0/24")
    assert "network or broadcast address" in view.connection_error_label.text()
    _connect(view, "client", "lan", "nope")
    assert "not a valid IPv4 address" in view.connection_error_label.text()

    _connect(view, "client", "lan", "10.0.1.10/24")
    assert view.connection_error_label.isHidden()
    _connect(view, "client", "lan", "10.0.1.11/24")
    assert "already has an interface on 'lan'" in view.connection_error_label.text()

    _add_node(view, "other")
    _connect(view, "other", "lan", "10.0.1.10/24")
    assert "already assigned" in view.connection_error_label.text()


def test_removing_a_machine_cascades_to_connections_and_topology(view: DesignerView) -> None:
    _build_static_routing(view)

    view._on_remove_node_clicked("router")

    assert [n["id"] for n in view.nodes] == ["client", "server"]
    assert all(i["node"] != "router" for i in view.interfaces)
    assert view.connections_table.rowCount() == 2
    assert view.topology_canvas.view.connector_network("client", "server") is None
    assert len(view._machine_rows) == 2


def test_removing_a_network_cascades_and_status_pill_reports_gaps(view: DesignerView) -> None:
    _build_static_routing(view)

    view._on_remove_network_clicked("dmz")

    assert [n["id"] for n in view.networks] == ["lan"]
    assert all(i["network"] != "dmz" for i in view.interfaces)
    assert "a connection for server" in view.status_pill.text_label.text()


def test_removing_a_connection_by_row(view: DesignerView) -> None:
    _build_static_routing(view)

    view._on_remove_connection_clicked(0)

    assert view.interfaces[0] == {"node": "router", "network": "lan", "address": "10.0.1.1/24"}
    assert view.connections_table.rowCount() == 3


# ----- validate / save (unchanged API behaviour) ---------------------------------------------


def test_validate_sends_the_same_definition_as_before(view: DesignerView) -> None:
    _build_static_routing(view)

    view.validate_button.click()

    assert view.api.validated == [
        {
            "name": "Static routing topology",
            "nodes": [
                {"id": "client", "image": "ubuntu:22.04"},
                {"id": "router", "image": "frrouting/frr:latest"},
                {"id": "server", "image": "nginx:latest"},
            ],
            "networks": [
                {"id": "lan", "subnet": "10.0.1.0/24"},
                {"id": "dmz", "subnet": "10.0.2.0/24"},
            ],
            "interfaces": [
                {"node": "client", "network": "lan", "address": "10.0.1.10/24"},
                {"node": "router", "network": "lan", "address": "10.0.1.1/24"},
                {"node": "router", "network": "dmz", "address": "10.0.2.1/24"},
                {"node": "server", "network": "dmz", "address": "10.0.2.10/24"},
            ],
        }
    ]
    assert "The lab is valid." in view.status_label.text()


def test_validate_shows_server_errors_verbatim(view: DesignerView) -> None:
    view.api.validate_result = ValidateLabResult(
        success=True,
        valid=False,
        errors=[FieldIssue(["name"], "String should have at least 1 character", "too_short")],
    )

    view.validate_button.click()

    assert view.status_label.text() == "name: String should have at least 1 character"
    assert view.status_label.property("banner") == "error"


def test_save_emits_saved_without_start_and_save_and_start_with(view: DesignerView) -> None:
    _build_static_routing(view)
    saved: list[tuple[str, bool]] = []
    view.saved.connect(lambda lab_id, start: saved.append((lab_id, start)))

    view.save_button.click()
    view.save_start_button.click()

    assert saved == [("lab-new", False), ("lab-new", True)]
    assert len(view.api.created) == 2


def test_failed_save_shows_errors_and_keeps_the_draft(view: DesignerView) -> None:
    _build_static_routing(view)
    view.api.create_result = CreateLabResult(
        success=False, errors=[FieldIssue(["body", "nodes"], "duplicate", "value_error")]
    )
    saved: list = []
    view.saved.connect(lambda *args: saved.append(args))

    view.save_button.click()

    assert saved == []
    assert view.status_label.text() == "body.nodes: duplicate"
    assert len(view.nodes) == 3
    assert view.save_button.isEnabled()


def test_reset_empties_the_draft(view: DesignerView) -> None:
    _build_static_routing(view)

    view.reset()

    assert view.nodes == [] and view.networks == [] and view.interfaces == []
    assert view.name_field.text() == ""
    assert view.topology_canvas.view.is_empty()
    assert "Draft needs a lab name, at least one machine" in view.status_pill.text_label.text()


def test_navigation_signals(view: DesignerView) -> None:
    fired: list[str] = []
    view.back_requested.connect(lambda: fired.append("back"))
    view.cancel_requested.connect(lambda: fired.append("cancel"))

    view.back_button.click()
    view.cancel_button.click()

    assert fired == ["back", "cancel"]


# ----- node catalogue, address help, editing (designer-node-catalog, designer-edit-existing-lab)


def test_presets_fill_image_and_suggest_ids(view: DesignerView) -> None:
    _select_preset(view, "router")

    assert view.node_image_field.isHidden()  # the preset decides the image
    assert view.node_id_field.text() == "router-1"
    assert "Forwards packets" in view.preset_description.text()
    view._on_add_node_clicked()
    assert view.node_id_field.text() == "router-2"  # ready for the next one

    node = view.nodes[0]
    assert node["id"] == "router-1"
    assert node["image"] == "alpine:3.21"
    assert node["resources"]["sysctls"] == {"net.ipv4.ip_forward": "1"}
    assert node["preset"] == "router"

    _select_preset(view, "ubuntu-desktop")
    view._on_add_node_clicked()
    desktop = view.nodes[1]
    assert desktop["id"] == "desktop-1"
    assert desktop["command"] is None
    assert desktop["resources"]["port_mappings"] == [
        {"host": 3000, "container": 3000},
        {"host": 3001, "container": 3001},
    ]
    assert desktop["environment"] == {"TITLE": "Practicum"}

    _select_preset(view, "custom")
    assert view.node_image_field.isHidden() is False
    assert view.node_image_field.currentText() == ""


def test_definition_carries_full_node_recipes_and_details(view: DesignerView) -> None:
    view.name_field.setText("Chain")
    view.description_field.setText("host - router - host")
    view.author_field.setText("Ada")
    view.version_field.setText("1.0")
    _select_preset(view, "alpine-host")
    view._on_add_node_clicked()
    _select_preset(view, "router")
    view._on_add_node_clicked()

    definition = view._build_definition()

    assert definition["description"] == "host - router - host"
    assert definition["author"] == "Ada" and definition["version"] == "1.0"
    assert [n["id"] for n in definition["nodes"]] == ["host-1", "router-1"]
    assert all("preset" not in n for n in definition["nodes"])
    assert definition["nodes"][0]["resources"] == {"cpu": 0.5, "memory_mb": 128}


def test_connect_form_suggests_the_next_free_address_and_shows_a_reference(
    view: DesignerView,
) -> None:
    _select_preset(view, "ubuntu-host")
    view._on_add_node_clicked()  # host-1
    _select_preset(view, "router")
    view._on_add_node_clicked()  # router-1
    _add_network(view, "lan", "10.0.1.0/24")

    view.connection_node_combo.setCurrentText("host-1")
    view.connection_network_combo.setCurrentText("lan")
    assert view.connection_address_field.text() == "10.0.1.10/24"
    assert "no machines yet" in view.address_reference_label.text()
    assert "Docker gateway 10.0.1.254" in view.address_reference_label.text()
    view._on_add_connection_clicked()

    view.connection_node_combo.setCurrentText("router-1")
    assert view.connection_address_field.text() == "10.0.1.1/24"  # routers get .1
    view._on_add_connection_clicked()

    view.connection_node_combo.setCurrentText("host-1")
    assert view.connection_address_field.text() == "10.0.1.11/24"
    assert "host-1 10.0.1.10" in view.address_reference_label.text()
    assert "router-1 10.0.1.1" in view.address_reference_label.text()
    assert "next free 10.0.1.11" in view.address_reference_label.text()


def test_load_lab_enters_edit_mode_and_saves_with_put(view: DesignerView) -> None:
    stored = {
        "id": "lab-7",
        "status": "stopped",
        "origin": "quick_start",
        "schema_version": "1.0",
        "name": "Ubuntu Quick Start",
        "description": "A sandbox",
        "manual": {"sections": [{"id": "s", "title": "T", "content_markdown": "c", "tasks": []}]},
        "nodes": [
            {
                "id": "host",
                "image": "ubuntu:22.04",
                "command": ["bash", "-c", "sleep infinity"],
                "environment": {},
                "resources": {"cpu": 1, "memory_mb": 1024},
            }
        ],
        "networks": [{"id": "lab-net", "subnet": "10.90.0.0/24"}],
        "interfaces": [{"node": "host", "network": "lab-net", "address": "10.90.0.10/24"}],
    }
    saved: list[tuple[str, bool]] = []
    view.saved.connect(lambda lab_id, start: saved.append((lab_id, start)))

    view.load_lab("lab-7", stored)

    assert view.editing_lab_id == "lab-7"
    assert view.title_label.text() == "Edit your lab"
    assert view.save_button.text() == "Save changes"
    assert view.name_field.text() == "Ubuntu Quick Start"
    assert view.description_field.text() == "A sandbox"
    assert [n["id"] for n in view.nodes] == ["host"]
    assert view.nodes[0]["preset"] == "ubuntu-host"
    assert view.connections_table.rowCount() == 1
    assert (
        view.status_pill.text_label.text()
        == "Draft valid \u00b7 1 machine \u00b7 1 network \u00b7 1 step"
    )
    assert [row.title_field.text() for row in view.manual_editor.rows] == ["T"]

    _select_preset(view, "router")
    view._on_add_node_clicked()
    view.api.create_result = CreateLabResult(success=True, lab_id="lab-7")
    view.save_button.click()

    assert view.api.created == []
    lab_id, definition = view.api.updated[0]
    assert lab_id == "lab-7"
    assert definition["manual"] == stored["manual"]  # loaded into the editor, saved as it was
    assert definition["schema_version"] == "1.0"
    assert "id" not in definition and "status" not in definition and "origin" not in definition
    assert [n["id"] for n in definition["nodes"]] == ["host", "router-1"]
    assert definition["nodes"][0]["command"] == ["bash", "-c", "sleep infinity"]
    assert saved == [("lab-7", False)]

    view.reset()
    assert view.editing_lab_id is None
    assert view.title_label.text() == "Build your Custom Lab"


def test_editing_a_windows_lab_keeps_os_and_shell(view: DesignerView) -> None:
    """windows-desktop-open-windows-shell: the declared shell survives a designer edit too
    (the designer passes through node fields it does not edit)."""
    stored = {
        "id": "lab-w",
        "status": "defined",
        "origin": "quick_start",
        "schema_version": "1.0",
        "name": "Windows Quick Start",
        "nodes": [
            {
                "id": "host",
                "image": "mcr.microsoft.com/windows/servercore:ltsc2022",
                "os": "windows",
                "shell": "powershell",
                "command": ["powershell.exe", "-NoLogo"],
                "environment": {"PRACTICUM_PACKAGES": "git"},
                "resources": {"cpu": 2, "memory_mb": 2048},
            }
        ],
        "networks": [{"id": "lab-net", "subnet": "10.90.0.0/24"}],
        "interfaces": [{"node": "host", "network": "lab-net", "address": "10.90.0.10/24"}],
    }

    view.load_lab("lab-w", stored)
    view.name_field.setText("Windows Quick Start (edited)")
    view.api.create_result = CreateLabResult(success=True, lab_id="lab-w")
    view.save_button.click()

    (lab_id, definition), = view.api.updated
    assert lab_id == "lab-w"
    node = definition["nodes"][0]
    assert node["os"] == "windows" and node["shell"] == "powershell"
    assert node["command"] == ["powershell.exe", "-NoLogo"]
    assert node["environment"] == {"PRACTICUM_PACKAGES": "git"}
    assert "preset" not in node


def test_machine_rows_carry_the_design_icon_for_their_preset(view: DesignerView) -> None:
    from PySide6.QtWidgets import QLabel

    _build_static_routing(view)

    icons_by_id = {}
    for row in view._machine_rows:
        label = next(
            lab for lab in row.findChildren(QLabel) if lab.property("icon") or lab.pixmap()
        )
        icons_by_id[row.findChildren(QLabel)[1].text()] = label.property("icon")
    assert icons_by_id["router"] == "forward"
    assert icons_by_id["client"] == "desktop" and icons_by_id["server"] == "desktop"


def test_preset_picker_shows_design_icons(view: DesignerView) -> None:
    combo = view.preset_combo
    titles = [combo.itemText(i) for i in range(combo.count())]
    assert titles == [
        "Ubuntu host",
        "Alpine host (tiny)",
        "Router",
        "Web server",
        "Ubuntu Desktop",
        "Custom image",
    ]
    assert all(not combo.itemIcon(i).isNull() for i in range(combo.count()))
    assert not any(t.startswith(("\u25a0", "\u25c6", "\u25cc")) for t in titles)  # no glyphs


# ----- lab instructions (designer-author-manual) ----------------------------------------------


def test_designer_saves_the_steps_as_the_labs_manual(view: DesignerView) -> None:
    _build_static_routing(view)
    assert view.manual is None  # no steps → no manual key
    assert view.instructions_panel.count_label.text() == "0"

    first = view.manual_editor.add_step()
    first.title_field.setText("Check connectivity")
    first.details_field.setPlainText("From client:\n\n```\nping 10.0.2.10\n```")
    second = view.manual_editor.add_step()
    second.title_field.setText("Add the route")
    view.manual_editor.add_step()  # untitled: ignored

    assert view.instructions_panel.count_label.text() == "2"
    assert view.status_pill.text_label.text().endswith("\u00b7 2 networks \u00b7 2 steps")
    view.api.create_result = CreateLabResult(success=True, lab_id="lab-9")
    view.save_button.click()

    definition = view.api.created[0]
    assert definition["manual"] == {
        "sections": [
            {
                "id": "step-1",
                "title": "Check connectivity",
                "content_markdown": "From client:\n\n```\nping 10.0.2.10\n```",
                "tasks": [{"id": "done", "text": "Done: Check connectivity"}],
            },
            {
                "id": "step-2",
                "title": "Add the route",
                "content_markdown": "Add the route",
                "tasks": [{"id": "done", "text": "Done: Add the route"}],
            },
        ]
    }

    view.reset()
    assert view.manual_editor.rows == [] and view.manual is None


def test_editing_keeps_hand_authored_tasks_and_regenerates_only_generated_ones(
    view: DesignerView,
) -> None:
    stored = {
        "id": "lab-8",
        "status": "defined",
        "schema_version": "1.0",
        "name": "Static Routing Fundamentals",
        "manual": {
            "sections": [
                {
                    "id": "overview",
                    "title": "Overview",
                    "content_markdown": "## Goal\n\nReach host-b.",
                    "tasks": [
                        {"id": "verify-topology", "text": "Review the topology."},
                        {"id": "note-addresses", "text": "Note both addresses."},
                    ],
                },
                {
                    "id": "step-2",
                    "title": "Ping",
                    "content_markdown": "ping 10.0.2.10",
                    "tasks": [{"id": "done", "text": "Done: Ping"}],
                },
                {"id": "reading", "title": "Reading", "content_markdown": "RFC 1812", "tasks": []},
            ]
        },
        "nodes": [{"id": "host", "image": "alpine:3.21"}],
        "networks": [{"id": "lan", "subnet": "10.0.1.0/24"}],
        "interfaces": [{"node": "host", "network": "lan", "address": "10.0.1.10/24"}],
    }
    view.load_lab("lab-8", stored)

    rows = view.manual_editor.rows
    assert rows[0].tasks == stored["manual"]["sections"][0]["tasks"]  # custom tasks kept
    assert rows[1].tasks is None  # the generated task is regenerated from the title
    assert rows[2].tasks == []  # "no tasks" is a choice, kept as such
    assert [r.title_field.text() for r in rows] == ["Overview", "Ping", "Reading"]

    rows[1].title_field.setText("Ping host-b")
    view.api.create_result = CreateLabResult(success=True, lab_id="lab-8")
    view.save_button.click()

    (_lab_id, definition), = view.api.updated
    sections = definition["manual"]["sections"]
    assert sections[0]["id"] == "overview"
    assert sections[0]["tasks"] == stored["manual"]["sections"][0]["tasks"]
    assert sections[1]["id"] == "step-2"
    assert sections[1]["tasks"] == [{"id": "done", "text": "Done: Ping host-b"}]
    assert sections[2] == stored["manual"]["sections"][2]

    for row in list(view.manual_editor.rows):
        view.manual_editor.remove_row(row)
    assert view.manual is None  # all steps removed → the saved lab has no manual


def test_manual_preview_renders_steps_like_the_flyout(view: DesignerView) -> None:
    editor = view.manual_editor
    editor.add_step()
    editor.rows[0].title_field.setText("Install")
    editor.rows[0].details_field.setPlainText("Run:\n\n```\napt-get install -y git\n```")

    editor.preview_button.click()

    assert editor.previewing is True
    assert editor.preview_button.text() == "Edit"
    assert editor.preview.empty_label.isHidden()
    labels = [w.text() for w in editor.preview.findChildren(QLabel)]
    assert "Install" in labels
    assert any("apt-get install -y git" in t for t in labels)
    assert "Done: Install" in labels
    assert [m.state for m in editor.preview.findChildren(StepMarker)] == ["active"]

    editor.preview_button.click()
    assert editor.previewing is False and editor.preview_button.text() == "Preview"
    editor.clear()
    editor.preview_button.click()
    assert editor.preview.empty_label.isHidden() is False


def test_instructions_panel_collapses_to_its_header_and_keeps_the_steps(
    view: DesignerView,
) -> None:
    view.manual_editor.add_step(QuickStartStep("Keep me"))
    view.show()

    view.instructions_toggle.click()  # Hide
    assert view.instructions_panel.body.isHidden()
    assert view.instructions_toggle.text() == "Show"
    assert view.instructions_panel.maximumHeight() < 80
    assert view.instructions_panel.count_label.text() == "1"  # still visible in the header

    view.instructions_toggle.click()  # Show
    assert view.instructions_panel.body.isHidden() is False
    assert view.instructions_toggle.text() == "Hide"
    assert view.manual_editor.steps()[0].title == "Keep me"
    view.close()


def test_second_desktop_gets_free_host_ports_instead_of_clashing(view: DesignerView) -> None:
    """Two Ubuntu Desktop machines: the second one is published on the next free ports, so
    the lab validates and starts without a port-conflict fix in the gate."""
    _select_preset(view, "ubuntu-desktop")
    view._on_add_node_clicked()
    _select_preset(view, "ubuntu-desktop")
    view._on_add_node_clicked()
    _select_preset(view, "web-server")
    view._on_add_node_clicked()

    ports = {
        n["id"]: [m["host"] for m in n["resources"].get("port_mappings", [])] for n in view.nodes
    }
    assert ports["desktop-1"] == [3000, 3001]
    assert ports["desktop-2"] == [3002, 3003]
    assert ports["web-1"] == [8080]  # untouched: not taken

    _select_preset(view, "web-server")
    view._on_add_node_clicked()
    assert [m["host"] for m in view.nodes[-1]["resources"]["port_mappings"]] == [8081]
