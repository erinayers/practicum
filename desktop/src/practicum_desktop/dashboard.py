"""Welcome screen and Labs Dashboard (windows-desktop-labs-dashboard).

`WelcomeScreen` is the zero-state hero (Create New Lab / Import Existing Lab) and, when labs
do exist, offers the "You have N labs · View your labs dashboard →" link. `DashboardScreen`
lists every lab known to the API as a card (icon, name, origin/meta line, status badge,
activity line) with the actions that make sense for its status:

    running            Export · Open                    (no new Start call)
    stopped / defined  Export · Edit · Delete · Start   (Start goes through the pre-start gate)
    error              Export · Edit · Delete · Reset · Start  (Reset: confirmed, red)
    starting/stopping  Open                             (watch the progress; nothing else yet)

Delete and Reset ask through `dialogs.confirm()` (windows-desktop-in-app-dialogs). The
screens only emit signals; `MainWindow` does the API calls and navigation.
"""

from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from practicum_desktop import theme
from practicum_desktop.api_client import LabSummary
from practicum_desktop.labels import activity_line, lab_icon, origin_meta, plural
from practicum_desktop.widgets import (
    Badge,
    NoteBanner,
    bind,
    copyable_label,
    discard,
    edge_frame,
    make_button,
    page_container,
    payload_of,
    powered_by_docker,
    role_label,
)

CARD_COLUMNS = 2


class WelcomeScreen(QWidget):
    create_requested = Signal()
    import_requested = Signal()
    dashboard_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("screen")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        hero = QVBoxLayout()
        hero.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hero.setSpacing(14)
        title = role_label("practicum", "hero")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hero.addWidget(title)
        subtitle = role_label(
            "Create and manage Docker-based lab environments with ease.", "subtitle"
        )
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hero.addWidget(subtitle)

        self.blocked_banner = copyable_label("")
        self.blocked_banner.setProperty("banner", "warn")
        self.blocked_banner.setMaximumWidth(560)
        self.blocked_banner.hide()
        hero.addWidget(self.blocked_banner, 0, Qt.AlignmentFlag.AlignHCenter)
        self.note = NoteBanner(fixed_width=560)
        self.note_label = self.note.message_label
        hero.addWidget(self.note, 0, Qt.AlignmentFlag.AlignHCenter)

        cta = QHBoxLayout()
        cta.setSpacing(12)
        cta.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.create_button = make_button("Create New Lab", kind="primary")
        self.create_button.clicked.connect(self.create_requested.emit)
        cta.addWidget(self.create_button)
        self.import_button = make_button("Import Existing Lab", kind="secondary")
        self.import_button.clicked.connect(self.import_requested.emit)
        cta.addWidget(self.import_button)
        hero.addLayout(cta)

        self.dashboard_link = make_button("", kind="link")
        self.dashboard_link.clicked.connect(self.dashboard_requested.emit)
        self.dashboard_link.hide()
        hero.addWidget(self.dashboard_link, 0, Qt.AlignmentFlag.AlignHCenter)

        hero_widget = QWidget()
        hero_widget.setLayout(hero)
        layout.addWidget(hero_widget, 1)
        layout.addWidget(powered_by_docker())

    def set_lab_count(self, count: int) -> None:
        self.dashboard_link.setVisible(count > 0)
        self.dashboard_link.setText(
            f"You have {plural(count, 'lab')} \u00b7 View your labs dashboard \u2192"
        )

    def show_note(self, text: str, banner: str = "info") -> None:
        """A transient, dismissible note (e.g. the last lab was just deleted)."""
        self.note.show_note(text, banner)

    def set_blocked(self, message: str | None) -> None:
        """Shows why labs can't be loaded (API unreachable) and disables the actions that
        need the API; the welcome screen is the fallback when the dashboard has no data."""
        self.blocked_banner.setVisible(bool(message))
        self.blocked_banner.setText(message or "")
        self.create_button.setEnabled(not message)
        self.import_button.setEnabled(not message)


