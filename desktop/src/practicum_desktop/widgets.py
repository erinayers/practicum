"""Small reusable building blocks shared by every screen (the mockup's .panel, .chip,
.lab-status, .stat-tile, .back-link, .bottom-bar ... plus the schematic topology view).

Everything here is presentation only. Widgets take plain values (strings, dataclasses) and
emit Qt signals; they never talk to the API.
"""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QRect, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPainter, QPen
from PySide6.QtWidgets import (
    QAbstractButton,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLayout,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from practicum_desktop import icons, theme

COPYABLE_TEXT_FLAGS = (
    Qt.TextInteractionFlag.TextSelectableByMouse | Qt.TextInteractionFlag.TextSelectableByKeyboard
)

PAYLOAD_PROPERTY = "practicumPayload"


def bind(button: QAbstractButton, slot, payload: object = None) -> None:
    """Connects `button.clicked` to a *bound method* `slot`, handing it `payload` through
    `payload_of(self.sender())`.

    Never connect a lambda that captures `self` to a child widget's signal: it closes a
    Python reference cycle (owner → child → lambda → owner) that the garbage collector
    tears down in an order Qt 6.12 does not survive (heap corruption on teardown, seen
    when rebuilding lists of rows/cards). PySide keeps bound-method connections weak, so
    this helper has no such cycle.
    """
    button.setProperty(PAYLOAD_PROPERTY, payload)
    button.clicked.connect(slot)


def payload_of(sender) -> object:
    """The payload `bind()` attached to the widget that emitted the current signal."""
    return sender.property(PAYLOAD_PROPERTY) if sender is not None else None


# ----- labels and buttons -------------------------------------------------------------------


def copyable_label(text: str = "", role: str | None = None) -> QLabel:
    """A word-wrapping label whose text can be selected and copied (errors, commands)."""
    label = QLabel(text)
    label.setWordWrap(True)
    label.setTextInteractionFlags(COPYABLE_TEXT_FLAGS)
    if role:
        label.setProperty("role", role)
    return label


def role_label(text: str, role: str, wrap: bool = False) -> QLabel:
    label = QLabel(text)
    label.setProperty("role", role)
    label.setWordWrap(wrap)
    return label


# Icon tint per button kind: white on the dark/red buttons, ink elsewhere.
_ICON_COLOUR_BY_KIND = {
    "primary": "white",
    "danger": "white",
    "ghost": theme.MUTED,
    "link": theme.MUTED,
}


def make_button(
    text: str,
    kind: str = "secondary",
    small: bool = False,
    icon: str | None = None,
    icon_trailing: bool = False,
) -> QPushButton:
    """A QPushButton styled by `kind` (primary | secondary | danger | ghost | link | dashed),
    optionally with a design icon (`icons.ICONS` name) before - or, with `icon_trailing`,
    after - its text."""
    button = QPushButton(text)
    button.setProperty("kind", kind)
    if small:
        button.setProperty("small", True)
    button.setCursor(Qt.CursorShape.PointingHandCursor)
    if icon is not None:
        icons.set_button_icon(
            button,
            icon,
            size=13 if small else 14,
            colour=_ICON_COLOUR_BY_KIND.get(kind, theme.INK),
            trailing=icon_trailing,
        )
    return button


def set_role(widget: QWidget, name: str, value: object) -> None:
    """Changes a style property at runtime and re-polishes the widget."""
    widget.setProperty(name, value)
    theme.restyle(widget)


class Badge(QLabel):
    """Status pill: `set_status("running")` picks the role + label from the API status."""

    def __init__(self, status: str = "defined", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.set_status(status)

    def set_status(self, status: str) -> None:
        role, label = theme.badge_for_status(status)
        self.setText(f"\u25cf {label}")
        set_role(self, "badge", role)


class Chip(QLabel):
    def __init__(self, text: str, muted: bool = False, parent: QWidget | None = None) -> None:
        super().__init__(text, parent)
        self.setProperty("chip", "muted" if muted else "true")


class ToggleChip(QPushButton):
    """A checkable chip (the quick start's popular-software picker)."""

    def __init__(self, text: str, tooltip: str = "", parent: QWidget | None = None) -> None:
        super().__init__(text, parent)
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip(tooltip)
        # Same weight checked and unchecked: a bolder checked label would outgrow the chip.
        self.setStyleSheet(
            f"QPushButton {{ background: #f3f4f6; color: {theme.MUTED}; border: 1px solid {theme.LINE};"
            " border-radius: 11px; padding: 3px 10px; font-size: 11.5px; font-weight: 600; }"
            f"QPushButton:hover {{ border-color: {theme.INK}; color: {theme.INK}; }}"
            f"QPushButton:checked {{ background: {theme.ACCENT_SOFT}; color: #3730a3;"
            " border-color: #c7d2fe; }"
        )


class RemovableChip(QFrame):
    """A chip with an inline × (the quick-start package list)."""

    removed = Signal(str)

    def __init__(self, text: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.value = text
        self.setObjectName("removableChip")
        self.setStyleSheet(
            f"QFrame#removableChip {{ background: {theme.ACCENT_SOFT}; border-radius: 11px; }}"
            "QLabel { background: transparent; color: #3730a3; font-size: 11.5px; }"
            "QPushButton { background: transparent; border: none; color: #3730a3;"
            " font-weight: 700; padding: 0 2px; }"
        )
        row = QHBoxLayout(self)
        row.setContentsMargins(10, 3, 6, 3)
        row.setSpacing(4)
        row.addWidget(QLabel(text))
        remove = QPushButton("\u00d7")
        remove.setCursor(Qt.CursorShape.PointingHandCursor)
        remove.setToolTip(f"Remove {text}")
        remove.clicked.connect(self._on_remove_clicked)
        row.addWidget(remove)

    def _on_remove_clicked(self) -> None:
        self.removed.emit(self.value)


BANNER_ICON_SIZE = 16


class MessageBanner(QFrame):
    """A message bar (ok / info / warn / error) with the matching design icon in front of a
    word-wrapping, copyable text: the shared shape of every status banner in the app
    (gate checks, running-view action feedback, designer validation, welcome blockers).

    Styled through the `banner` property (theme `[banner="warn"]` rules), the same role the
    older plain-label banners used, so `text()` / `property("banner")` read the same way.
    Meaning never rests on the icon or colour alone: the text always says it."""

    def __init__(self, kind: str = "info", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("messageBanner")
        row = QHBoxLayout(self)
        row.setContentsMargins(12, 8, 12, 8)
        row.setSpacing(8)
        self.icon_label = icons.icon_label("success", BANNER_ICON_SIZE)
        self.icon_label.hide()
        row.addWidget(self.icon_label, 0, Qt.AlignmentFlag.AlignTop)
        self.message_label = QLabel("")
        self.message_label.setWordWrap(True)
        self.message_label.setTextInteractionFlags(COPYABLE_TEXT_FLAGS)
        self.message_label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        row.addWidget(self.message_label, 1)
        self.row = row
        self.kind = kind
        self.set_kind(kind)

    def set_kind(self, kind: str) -> None:
        self.kind = kind
        set_role(self, "banner", kind)
        icon_name = icons.BANNER_ICONS.get(kind)
        icons.set_label_icon(self.icon_label, icon_name, BANNER_ICON_SIZE)
        self.icon_label.setVisible(icon_name is not None and icons.icon_available(icon_name))

    def set_message(self, text: str, kind: str | None = None) -> None:
        """Sets the text (and kind) and shows the banner; an empty text hides it."""
        if kind is not None and kind != self.kind:
            self.set_kind(kind)
        self.message_label.setText(text)
        self.setVisible(bool(text))

    # QLabel-compatible accessors, so screens and tests read banners the same way.
    def setText(self, text: str) -> None:  # Qt naming
        self.message_label.setText(text)

    def text(self) -> str:
        return self.message_label.text()


class NoteBanner(MessageBanner):
    """A dismissible MessageBanner for transient notes such as "Deleted 'X'. Its containers
    were removed …". `message_label` is the text; `show_note("")` or the × hides it."""

    dismissed = Signal()

    def __init__(self, parent: QWidget | None = None, fixed_width: int | None = None) -> None:
        super().__init__("info", parent)
        self.setObjectName("noteBanner")
        if fixed_width is not None:
            self.setFixedWidth(fixed_width)
        self.row.setContentsMargins(12, 8, 8, 8)
        self.close_button = QPushButton("\u00d7")
        self.close_button.setObjectName("bannerDismiss")
        self.close_button.setToolTip("Dismiss")
        self.close_button.setAccessibleName("Dismiss")
        self.close_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.close_button.setFixedSize(22, 22)
        self.close_button.clicked.connect(self._on_dismiss)
        self.row.addWidget(self.close_button, 0, Qt.AlignmentFlag.AlignTop)
        self.hide()
        self.message_label.hide()

    def show_note(self, text: str, kind: str = "info") -> None:
        if not text:
            self.clear()
            return
        self.set_kind(kind)
        self.message_label.setText(text)
        self.message_label.show()
        self.show()

    def clear(self) -> None:
        self.message_label.setText("")
        self.message_label.hide()
        self.hide()

    def _on_dismiss(self) -> None:
        self.clear()
        self.dismissed.emit()


class StatTile(QFrame):
    """.stat-tile: a small bordered box with an uppercase label and a bold value."""

    def __init__(self, label: str, value: str = "\u2014", parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setProperty("panel", "true")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(2)
        caption = QLabel(label.upper())
        caption.setProperty("role", "hint")
        layout.addWidget(caption)
        self.value_label = QLabel(value)
        self.value_label.setProperty("role", "title")
        layout.addWidget(self.value_label)

    def set_value(self, value: str) -> None:
        self.value_label.setText(value)


class BackLink(QPushButton):
    """'(back icon) Back to my labs' ghost link. Without text it is icon-only and carries
    its meaning in the accessible name and tooltip."""

    def __init__(self, text: str, parent: QWidget | None = None) -> None:
        super().__init__(text, parent)
        self.setProperty("kind", "ghost")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Fixed)
        self.setStyleSheet("padding: 4px 6px; font-weight: 400; font-size: 13px;")
        if not icons.icon_available("back"):
            self.setText(f"\u2190 {text}".strip())
        icons.set_button_icon(self, "back", size=16, colour=theme.INK)
        self.setAccessibleName(text or "Back")


class StatusPill(QWidget):
    """'(check) Draft valid · 3 machines' — the design icon for the state (green = success,
    amber = warning, red = error; a plain dot for any other colour) followed by muted text."""

    ICON_SIZE = 14

    def __init__(self, text: str = "", colour: str = theme.GREEN, parent=None) -> None:
        super().__init__(parent)
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(6)
        self.dot = QLabel()
        self.dot.setFixedSize(self.ICON_SIZE, self.ICON_SIZE)
        self.dot.setAlignment(Qt.AlignmentFlag.AlignCenter)
        row.addWidget(self.dot)
        self.text_label = QLabel(text)
        self.text_label.setProperty("role", "muted")
        row.addWidget(self.text_label)
        row.addStretch(1)
        self.colour = colour
        self.set_state(text, colour)

    def set_state(self, text: str, colour: str = theme.GREEN) -> None:
        self.text_label.setText(text)
        self.colour = colour
        icon_name = icons.COLOUR_ICONS.get(colour)
        if icon_name is not None and icons.icon_available(icon_name):
            self.dot.setStyleSheet("background: transparent;")
            icons.set_label_icon(self.dot, icon_name, self.ICON_SIZE)
            return
        icons.set_label_icon(self.dot, None, self.ICON_SIZE)
        radius = self.ICON_SIZE // 2
        self.dot.setStyleSheet(
            f"background: {colour}; border-radius: {radius}px; margin: 3px;"
        )


# ----- panels -------------------------------------------------------------------------------


class Panel(QFrame):
    """.panel: bordered card with an optional header row (title + count badge + actions)."""

    def __init__(
        self,
        title: str | None = None,
        parent: QWidget | None = None,
        padding: int = 14,
    ) -> None:
        super().__init__(parent)
        self.setProperty("panel", "true")
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(0)
        self.head: QFrame | None = None
        self.title_label: QLabel | None = None
        self.count_label: QLabel | None = None
        self.head_actions: QHBoxLayout | None = None
        if title is not None:
            self.head = QFrame()
            self.head.setObjectName("panelHead")
            head_row = QHBoxLayout(self.head)
            head_row.setContentsMargins(14, 10, 14, 10)
            head_row.setSpacing(6)
            self.title_label = QLabel(title)
            self.title_label.setProperty("role", "h3")
            head_row.addWidget(self.title_label)
            self.count_label = QLabel()
            self.count_label.setProperty("chip", "count")
            self.count_label.hide()
            head_row.addWidget(self.count_label)
            head_row.addStretch(1)
            self.head_actions = QHBoxLayout()
            self.head_actions.setSpacing(6)
            head_row.addLayout(self.head_actions)
            self._layout.addWidget(self.head)
        self.body = QWidget()
        self.body.setStyleSheet("background: transparent;")
        self.body_layout = QVBoxLayout(self.body)
        self.body_layout.setContentsMargins(padding, padding, padding, padding)
        self.body_layout.setSpacing(8)
        self._layout.addWidget(self.body, 1)

    def set_count(self, count: int | None) -> None:
        if self.count_label is None:
            return
        self.count_label.setVisible(count is not None)
        self.count_label.setText(str(count if count is not None else ""))

    def add_head_action(self, widget: QWidget) -> None:
        if self.head_actions is not None:
            self.head_actions.addWidget(widget)


_FRAME_COUNTER = 0


def discard(widget: QWidget | None) -> None:
    """Removes a widget from view right away and schedules its deletion. `deleteLater()`
    alone leaves the widget painted until the event loop runs, which shows up as ghost rows
    when a list is rebuilt."""
    if widget is None:
        return
    widget.hide()
    widget.setParent(None)
    widget.deleteLater()


def style_frame(frame: QFrame, css: str) -> None:
    """Applies `css` to this frame only. A bare `QFrame {}` selector would also hit every
    QLabel inside it (QLabel is a QFrame), so the rule is keyed on a unique object name."""
    global _FRAME_COUNTER
    if not frame.objectName():
        _FRAME_COUNTER += 1
        frame.setObjectName(f"styledFrame{_FRAME_COUNTER}")
    frame.setStyleSheet(f"QFrame#{frame.objectName()} {{ {css} }}")


def edge_frame(edge: str, colour: str = theme.LINE, style: str = "solid") -> QFrame:
    """A container with a single border line on `edge` ('top' | 'bottom' | 'left')."""
    frame = QFrame()
    style_frame(frame, f"border-{edge}: 1px {style} {colour};")
    return frame


class AutoSizeStack(QStackedWidget):
    """A QStackedWidget that is only as tall as its *current* page (the default takes the
    tallest page, which leaves big gaps under a small status line)."""

    def sizeHint(self) -> QSize:
        current = self.currentWidget()
        return current.sizeHint() if current is not None else super().sizeHint()

    def minimumSizeHint(self) -> QSize:
        current = self.currentWidget()
        return current.minimumSizeHint() if current is not None else super().minimumSizeHint()

    def setCurrentIndex(self, index: int) -> None:
        super().setCurrentIndex(index)
        self.updateGeometry()


def separator() -> QFrame:
    line = QFrame()
    line.setProperty("separator", True)
    return line


def page_container(
    margins: tuple[int, int, int, int] = (44, 24, 44, 0),
) -> tuple[QWidget, QVBoxLayout]:
    """The mockup's .page: a screen-wide column with generous side padding."""
    page = QWidget()
    page.setObjectName("screen")
    layout = QVBoxLayout(page)
    layout.setContentsMargins(*margins)
    layout.setSpacing(10)
    return page, layout


def bottom_bar() -> tuple[QFrame, QHBoxLayout]:
    bar = QFrame()
    bar.setObjectName("bottomBar")
    row = QHBoxLayout(bar)
    row.setContentsMargins(44, 12, 44, 12)
    row.setSpacing(10)
    return bar, row


def powered_by_docker() -> QLabel:
    label = QLabel("\u2297 Powered by Docker")
    label.setProperty("role", "hint")
    label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    label.setContentsMargins(0, 10, 0, 16)
    return label


class FlowLayout(QLayout):
    """Wraps child widgets onto new rows as needed (chips)."""

    def __init__(self, parent: QWidget | None = None, spacing: int = 6) -> None:
        super().__init__(parent)
        self._items = []
        self._spacing = spacing
        self.setContentsMargins(0, 0, 0, 0)

    def addItem(self, item) -> None:
        self._items.append(item)

    def count(self) -> int:
        return len(self._items)

    def itemAt(self, index: int):
        return self._items[index] if 0 <= index < len(self._items) else None

    def takeAt(self, index: int):
        return self._items.pop(index) if 0 <= index < len(self._items) else None

    def expandingDirections(self):
        return Qt.Orientation(0)

    def hasHeightForWidth(self) -> bool:
        return True

    def heightForWidth(self, width: int) -> int:
        return self._arrange(QRect(0, 0, width, 0), dry_run=True)

    def setGeometry(self, rect: QRect) -> None:
        super().setGeometry(rect)
        self._arrange(rect, dry_run=False)

    def sizeHint(self) -> QSize:
        return self.minimumSize()

    def minimumSize(self) -> QSize:
        size = QSize()
        for item in self._items:
            size = size.expandedTo(item.minimumSize())
        return size + QSize(0, 0)

    def _arrange(self, rect: QRect, dry_run: bool) -> int:
        x, y, row_height = rect.x(), rect.y(), 0
        for item in self._items:
            hint = item.sizeHint()
            if x + hint.width() > rect.right() + 1 and row_height > 0:
                x = rect.x()
                y += row_height + self._spacing
                row_height = 0
            if not dry_run:
                item.setGeometry(QRect(x, y, hint.width(), hint.height()))
            x += hint.width() + self._spacing
            row_height = max(row_height, hint.height())
        return y + row_height - rect.y()

    def clear(self) -> None:
        while self._items:
            item = self._items.pop()
            discard(item.widget())


class FlowHost(QWidget):
    """A widget whose FlowLayout children always get the height they need: QBoxLayout does
    not reliably honour height-for-width for nested layouts, so the host pins its minimum
    height to the flow's height at its current width."""

    def __init__(self, parent: QWidget | None = None, spacing: int = 6) -> None:
        super().__init__(parent)
        self.flow = FlowLayout(self, spacing=spacing)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self.refit()

    def refit(self) -> None:
        width = self.width() if self.width() > 0 else 480
        self.setMinimumHeight(self.flow.heightForWidth(width))


# ----- schematic topology -------------------------------------------------------------------


@dataclass(frozen=True)
class TopologyNode:
    id: str
    image: str = ""


@dataclass(frozen=True)
class TopologyNetwork:
    id: str
    subnet: str = ""


@dataclass(frozen=True)
class TopologyLink:
    node: str
    network: str
    address: str = ""


NODE_HOST_GLYPH = "\u25a0"  # ■ a machine (text fallback)
NODE_GATEWAY_GLYPH = "\u25c6"  # ◆ a machine that joins two or more networks (text fallback)
# Design icons per derived role: a host is a machine (desktop), a gateway forwards traffic
# between its networks (forward arrow).
NODE_ICON_NAMES = {"host": "desktop", "gateway": "forward", "unconnected": "desktop"}
NODE_CARD_ICON_SIZE = 18
CARD_W, CARD_H = 108, 66
CONNECTOR_W = 130
COMPACT_CONNECTOR_W = 70  # illustrations (Create screen) have less room
ADDRESS_PILL_H = 16
MARGIN = 20
GRID = 24


def node_role(link_count: int) -> str:
    """Derived only from the number of interfaces (decision D-27 / Tigre 11 C12)."""
    if link_count >= 2:
        return "gateway"
    if link_count == 1:
        return "host"
    return "unconnected"


def node_icon_name(link_count: int) -> str:
    """The design icon for a node's derived role (see NODE_ICON_NAMES)."""
    return NODE_ICON_NAMES[node_role(link_count)]


class TopologyView(QWidget):
    """Read-only schematic of a lab (designer-visual-topology-builder, pre-start gate).

    Machines are drawn as cards in spec order; adjacent machines that share a network get a
    connector carrying that network's pill (the mockup's `client —lan— router —dmz— server`).
    Every interface is also listed under its machine as `network · address`, so a machine on
    three networks shows all three even though only one can be a connector. Networks without
    machines are listed at the far right. No drag-and-drop: positions are derived from the
    spec order only (that is the paid roadmap's territory).
    """

    EMPTY_TEXT = "Add machines and connect them to networks to see the topology here."

    def __init__(self, parent: QWidget | None = None, compact: bool = False) -> None:
        super().__init__(parent)
        self._nodes: list[TopologyNode] = []
        self._networks: list[TopologyNetwork] = []
        self._links: list[TopologyLink] = []
        # compact: an illustration that shrinks to whatever space it is given and centres
        # its drawing (the Create screen's mini topology) instead of asking for full size.
        self._compact = compact
        self._connector_w = COMPACT_CONNECTOR_W if compact else CONNECTOR_W
        self.setMinimumHeight(CARD_H + 2 * MARGIN + 2 * ADDRESS_PILL_H)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)

    # -- data ---------------------------------------------------------------------------

    def set_topology(
        self,
        nodes: list[TopologyNode],
        networks: list[TopologyNetwork],
        links: list[TopologyLink],
    ) -> None:
        self._nodes = list(nodes)
        self._networks = list(networks)
        self._links = list(links)
        self.updateGeometry()
        self.update()

    def links_of(self, node_id: str) -> list[TopologyLink]:
        return [link for link in self._links if link.node == node_id]

    def connector_network(self, left: str, right: str) -> TopologyNetwork | None:
        """The first network (in spec order) both machines are attached to, if any."""
        left_nets = {link.network for link in self.links_of(left)}
        right_nets = {link.network for link in self.links_of(right)}
        for network in self._networks:
            if network.id in left_nets and network.id in right_nets:
                return network
        return None

    def orphan_networks(self) -> list[TopologyNetwork]:
        used = {link.network for link in self._links}
        return [network for network in self._networks if network.id not in used]

    def max_links(self) -> int:
        return max((len(self.links_of(node.id)) for node in self._nodes), default=0)

    def is_empty(self) -> bool:
        return not self._nodes and not self._networks

    # -- geometry -------------------------------------------------------------------------

    def sizeHint(self) -> QSize:
        count = len(self._nodes)
        width = 2 * MARGIN + count * CARD_W + max(count - 1, 0) * self._connector_w
        if self.orphan_networks():
            width += 30 + 140 - (self._connector_w if count else 0)
        width = max(width, 320)
        height = 2 * MARGIN + CARD_H + self.max_links() * (ADDRESS_PILL_H + 4) + 8
        return QSize(width, max(height, self.minimumHeight()))

    def minimumSizeHint(self) -> QSize:
        if self._compact:
            return QSize(200, self.minimumHeight())
        return self.sizeHint()

    def content_width(self) -> int:
        count = len(self._nodes)
        return count * CARD_W + max(count - 1, 0) * self._connector_w

    # -- painting -------------------------------------------------------------------------

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        self._paint_grid(painter)

        if self.is_empty():
            painter.setPen(QColor(theme.MUTED))
            font = QFont(self.font())
            font.setPointSizeF(max(8.0, font.pointSizeF()))
            painter.setFont(font)
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, self.EMPTY_TEXT)
            return

        top = MARGIN
        x = MARGIN
        if self._compact:
            # Centre the chain; the address pills below need the same vertical room.
            x = max(MARGIN, (self.width() - self.content_width()) // 2)
            used_height = CARD_H + self.max_links() * (ADDRESS_PILL_H + 4)
            top = max(MARGIN, (self.height() - used_height) // 2)
        for index, node in enumerate(self._nodes):
            card = QRect(x, top, CARD_W, CARD_H)
            self._paint_card(painter, card, node)
            self._paint_addresses(painter, card, node)
            if index + 1 < len(self._nodes):
                connector = QRect(card.right() + 1, top, self._connector_w, CARD_H)
                network = self.connector_network(node.id, self._nodes[index + 1].id)
                self._paint_connector(painter, connector, network)
            x += CARD_W + self._connector_w

        orphans = self.orphan_networks()
        if orphans:
            x = MARGIN if not self._nodes else x - self._connector_w + 30
            y = top + 8
            for network in orphans:
                self._paint_pill(
                    painter,
                    QRect(x, y, 140, 20),
                    f"{network.id} \u00b7 {network.subnet}" if network.subnet else network.id,
                    dashed=True,
                )
                y += 26

    def _paint_grid(self, painter: QPainter) -> None:
        painter.fillRect(self.rect(), QColor("#f8fafc"))
        pen = QPen(QColor("#f1f5f9"))
        pen.setWidth(1)
        painter.setPen(pen)
        for gx in range(0, self.width(), GRID):
            painter.drawLine(gx, 0, gx, self.height())
        for gy in range(0, self.height(), GRID):
            painter.drawLine(0, gy, self.width(), gy)

    def _paint_card(self, painter: QPainter, rect: QRect, node: TopologyNode) -> None:
        painter.setPen(QPen(QColor(theme.LINE), 1.5))
        painter.setBrush(QColor(theme.CARD))
        painter.drawRoundedRect(QRectF(rect), 12, 12)

        links = len(self.links_of(node.id))
        icon_rect = QRect(rect.left(), rect.top() + 6, rect.width(), 22)
        icon_name = node_icon_name(links)
        if icons.icon_available(icon_name):
            pixmap = icons.pixmap(icon_name, NODE_CARD_ICON_SIZE, theme.INK)
            painter.drawPixmap(
                icon_rect.center().x() - pixmap.width() // 2,
                icon_rect.center().y() - pixmap.height() // 2 + 1,
                pixmap,
            )
        else:
            icon = NODE_GATEWAY_GLYPH if links >= 2 else NODE_HOST_GLYPH
            painter.setPen(QColor(theme.INK))
            icon_font = QFont(self.font())
            icon_font.setPointSizeF(14)
            painter.setFont(icon_font)
            painter.drawText(icon_rect, Qt.AlignmentFlag.AlignCenter, icon)

        id_font = QFont(self.font())
        id_font.setBold(True)
        id_font.setPointSizeF(9)
        painter.setFont(id_font)
        painter.drawText(
            QRect(rect.left() + 4, rect.top() + 30, rect.width() - 8, 16),
            Qt.AlignmentFlag.AlignCenter,
            QFontMetrics(id_font).elidedText(
                node.id, Qt.TextElideMode.ElideRight, rect.width() - 8
            ),
        )

        role_font = QFont(self.font())
        role_font.setPointSizeF(7.5)
        painter.setFont(role_font)
        painter.setPen(QColor(theme.MUTED))
        painter.drawText(
            QRect(rect.left(), rect.top() + 46, rect.width(), 14),
            Qt.AlignmentFlag.AlignCenter,
            node_role(links),
        )

    def _paint_addresses(self, painter: QPainter, card: QRect, node: TopologyNode) -> None:
        y = card.bottom() + 6
        metrics = QFontMetrics(self._pill_font())
        for link in self.links_of(node.id):
            text = f"{link.network} \u00b7 {link.address}" if link.address else link.network
            # Wide enough for the whole address when possible, centred under the card.
            width = min(
                max(card.width(), metrics.horizontalAdvance(text) + 16),
                CARD_W + self._connector_w - 12,
            )
            pill = QRect(card.center().x() - width // 2, y, width, ADDRESS_PILL_H)
            self._paint_pill(painter, pill, text)
            y += ADDRESS_PILL_H + 4

    def _paint_connector(
        self, painter: QPainter, rect: QRect, network: TopologyNetwork | None
    ) -> None:
        mid_y = rect.top() + CARD_H // 2
        pen = QPen(QColor("#cbd5e1"), 2)
        if network is None:
            pen.setStyle(Qt.PenStyle.DotLine)
            pen.setColor(QColor(theme.LINE))
        painter.setPen(pen)
        painter.drawLine(rect.left(), mid_y, rect.right(), mid_y)
        if network is None:
            return
        text = f"{network.id} \u00b7 {network.subnet}" if network.subnet else network.id
        pill_w = min(
            rect.width() - 6, max(48, QFontMetrics(self._pill_font()).horizontalAdvance(text) + 16)
        )
        pill = QRect(rect.center().x() - pill_w // 2, mid_y - 10, pill_w, 20)
        self._paint_pill(painter, pill, text)

    def _pill_font(self) -> QFont:
        font = QFont(self.font())
        font.setFamily("Consolas")
        font.setPointSizeF(7.5)
        return font

    def _paint_pill(self, painter: QPainter, rect: QRect, text: str, dashed: bool = False) -> None:
        pen = QPen(QColor(theme.LINE), 1)
        if dashed:
            pen.setStyle(Qt.PenStyle.DashLine)
        painter.setPen(pen)
        painter.setBrush(QColor(theme.CARD))
        painter.drawRoundedRect(QRectF(rect), rect.height() / 2, rect.height() / 2)
        font = self._pill_font()
        painter.setFont(font)
        painter.setPen(QColor("#475569"))
        elided = QFontMetrics(font).elidedText(
            text, Qt.TextElideMode.ElideMiddle, rect.width() - 10
        )
        painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, elided)


class TopologyCanvas(QScrollArea):
    """Scrollable host for a TopologyView (the mockup's .topology-canvas)."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.view = TopologyView()
        self.setWidget(self.view)
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setStyleSheet("QScrollArea { background: #f8fafc; border-radius: 8px; }")

    def set_topology(self, nodes, networks, links) -> None:
        self.view.set_topology(nodes, networks, links)
