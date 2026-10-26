from __future__ import annotations

import httpx
import pytest
from PySide6.QtWidgets import QTextBrowser
from qt_helpers import ImmediateWorker

from practicum_desktop import embedded_view
from practicum_desktop.api_client import PortMappingInfo
from practicum_desktop.embedded_view import (
    EmbeddedLabView,
    ProbeResult,
    pick_default_mapping,
    probe_service,
)


class FakeWebView(QTextBrowser):
    def __init__(self) -> None:
        super().__init__()
        self.urls: list[str] = []
        self.reloads = 0

    def setUrl(self, url) -> None:
        self.urls.append(url.toString())

    def reload(self) -> None:
        self.reloads += 1


# ----- probe_service ---------------------------------------------------------------------------


def test_probe_reports_http_service_as_reachable(monkeypatch) -> None:
    seen: list[str] = []

    def fake_get(url, **kwargs):
        seen.append(url)
        return httpx.Response(401, request=httpx.Request("GET", url))  # any status counts

    monkeypatch.setattr(httpx, "get", fake_get)

    result = probe_service(3000)

    assert result == ProbeResult(reachable=True, url="http://localhost:3000/")
    assert seen == ["http://localhost:3000/"]


def test_probe_falls_back_to_https_when_plain_http_is_garbled(monkeypatch) -> None:
    def fake_get(url, **kwargs):
        if url.startswith("http://"):
            raise httpx.RemoteProtocolError("illegal request", request=httpx.Request("GET", url))
        return httpx.Response(200, request=httpx.Request("GET", url))

    monkeypatch.setattr(httpx, "get", fake_get)

    result = probe_service(3001)

    assert result.reachable is True
    assert result.url == "https://localhost:3001/"


def test_probe_treats_nginx_plain_http_on_tls_port_as_https(monkeypatch) -> None:
    """webtop's 3001: nginx answers plain HTTP with 400 'The plain HTTP request was sent to
    HTTPS port' - that is a TLS port, not a working http UI."""
    seen: list[str] = []

    def fake_get(url, **kwargs):
        seen.append(url)
        if url.startswith("http://"):
            return httpx.Response(
                400,
                text="<h1>400 Bad Request</h1>The plain HTTP request was sent to HTTPS port<hr>nginx",
                request=httpx.Request("GET", url),
            )
        return httpx.Response(200, request=httpx.Request("GET", url))

    monkeypatch.setattr(httpx, "get", fake_get)

    result = probe_service(3001)

    assert seen == ["http://localhost:3001/", "https://localhost:3001/"]
    assert result == ProbeResult(reachable=True, url="https://localhost:3001/")


def test_probe_reports_refused_and_timeout_as_not_ready(monkeypatch) -> None:
    def refused(url, **kwargs):
        raise httpx.ConnectError(
            "[Errno 111] Connection refused", request=httpx.Request("GET", url)
        )

    monkeypatch.setattr(httpx, "get", refused)
    assert probe_service(3000).reachable is False
    assert "refused" in probe_service(3000).detail

    def slow(url, **kwargs):
        raise httpx.ReadTimeout("timed out", request=httpx.Request("GET", url))

    monkeypatch.setattr(httpx, "get", slow)
    assert probe_service(3000) == ProbeResult(reachable=False, detail="no response yet")


def test_default_mapping_prefers_web_like_tcp_ports() -> None:
    mappings = [
        PortMappingInfo(2222, 22, "tcp"),
        PortMappingInfo(5353, 53, "udp"),
        PortMappingInfo(3001, 3001, "tcp"),
    ]
    assert pick_default_mapping(mappings).host == 3001
    # webtop: plain-http 3000 beats https-only 3001 whatever the order (the gate's port fix
    # re-appends a remapped 3000 after 3001).
    webtop = [PortMappingInfo(3001, 3001, "tcp"), PortMappingInfo(3002, 3000, "tcp")]
    assert pick_default_mapping(webtop).host == 3002
    assert pick_default_mapping([PortMappingInfo(2222, 22, "tcp")]).host == 2222
    assert pick_default_mapping([PortMappingInfo(5353, 53, "udp")]) is None
    assert pick_default_mapping([]) is None


# ----- EmbeddedLabView -----------------------------------------------------------------------