class LabCard(QFrame):
    """One dashboard card. Emits the action the user picked; does nothing itself."""

    open_requested = Signal(str)
    start_requested = Signal(str)
    delete_requested = Signal(str)
    reset_requested = Signal(str)
    edit_requested = Signal(str)
    export_requested = Signal(str)

    def __init__(self, lab: LabSummary, now: datetime | None = None, parent=None) -> None:
        super().__init__(parent)
        self.lab = lab
        self.setProperty("panel", "true")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 12)
        layout.setSpacing(10)

        top = QHBoxLayout()
        top.setSpacing(10)
        icon = QLabel(lab_icon(lab.origin))
        icon.setFixedSize(36, 36)
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon.setStyleSheet(f"background: {theme.LINE_SOFT}; border-radius: 10px; font-size: 17px;")
        top.addWidget(icon, 0, Qt.AlignmentFlag.AlignTop)
        names = QVBoxLayout()
        names.setSpacing(2)
        self.name_label = QLabel(lab.name)
        self.name_label.setProperty("role", "title")
        self.name_label.setWordWrap(True)
        names.addWidget(self.name_label)
        self.meta_label = QLabel(origin_meta(lab))
        self.meta_label.setProperty("role", "muted")
        self.meta_label.setWordWrap(True)
        names.addWidget(self.meta_label)
        top.addLayout(names, 1)
        self.badge = Badge(lab.status)
        top.addWidget(self.badge, 0, Qt.AlignmentFlag.AlignTop)
        layout.addLayout(top)

        if lab.status == "error" and lab.last_error:
            error = copyable_label(lab.last_error, role="error")
            error.setStyleSheet("font-size: 11px;")
            layout.addWidget(error)

        foot = edge_frame("top", theme.LINE_SOFT)
        foot_row = QHBoxLayout(foot)
        foot_row.setContentsMargins(0, 10, 0, 0)
        foot_row.setSpacing(6)
        self.time_label = QLabel(activity_line(lab, now))
        self.time_label.setProperty("role", "hint")
        foot_row.addWidget(self.time_label)
        foot_row.addStretch(1)
        self.buttons: dict[str, object] = {}
        for label, kind in self._actions_for(lab.status):
            button = make_button(label, kind=kind, small=True)
            bind(button, self._on_action_clicked, label)
            foot_row.addWidget(button)
            self.buttons[label] = button
        layout.addWidget(foot)

    @staticmethod
    def _actions_for(status: str) -> list[tuple[str, str]]:
        if status == "running":
            return [("Export", "secondary"), ("Open", "primary")]
        if status in ("starting", "stopping"):
            return [("Open", "secondary")]
        actions = [("Export", "secondary"), ("Edit", "secondary"), ("Delete", "secondary")]
        if status == "error":
            actions.append(("Reset", "danger"))
        actions.append(("Start", "primary"))
        return actions

    def _on_action_clicked(self) -> None:
        signals = {
            "Open": self.open_requested,
            "Start": self.start_requested,
            "Delete": self.delete_requested,
            "Reset": self.reset_requested,
            "Edit": self.edit_requested,
            "Export": self.export_requested,
        }
        signal = signals.get(payload_of(self.sender()))
        if signal is not None:
            signal.emit(self.lab.id)


class DashboardScreen(QWidget):
    create_requested = Signal()
    import_requested = Signal()
    open_requested = Signal(str)
    start_requested = Signal(str)
    delete_requested = Signal(str)
    reset_requested = Signal(str)
    edit_requested = Signal(str)
    export_requested = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.cards: list[LabCard] = []
        self._build_ui()

    def _build_ui(self) -> None:
        self.setObjectName("screen")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        page, layout = page_container()
        outer.addWidget(page, 1)

        head = QHBoxLayout()
        head.setSpacing(10)
        titles = QVBoxLayout()
        titles.setSpacing(4)
        titles.addWidget(role_label("Your Labs", "h1"))
        titles.addWidget(role_label("Resume a lab, or start something new.", "subtitle"))
        head.addLayout(titles, 1)
        self.import_button = make_button("Import Existing Lab", kind="secondary")
        self.import_button.clicked.connect(self.import_requested.emit)
        head.addWidget(self.import_button, 0, Qt.AlignmentFlag.AlignTop)
        self.create_button = make_button("+ Create New Lab", kind="primary")
        self.create_button.clicked.connect(self.create_requested.emit)
        head.addWidget(self.create_button, 0, Qt.AlignmentFlag.AlignTop)
        layout.addLayout(head)

        self.note = NoteBanner()
        self.message_label = self.note.message_label
        layout.addWidget(self.note)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.grid_host = QWidget()
        self.grid = QGridLayout(self.grid_host)
        self.grid.setContentsMargins(0, 6, 6, 8)
        self.grid.setHorizontalSpacing(16)
        self.grid.setVerticalSpacing(16)
        self.grid.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.scroll.setWidget(self.grid_host)
        layout.addWidget(self.scroll, 1)
        outer.addWidget(powered_by_docker())

    def set_labs(self, labs: list[LabSummary], now: datetime | None = None) -> None:
        for card in self.cards:
            self.grid.removeWidget(card)
            discard(card)
        self.cards = []
        for index, lab in enumerate(labs):
            card = LabCard(lab, now)
            card.open_requested.connect(self.open_requested.emit)
            card.start_requested.connect(self.start_requested.emit)
            card.delete_requested.connect(self.delete_requested.emit)
            card.reset_requested.connect(self.reset_requested.emit)
            card.edit_requested.connect(self.edit_requested.emit)
            card.export_requested.connect(self.export_requested.emit)
            self.grid.addWidget(card, index // CARD_COLUMNS, index % CARD_COLUMNS)
            self.cards.append(card)
        for column in range(CARD_COLUMNS):
            self.grid.setColumnStretch(column, 1)

    def card_for(self, lab_id: str) -> LabCard | None:
        return next((card for card in self.cards if card.lab.id == lab_id), None)

    def show_message(self, text: str, banner: str = "info") -> None:
        """A transient, dismissible note above the cards."""
        self.note.show_note(text, banner)

    def set_actions_enabled(self, enabled: bool) -> None:
        self.import_button.setEnabled(enabled)
        self.create_button.setEnabled(enabled)
