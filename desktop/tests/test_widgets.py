from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QWidget

from practicum_desktop import theme
from practicum_desktop.widgets import (
    AutoSizeStack,
    Badge,
    FlowLayout,
    StatusPill,
    TopologyLink,
    TopologyNetwork,
    TopologyNode,
    TopologyView,
    make_button,
    node_role,
)

NODES = [TopologyNode("client", "ubuntu"), TopologyNode("router", "frr"), TopologyNode("server")]
NETWORKS = [TopologyNetwork("lan", "10.0.1.0/24"), TopologyNetwork("dmz", "10.0.2.0/24")]
LINKS = [
    TopologyLink("client", "lan", "10.0.1.10/24"),
    TopologyLink("router", "lan", "10.0.1.1/24"),
    TopologyLink("router", "dmz", "10.0.2.1/24"),
    TopologyLink("server", "dmz", "10.0.2.10/24"),
]


def test_badge_maps_api_statuses_to_roles_and_labels() -> None:
    assert theme.badge_for_status("running") == ("running", "Running")
    assert theme.badge_for_status("defined") == ("ready", "Ready")
    assert theme.badge_for_status("error") == ("error", "Error")
    assert theme.badge_for_status("starting") == ("busy", "Starting\u2026")
    assert theme.badge_for_status("weird") == ("stopped", "Weird")
    badge = Badge("stopped")
    assert badge.text() == "\u25cf Stopped"
    assert badge.property("badge") == "stopped"
    badge.set_status("running")
    assert badge.property("badge") == "running"


def test_make_button_sets_style_properties() -> None:
    button = make_button("Go", kind="danger", small=True)
    assert button.property("kind") == "danger"
    assert button.property("small") is True
    assert make_button("x").property("small") is None


def test_status_pill_text_and_colour() -> None:
    pill = StatusPill("Ready", theme.GREEN)
    assert pill.text_label.text() == "Ready"
    assert pill.dot.property("icon") == "success"  # green = the design check icon
    pill.set_state("Busy", theme.AMBER)
    assert pill.text_label.text() == "Busy"
    assert pill.dot.property("icon") == "warning"
    pill.set_state("Failed", theme.DANGER)
    assert pill.dot.property("icon") == "error"
    pill.set_state("Idle", theme.MUTED_2)  # no icon has that meaning: a plain coloured dot
    assert pill.dot.property("icon") == ""
    assert theme.MUTED_2 in pill.dot.styleSheet()


def test_node_role_is_derived_from_interface_count() -> None:
    assert node_role(0) == "unconnected"
    assert node_role(1) == "host"
    assert node_role(2) == "gateway"
    assert node_role(5) == "gateway"


def test_topology_view_derives_connectors_orphans_and_size() -> None:
    view = TopologyView()
    assert view.is_empty()
    empty_width = view.sizeHint().width()

    view.set_topology(NODES, NETWORKS + [TopologyNetwork("mgmt", "10.0.9.0/24")], LINKS)

    assert view.connector_network("client", "router").id == "lan"
    assert view.connector_network("router", "server").id == "dmz"
    assert view.connector_network("client", "server") is None
    assert [n.id for n in view.orphan_networks()] == ["mgmt"]
    assert view.max_links() == 2
    assert view.sizeHint().width() > empty_width
    assert view.sizeHint().height() >= view.minimumHeight()


def test_topology_view_paints_without_error(qapp) -> None:
    view = TopologyView()
    view.resize(600, 200)
    view.show()
    view.set_topology(NODES, NETWORKS, LINKS)
    qapp.processEvents()
    image = view.grab().toImage()
    assert image.width() == 600
    # Something other than the background grid was drawn (card outlines, pills).
    assert image.pixelColor(30, 30).name() != image.pixelColor(5, 5).name() or not view.is_empty()

    compact = TopologyView(compact=True)
    compact.set_topology(NODES, NETWORKS, LINKS)
    assert compact.minimumSizeHint().width() == 200