@pytest.fixture
def view(monkeypatch):
    monkeypatch.setattr(embedded_view, "CallableWorker", ImmediateWorker)
    web = FakeWebView()
    probes: list[int] = []
    outcome = {"result": ProbeResult(True, "http://localhost:3001/")}

    def probe(port: int) -> ProbeResult:
        probes.append(port)
        return outcome["result"]

    widget = EmbeddedLabView(web_view_factory=lambda parent: web, probe=probe)
    widget.web = web
    widget.probes = probes
    widget.outcome = outcome
    return widget


def test_no_ports_explains_instead_of_blank(view: EmbeddedLabView) -> None:
    view.set_port_mappings([])
    view.set_lab_running(True)

    assert "no browser-accessible ports" in view.message_title.text()
    assert "Open shell" in view.message_detail.text()
    assert view.stack.currentWidget() is view.message_page
    assert view.port_picker.isHidden()
    assert not view.open_external_button.isEnabled()


def test_not_running_shows_waiting_card_without_probing(view: EmbeddedLabView) -> None:
    view.set_port_mappings([PortMappingInfo(3001, 3001, "tcp")])

    assert view.current_url == "http://localhost:3001/"
    assert "not running" in view.message_title.text()
    assert view.probes == []


def test_running_lab_probes_then_loads_in_the_web_view(view: EmbeddedLabView) -> None:
    view.set_port_mappings([PortMappingInfo(3001, 3001, "tcp")])

    view.set_lab_running(True)

    assert view.probes == [3001]
    assert view.web.urls[-1] == "http://localhost:3001/"
    assert view.stack.currentWidget() is view.web
    assert view.url_label.text() == "http://localhost:3001"


def test_unreachable_service_waits_and_retries(view: EmbeddedLabView) -> None:
    view.outcome["result"] = ProbeResult(False, detail="connection refused")
    view.set_port_mappings([PortMappingInfo(3001, 3001, "tcp")])

    view.set_lab_running(True)

    assert "Waiting for the service on localhost:3001" in view.message_title.text()
    assert "Retrying" in view.message_detail.text()
    assert view._retry_timer.isActive()
    assert view.stack.currentWidget() is view.message_page

    view.outcome["result"] = ProbeResult(True, "https://localhost:3001/")
    view._probe_selected()  # what the retry timer does

    assert view.current_url == "https://localhost:3001/"
    assert view.stack.currentWidget() is view.web


def test_multiple_ports_offer_a_picker_and_switch_on_choice(view: EmbeddedLabView) -> None:
    view.set_port_mappings([PortMappingInfo(3000, 3000, "tcp"), PortMappingInfo(3001, 3001, "tcp")])
    view.set_lab_running(True)
    assert view.port_picker.isVisibleTo(view)
    assert view.port_picker.count() == 2
    assert view.selected_mapping().host == 3000

    view.outcome["result"] = ProbeResult(True, "http://localhost:3001/")
    view.port_picker.setCurrentIndex(1)

    assert view.probes[-1] == 3001
    assert view.current_url == "http://localhost:3001/"


def test_open_in_system_browser_uses_the_current_url(view: EmbeddedLabView, monkeypatch) -> None:
    opened: list[str] = []
    monkeypatch.setattr(embedded_view.webbrowser, "open", opened.append)
    emitted: list[str] = []
    view.url_opened_externally.connect(emitted.append)
    view.set_port_mappings([PortMappingInfo(3001, 3001, "tcp")])
    view.set_lab_running(True)

    view.open_external_button.click()

    assert opened == ["http://localhost:3001/"]
    assert emitted == ["http://localhost:3001/"]


def test_reload_reloads_the_page_when_shown_else_reprobes(view: EmbeddedLabView) -> None:
    view.set_port_mappings([PortMappingInfo(3001, 3001, "tcp")])
    view.set_lab_running(True)
    view.reload()
    assert view.web.reloads == 1

    view.set_lab_running(False)
    probes_before = len(view.probes)
    view.reload()
    assert view.web.reloads == 1
    assert len(view.probes) == probes_before  # not running: nothing to probe


def test_without_web_engine_offers_system_browser(monkeypatch) -> None:
    monkeypatch.setattr(embedded_view, "CallableWorker", ImmediateWorker)
    view = EmbeddedLabView(
        web_view_factory=lambda parent: None,
        probe=lambda port: ProbeResult(True, f"http://localhost:{port}/"),
    )
    view.set_port_mappings([PortMappingInfo(8080, 80, "tcp")])

    view.set_lab_running(True)

    assert view.has_web_engine is False
    assert "not available" in view.message_title.text()
    assert view.message_button.isVisibleTo(view)
    assert view.current_url == "http://localhost:8080/"


