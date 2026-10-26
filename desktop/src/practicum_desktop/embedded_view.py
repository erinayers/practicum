"""Embedded lab view (windows-desktop-embedded-lab-view).

The running view's left pane: whatever the lab publishes on a host port - a noVNC desktop,
code-server, a web app under test - rendered inside the app with QWebEngineView instead of
the system browser. A thin browser chrome gives context: reload, the URL, a picker when the
lab publishes more than one host port - listed **per machine** ("desktop-1 · localhost:3000",
"desktop-2 · localhost:3002"), so a lab with several desktops switches between them by name -
and "open in system browser" for content the embedded view can't render well (downloads,
OS prompts).

Before loading, the view probes the port (`probe_service`) and shows a waiting state while
the container's service boots, retrying every few seconds; webtop-style images that only
speak HTTPS with a self-signed certificate on a port are detected by the probe and the page
accepts that certificate for localhost only.

QtWebEngine is optional at runtime: when it cannot be imported the pane falls back to an
"open in system browser" card, so the rest of the app keeps working.
"""

from __future__ import annotations

import webbrowser
from collections.abc import Callable
from dataclasses import dataclass

import httpx
from PySide6.QtCore import QSize, Qt, QTimer, QUrl, Signal
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from practicum_desktop import icons, theme
from practicum_desktop.api_client import PortMappingInfo
from practicum_desktop.widgets import edge_frame, make_button
from practicum_desktop.workers import CallableWorker

try:  # QtWebEngine ships with PySide6-Addons; keep the app usable without it (D-16).
    from PySide6.QtWebEngineCore import QWebEngineCertificateError, QWebEnginePage
    from PySide6.QtWebEngineWidgets import QWebEngineView
except ImportError:  # pragma: no cover - exercised only on installs without the addon
    QWebEngineView = None  # type: ignore[assignment]
    QWebEnginePage = None  # type: ignore[assignment]
    QWebEngineCertificateError = None  # type: ignore[assignment]

PROBE_TIMEOUT_SECONDS = 2.0
RETRY_INTERVAL_MS = 2500
LOCAL_HOSTS = {"localhost", "127.0.0.1"}
# Ports that are conventionally not web UIs; they are still listed, just not auto-selected.
NON_WEB_PORTS = {22, 23, 25, 53, 69, 110, 143, 389, 636, 3306, 5432, 6379, 27017}
# Container ports that are conventionally TLS-only (webtop's 3001, https); a plain-HTTP sibling
# is preferred when the lab publishes both.
TLS_PORTS = {443, 8443, 3001}
# nginx (and others) answer a plain-HTTP request on a TLS port with 400 and this sentence.
TLS_PORT_HINT = "http request was sent to https port"


@dataclass
class ProbeResult:
    """Outcome of asking a host port whether something web-like answers."""

    reachable: bool
    url: str = ""  # the URL that answered (scheme chosen by the probe)
    detail: str = ""


def url_for(port: int, scheme: str = "http") -> str:
    return f"{scheme}://localhost:{port}/"


def probe_service(port: int, timeout: float = PROBE_TIMEOUT_SECONDS) -> ProbeResult:
    """GET http://localhost:<port>/ and, if the port answers but not in plain HTTP, https://.

    Any HTTP status counts as "answering" (a 401 from code-server is still a web UI). A
    refused connection or a timeout means the service inside the container is not up yet.
    A port that accepts the connection but garbles a plain-HTTP request is most likely
    TLS-only (webtop's 3001), so the https URL is tried before giving up.
    """
    last_detail = ""
    for scheme in ("http", "https"):
        url = url_for(port, scheme)
        try:
            response = httpx.get(url, timeout=timeout, verify=False, follow_redirects=False)
        except httpx.ConnectError as exc:
            return ProbeResult(reachable=False, detail=_short(str(exc)) or "connection refused")
        except httpx.TimeoutException:
            return ProbeResult(reachable=False, detail="no response yet")
        except httpx.HTTPError as exc:
            last_detail = _short(str(exc))
            if scheme == "http":
                continue
            return ProbeResult(reachable=False, detail=last_detail)
        if (
            scheme == "http"
            and response.status_code == 400
            and TLS_PORT_HINT in response.text.lower()
        ):
            continue  # "The plain HTTP request was sent to HTTPS port" → this port wants https
        return ProbeResult(reachable=True, url=url)
    return ProbeResult(reachable=False, detail=last_detail)