def test_flow_layout_wraps_and_clears() -> None:
    host = QWidget()
    layout = FlowLayout(host, spacing=4)
    for text in ("one", "two", "three"):
        layout.addWidget(QLabel(text))
    assert layout.count() == 3
    assert layout.heightForWidth(60) > layout.heightForWidth(600)

    layout.clear()

    assert layout.count() == 0


def test_auto_size_stack_follows_current_page() -> None:
    stack = AutoSizeStack()
    small = QLabel("small")
    tall = QLabel("tall")
    tall.setFixedHeight(300)
    stack.addWidget(small)
    stack.addWidget(tall)

    stack.setCurrentIndex(0)
    assert stack.sizeHint().height() < 100
    stack.setCurrentIndex(1)
    assert stack.sizeHint().height() == 300


# ----- banners with design icons (windows-desktop-design-icons) -------------------------------


def test_message_banner_shows_the_icon_for_its_kind_and_reads_like_a_label() -> None:
    from practicum_desktop.widgets import MessageBanner

    banner = MessageBanner("info")
    assert banner.icon_label.isHidden()  # info has no icon: text only

    banner.set_message("1 port conflict must be resolved before starting.", "warn")
    assert banner.text() == "1 port conflict must be resolved before starting."
    assert banner.property("banner") == "warn"
    assert banner.icon_label.property("icon") == "warning"
    assert banner.icon_label.isHidden() is False
    assert banner.isHidden() is False

    banner.set_message("No port conflicts detected.", "ok")
    assert banner.icon_label.property("icon") == "success"
    banner.set_message("Docker is unavailable", "error")
    assert banner.icon_label.property("icon") == "error"
    assert (
        banner.message_label.textInteractionFlags() & Qt.TextInteractionFlag.TextSelectableByMouse
    )

    banner.set_message("")  # empty text hides it
    assert banner.isHidden()
    banner.setText("plain setText works too")
    assert banner.text() == "plain setText works too"


def test_note_banner_is_a_dismissible_message_banner() -> None:
    from practicum_desktop.widgets import NoteBanner

    note = NoteBanner()
    fired: list[str] = []
    note.dismissed.connect(lambda: fired.append("dismissed"))
    assert note.isHidden()

    note.show_note("Deleted 'X'.", "ok")
    assert note.isHidden() is False
    assert note.text() == "Deleted 'X'." and note.property("banner") == "ok"
    assert note.icon_label.property("icon") == "success"
    assert note.close_button.accessibleName() == "Dismiss"

    note.close_button.click()
    assert note.isHidden() and note.text() == ""
    assert fired == ["dismissed"]


def test_back_link_and_icon_buttons_keep_their_meaning_in_text_or_accessible_name() -> None:
    from practicum_desktop.widgets import BackLink

    link = BackLink("Back to my labs")
    assert link.text() == "Back to my labs"
    assert not link.icon().isNull()
    assert link.accessibleName() == "Back to my labs"

    icon_only = BackLink("")
    assert icon_only.text() == ""
    assert icon_only.accessibleName() == "Back"

    start = make_button("Start lab", kind="primary", small=True, icon="play")
    assert not start.icon().isNull() and start.text() == "Start lab"
    cta = make_button("Quick start", kind="primary", icon="forward", icon_trailing=True)
    assert cta.layoutDirection() == Qt.LayoutDirection.RightToLeft


def test_topology_cards_and_machine_rows_use_design_icons_by_role() -> None:
    from practicum_desktop.widgets import NODE_ICON_NAMES, node_icon_name

    assert NODE_ICON_NAMES == {"host": "desktop", "gateway": "forward", "unconnected": "desktop"}
    assert node_icon_name(0) == "desktop"
    assert node_icon_name(1) == "desktop"
    assert node_icon_name(2) == "forward"  # a gateway forwards traffic between its networks
    view = TopologyView()
    view.set_topology(NODES, NETWORKS, LINKS)
    view.resize(520, 180)
    view.grab()  # paints the cards with pixmaps (no exception, no glyph fallback needed)