def test_clear_resets_everything(view: EmbeddedLabView) -> None:
    view.set_port_mappings([PortMappingInfo(3001, 3001, "tcp")])
    view.set_lab_running(True)

    view.clear()

    assert view.current_url == ""
    assert view.message_title.text() == "No lab open."
    assert view.web.urls[-1] == "about:blank"


def test_toolbar_buttons_carry_icon_or_name(monkeypatch) -> None:
    view = EmbeddedLabView(web_view_factory=lambda parent: FakeWebView())

    assert not view.open_external_button.icon().isNull()  # the design "forward" icon
    assert view.open_external_button.text() == ""
    assert view.open_external_button.accessibleName() == "Open in your system browser"
    assert view.open_external_button.toolTip() == "Open in your system browser"
    assert not view.reload_button.icon().isNull()  # the derived "refresh" icon
    assert view.reload_button.text() == ""
    assert view.reload_button.accessibleName() == "Reload"
    assert view.reload_button.toolTip() == "Reload"


def test_picker_lists_machines_by_name_and_switches_between_desktops(
    view: EmbeddedLabView,
) -> None:
    """Two Ubuntu Desktop machines: the picker names them, defaults to the first one's plain
    web port, and choosing the other loads that machine's port."""
    view.set_port_mappings(
        [
            PortMappingInfo(3000, 3000, "tcp", node_id="desktop-1"),
            PortMappingInfo(3001, 3001, "tcp", node_id="desktop-1"),
            PortMappingInfo(3002, 3000, "tcp", node_id="desktop-2"),
            PortMappingInfo(3003, 3001, "tcp", node_id="desktop-2"),
        ]
    )
    view.set_lab_running(True)

    assert view.port_picker.isVisibleTo(view)
    assert [view.port_picker.itemText(i) for i in range(view.port_picker.count())] == [
        "desktop-1 \u00b7 localhost:3000",
        "desktop-1 \u00b7 localhost:3001 (https)",
        "desktop-2 \u00b7 localhost:3002",
        "desktop-2 \u00b7 localhost:3003 (https)",
    ]
    assert view.selected_mapping().node_id == "desktop-1"
    assert view.probes[-1] == 3000
    assert view.port_picker.accessibleName() == "Machine to show"

    view.outcome["result"] = ProbeResult(True, "http://localhost:3002/")
    view.port_picker.setCurrentIndex(2)

    assert view.selected_mapping().node_id == "desktop-2"
    assert view.probes[-1] == 3002
    assert view.current_url == "http://localhost:3002/"


def test_waiting_message_names_the_machine(view: EmbeddedLabView) -> None:
    view.outcome["result"] = ProbeResult(False, detail="refused")
    view.set_port_mappings([PortMappingInfo(3002, 3000, "tcp", node_id="desktop-2")])
    view.set_lab_running(True)

    assert view.message_title.text() == "Waiting for 'desktop-2' on localhost:3002\u2026"

    view.set_lab_running(False)
    assert "Start it to load 'desktop-2' on localhost:3002 here." == view.message_detail.text()


def test_mapping_labels_without_a_machine_keep_the_port_form() -> None:
    from practicum_desktop.embedded_view import mapping_label

    assert mapping_label(PortMappingInfo(8080, 80, "tcp")) == "localhost:8080 \u2192 80/tcp"
    dns = PortMappingInfo(5353, 53, "udp", node_id="dns")
    assert mapping_label(dns) == "dns \u00b7 localhost:5353/udp"


def test_capture_grabs_the_web_page_only_when_it_is_showing(view: EmbeddedLabView) -> None:
    view.set_port_mappings([])
    pixmap, problem = view.capture()
    assert pixmap is None
    assert "not showing a web interface" in problem and "Upload image" in problem

    view.set_port_mappings([PortMappingInfo(3001, 3001, "tcp")])
    view.set_lab_running(True)  # the fake probe answers → the web page is shown
    assert view.stack.currentWidget() is view.web
    pixmap, problem = view.capture()
    assert pixmap is not None and not pixmap.isNull() and problem == ""