def _short(detail: str) -> str:
    return detail.strip().splitlines()[0][:120] if detail.strip() else ""


def mapping_label(mapping: PortMappingInfo) -> str:
    """What the picker shows: the machine first, then the host port, with the https hint for
    TLS-only container ports (webtop's 3001)."""
    port = f"localhost:{mapping.host}"
    if mapping.protocol != "tcp":
        port += f"/{mapping.protocol}"
    elif mapping.container in TLS_PORTS:
        port += " (https)"
    if mapping.node_id:
        return f"{mapping.node_id} \u00b7 {port}"
    return f"{port} \u2192 {mapping.container}/{mapping.protocol}"


def pick_default_mapping(mappings: list[PortMappingInfo]) -> PortMappingInfo | None:
    """The mapping most likely to be a plain web UI: TCP, not a known non-web port, and a
    plain-HTTP port before a TLS-only sibling (webtop publishes http 3000 and https 3001; the
    order of the mappings must not matter - the gate's port fixes re-append them). Ties keep
    the spec order, so the first machine's desktop wins when several publish one."""
    tcp = [m for m in mappings if m.protocol == "tcp"]
    if not tcp:
        return None

    def score(mapping: PortMappingInfo) -> int:
        if mapping.container in NON_WEB_PORTS or mapping.host in NON_WEB_PORTS:
            return 2
        if mapping.container in TLS_PORTS:
            return 1
        return 0

    return min(tcp, key=score)  # min() is stable: ties keep the spec order


if QWebEnginePage is not None:

    class LocalLabPage(QWebEnginePage):
        """Accepts self-signed certificates, but only for localhost (D-28)."""

        def certificateError(self, error: QWebEngineCertificateError) -> bool:
            if error.url().host() in LOCAL_HOSTS:
                error.acceptCertificate()
                return True
            error.rejectCertificate()
            return False

else:  # pragma: no cover
    LocalLabPage = None  # type: ignore[assignment,misc]


def default_web_view_factory(parent: QWidget | None) -> QWidget | None:
    """Creates the QWebEngineView (or None when QtWebEngine is unavailable)."""
    if QWebEngineView is None:
        return None
    view = QWebEngineView(parent)
    if LocalLabPage is not None:
        view.setPage(LocalLabPage(view))
    return view


class EmbeddedLabView(QWidget):
    """Browser pane of the running view. Drive it with `set_port_mappings`, `set_lab_running`
    and `clear`; it probes, waits, loads and offers the system-browser fallback itself."""

    url_opened_externally = Signal(str)

    def __init__(
        self,
        parent: QWidget | None = None,
        web_view_factory: Callable[[QWidget | None], QWidget | None] = default_web_view_factory,
        probe: Callable[[int], ProbeResult] = probe_service,
    ) -> None:
        super().__init__(parent)
        self._mappings: list[PortMappingInfo] = []
        self._running = False
        self._current_url = ""
        self._probe = probe
        self._probe_worker: CallableWorker | None = None
        self._probing_port: int | None = None
        self._retry_timer = QTimer(self)
        self._retry_timer.setSingleShot(True)
        self._retry_timer.timeout.connect(self._probe_selected)
        self._build_ui(web_view_factory)
        self._show_message("No lab open.", "")

    # ----- UI --------------------------------------------------------------------------

    def _build_ui(self, web_view_factory) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        chrome = edge_frame("bottom", theme.LINE_SOFT)
        chrome_row = QHBoxLayout(chrome)
        chrome_row.setContentsMargins(12, 6, 12, 6)
        chrome_row.setSpacing(8)

        if icons.icon_available("refresh"):
            self.reload_button = make_button("", kind="ghost", icon="refresh")
            self.reload_button.setIconSize(QSize(16, 16))
        else:
            self.reload_button = make_button("\u21bb", kind="ghost")
        self.reload_button.setToolTip("Reload")
        self.reload_button.setAccessibleName("Reload")
        self.reload_button.setStyleSheet("padding: 2px 8px; font-size: 14px;")
        self.reload_button.clicked.connect(self.reload)
        chrome_row.addWidget(self.reload_button)

        self.url_label = QLabel("")
        self.url_label.setObjectName("urlBar")
        self.url_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        chrome_row.addWidget(self.url_label, 1)

        self.port_picker = QComboBox()
        self.port_picker.setToolTip(
            "Choose which machine (and published port) to show - each desktop in the lab is "
            "listed here"
        )
        self.port_picker.setAccessibleName("Machine to show")
        self.port_picker.setStyleSheet("padding: 3px 8px; font-size: 12px;")
        self.port_picker.currentIndexChanged.connect(self._on_port_picked)
        self.port_picker.hide()
        chrome_row.addWidget(self.port_picker)

        if icons.icon_available("forward"):
            self.open_external_button = make_button("", kind="ghost", icon="forward")
            self.open_external_button.setIconSize(QSize(16, 16))
        else:
            self.open_external_button = make_button("\u2197", kind="ghost")
        self.open_external_button.setToolTip("Open in your system browser")
        self.open_external_button.setAccessibleName("Open in your system browser")
        self.open_external_button.setStyleSheet("padding: 2px 8px; font-size: 14px;")
        self.open_external_button.clicked.connect(self.open_in_system_browser)
        chrome_row.addWidget(self.open_external_button)
        layout.addWidget(chrome)

        self.stack = QStackedWidget()
        layout.addWidget(self.stack, 1)

        # page 0: dark message card (waiting / no ports / stopped / no web engine)
        self.message_page = QFrame()
        self.message_page.setProperty("panel", "dark")
        message_layout = QVBoxLayout(self.message_page)
        message_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card = QFrame()
        card.setObjectName("messageCard")
        card.setStyleSheet(
            "QFrame#messageCard { background: #111827; border: 1px solid #1e293b;"
            " border-radius: 10px; }"
            "QLabel { color: #94a3b8; background: transparent; border: none; }"
        )
        card.setMinimumWidth(360)
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(28, 24, 28, 24)
        card_layout.setSpacing(8)
        if icons.icon_available("desktop"):
            icon = icons.icon_label("desktop", 34, "Lab view", colour="#94a3b8")
        else:
            icon = QLabel("\u25a1")  # an empty screen
            icon.setStyleSheet("font-size: 26px;")
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        card_layout.addWidget(icon, 0, Qt.AlignmentFlag.AlignHCenter)
        self.message_title = QLabel("")
        self.message_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.message_title.setWordWrap(True)
        self.message_title.setStyleSheet("font-size: 13px; color: #cbd5e1;")
        card_layout.addWidget(self.message_title)
        self.message_detail = QLabel("")
        self.message_detail.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.message_detail.setWordWrap(True)
        self.message_detail.setStyleSheet("font-size: 11px; color: #64748b;")
        card_layout.addWidget(self.message_detail)
        self.message_button = make_button("Open in system browser", kind="secondary", small=True)
        self.message_button.clicked.connect(self.open_in_system_browser)
        self.message_button.hide()
        card_layout.addWidget(self.message_button, 0, Qt.AlignmentFlag.AlignHCenter)
        message_layout.addWidget(card)
        self.stack.addWidget(self.message_page)

        # page 1: the web view (if available)
        self.web_view = web_view_factory(self)
        if self.web_view is not None:
            self.stack.addWidget(self.web_view)

    # ----- state -----------------------------------------------------------------------

    @property
    def has_web_engine(self) -> bool:
        return self.web_view is not None

    @property
    def current_url(self) -> str:
        return self._current_url

    def selected_mapping(self) -> PortMappingInfo | None:
        index = self.port_picker.currentIndex()
        if 0 <= index < len(self._mappings):
            return self._mappings[index]
        return None

    def set_port_mappings(self, mappings: list[PortMappingInfo]) -> None:
        """Lists the lab's published ports; picks the most web-like one by default."""
        self._mappings = list(mappings)
        self.port_picker.blockSignals(True)
        self.port_picker.clear()
        for mapping in self._mappings:
            self.port_picker.addItem(mapping_label(mapping))
        default = pick_default_mapping(self._mappings)
        if default is not None:
            self.port_picker.setCurrentIndex(self._mappings.index(default))
        self.port_picker.blockSignals(False)
        self.port_picker.setVisible(len(self._mappings) > 1)
        self._refresh()

    def set_lab_running(self, running: bool) -> None:
        self._running = running
        self._refresh()

    def clear(self) -> None:
        self._mappings = []
        self._running = False
        self.port_picker.clear()
        self.port_picker.hide()
        self._retry_timer.stop()
        self._set_url("")
        if self.web_view is not None:
            self.web_view.setUrl(QUrl("about:blank"))
        self._show_message("No lab open.", "")

    def _refresh(self) -> None:
        self._retry_timer.stop()
        mapping = self.selected_mapping()
        if mapping is None:
            self._set_url("")
            self._show_message(
                "This lab has no browser-accessible ports.",
                "Use Open shell on a node to work inside it; node addresses are only "
                "reachable from inside the lab.",
            )
            return
        self._set_url(url_for(mapping.host))
        who = f"'{mapping.node_id}'" if mapping.node_id else "the service"
        if not self._running:
            self._show_message(
                "The lab is not running.",
                f"Start it to load {who} on localhost:{mapping.host} here.",
            )
            return
        self._show_message(
            f"Waiting for {who} on localhost:{mapping.host}\u2026",
            "The container is starting its web service. This view loads automatically "
            "as soon as it answers.",
        )
        self._probe_selected()

    def _probe_selected(self) -> None:
        mapping = self.selected_mapping()
        if mapping is None or not self._running:
            return
        self._probing_port = mapping.host
        self._probe_worker = CallableWorker(self._probe, mapping.host)
        self._probe_worker.finished_call.connect(self._on_probed)
        self._probe_worker.start()

    def _on_probed(self, result: ProbeResult) -> None:
        mapping = self.selected_mapping()
        if mapping is None or not self._running or mapping.host != self._probing_port:
            return  # the selection changed meanwhile; that probe is stale
        if not result.reachable:
            self.message_detail.setText(
                "Still waiting for the container's web service to answer"
                + (f" ({result.detail})" if result.detail else "")
                + ". Retrying\u2026"
            )
            self._retry_timer.start(RETRY_INTERVAL_MS)
            return
        self._set_url(result.url)
        if self.web_view is None:
            self._show_message(
                "The embedded browser is not available on this installation.",
                "Open the lab in your system browser instead.",
                offer_external=True,
            )
            return
        self.web_view.setUrl(QUrl(result.url))
        self.stack.setCurrentWidget(self.web_view)

    def _on_port_picked(self, _index: int) -> None:
        self._refresh()

    def _set_url(self, url: str) -> None:
        self._current_url = url
        self.url_label.setText(url.rstrip("/") if url else "")
        self.open_external_button.setEnabled(bool(url))
        self.reload_button.setEnabled(bool(url))

    def _show_message(self, title: str, detail: str, offer_external: bool = False) -> None:
        self.message_title.setText(title)
        self.message_detail.setText(detail)
        self.message_button.setVisible(offer_external)
        self.stack.setCurrentWidget(self.message_page)

    # ----- actions ---------------------------------------------------------------------

    def capture(self) -> tuple[QPixmap | None, str]:
        """A screenshot of what the lab view shows (the embedded page), or (None, why not):
        a lab without a web interface has nothing to capture here - the student uploads a
        screenshot of their terminal instead."""
        if self.web_view is None or self.stack.currentWidget() is not self.web_view:
            return None, (
                "The lab view is not showing a web interface right now, so there is nothing "
                "to capture here. Take a screenshot of your work yourself (for example of the "
                "node's shell window) and use Upload image."
            )
        pixmap = self.web_view.grab()
        if pixmap.isNull():
            return None, "The lab view could not be captured; try again in a moment."
        return pixmap, ""

    def reload(self) -> None:
        if self.web_view is not None and self.stack.currentWidget() is self.web_view:
            self.web_view.reload()
        else:
            self._refresh()

    def open_in_system_browser(self) -> None:
        if not self._current_url:
            return
        webbrowser.open(self._current_url)
        self.url_opened_externally.emit(self._current_url)
