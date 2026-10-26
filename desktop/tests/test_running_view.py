from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtCore import QSettings
from PySide6.QtGui import QColor, QPixmap
from PySide6.QtWidgets import QTextBrowser
from qt_helpers import ImmediateWorker, StalledWorker

from practicum_desktop import embedded_view, running_view
from practicum_desktop.api_client import (
    LabSummary,
    ManualSectionInfo,
    ManualTaskInfo,
    NodeProgressInfo,
    PortMappingInfo,
    PreviewResult,
    ResourceStatusInfo,
    StartResult,
    StatusResult,
    TopologyInfo,
    TopologyInterfaceInfo,
    TopologyNodeInfo,
)
from practicum_desktop.embedded_view import ProbeResult
from practicum_desktop.node_shell import ShellLaunchResult
from practicum_desktop.running_view import RESET_TITLE, RunningLabView


class FakeWebView(QTextBrowser):
    """Stands in for QWebEngineView: records the URLs it was asked to load."""

    def __init__(self) -> None:
        super().__init__()
        self.urls: list[str] = []
        self.reloads = 0

    def setUrl(self, url) -> None:
        self.urls.append(url.toString())

    def reload(self) -> None:
        self.reloads += 1


class FakeApiClient:
    def __init__(self) -> None:
        self.status = "running"
        self.last_error: str | None = None
        self.progress: list[NodeProgressInfo] = []
        self.calls: list[str] = []
        self.stop_result = StartResult(success=True, detail="Lab stopped.", lab_status="stopped")
        self.restart_result = StartResult(
            success=True, detail="Lab restarted.", lab_status="running"
        )
        self.reset_result = StartResult(success=True, detail="Lab reset.", lab_status="defined")
        self.port_mappings = [PortMappingInfo(3001, 3001, "tcp")]
        self.topology_nodes = [TopologyNodeInfo("host", "ubuntu:22.04")]
        self.note: str | None = None
        self.sections = [
            ManualSectionInfo("s1", "Install", "pip install", [ManualTaskInfo("t1", "Installed")]),
            ManualSectionInfo("s2", "Run", "flask run", [ManualTaskInfo("t2", "Running")]),
        ]

    def get_preview(self, lab_id: str) -> PreviewResult:
        self.calls.append("preview")
        return PreviewResult(
            success=True,
            name="Build a Python API",
            manual_sections=list(self.sections),
            port_mappings=self.port_mappings,
            topology=TopologyInfo(
                nodes=list(self.topology_nodes),
                interfaces=[TopologyInterfaceInfo("host", "lab-net", "10.90.0.10/24")],
            ),
        )

    def get_status(self, lab_id: str) -> StatusResult:
        self.calls.append("status")
        exists = self.status in ("running", "stopped")
        return StatusResult(
            success=True,
            lab_status=self.status,
            resources=[
                ResourceStatusInfo(
                    "container",
                    "host",
                    f"practicum-{lab_id}-host",
                    exists,
                    "running" if self.status == "running" else ("exited" if exists else None),
                    note=self.note,
                )
            ],
            progress=self.progress,
            last_error=self.last_error,
        )

    def stop_lab(self, lab_id: str) -> StartResult:
        self.calls.append("stop")
        self.status = self.stop_result.lab_status or self.status
        return self.stop_result

    def restart_lab(self, lab_id: str) -> StartResult:
        self.calls.append("restart")
        return self.restart_result

    def reset_lab(self, lab_id: str) -> StartResult:
        self.calls.append("reset")
        self.status = self.reset_result.lab_status or self.status
        return self.reset_result


@pytest.fixture
def settings(tmp_path: Path) -> QSettings:
    return QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)


@pytest.fixture
def view(monkeypatch, settings: QSettings, tmp_path: Path):
    monkeypatch.setattr(running_view, "CallableWorker", ImmediateWorker)
    monkeypatch.setattr(embedded_view, "CallableWorker", ImmediateWorker)
    api = FakeApiClient()
    web = FakeWebView()
    widget = RunningLabView(
        api, settings, web_view_factory=lambda parent: web, screenshot_dir=tmp_path / "shots"
    )
    widget.embedded_view._probe = lambda port: ProbeResult(True, f"http://localhost:{port}/")
    widget.api = api
    widget.web = web
    widget.show()
    yield widget
    widget.clear()
    widget.close()
    widget.deleteLater()


def _lab(status: str = "running") -> LabSummary:
    return LabSummary(
        id="lab-1",
        name="Build a Python API",
        status=status,
        origin="imported",
        source_file="python-api-lab.json",
    )


# ----- header, badge, toolbar ---------------------------------------------------------------


def test_running_lab_shows_restart_stop_reset_and_hides_start(view: RunningLabView) -> None:
    view.show_lab(_lab("running"))

    assert view.title_label.text() == "Build a Python API"
    assert view.meta_label.text() == "Imported from python-api-lab.json"
    assert view.badge.text() == "\u25cf Running"
    assert view.restart_button.isVisible() and view.stop_button.isVisible()
    assert view.reset_button.isVisible() and view.reset_button.isEnabled()
    assert view.reset_button.property("kind") == "danger"  # visually distinct from Stop
    assert view.start_button.isHidden()


def test_stopped_lab_offers_start_and_reset_only(view: RunningLabView) -> None:
    view.api.status = "stopped"

    view.show_lab(_lab("stopped"))

    assert view.badge.text() == "\u25cf Stopped"
    assert view.start_button.isVisible() and view.start_button.isEnabled()
    assert view.restart_button.isHidden() and view.stop_button.isHidden()
    assert view.reset_button.isEnabled()  # Reset is still offered when already stopped


def test_start_button_routes_through_the_owner_not_the_api(view: RunningLabView) -> None:
    view.api.status = "defined"
    view.show_lab(_lab("defined"))
    requested: list[str] = []
    view.start_requested.connect(requested.append)

    view.start_button.click()

    assert requested == ["lab-1"]
    assert "start" not in view.api.calls


# ----- stop / restart -----------------------------------------------------------------------


def test_stop_runs_without_confirmation_and_updates_the_badge(view: RunningLabView) -> None:
    view.show_lab(_lab())
    changes: list[tuple[str, str]] = []
    view.lab_changed.connect(lambda lab_id, status: changes.append((lab_id, status)))

    view.stop_button.click()

    assert view.api.calls.count("stop") == 1
    assert view.badge.text() == "\u25cf Stopped"
    assert "Lab stopped." in view.message_label.text()
    assert ("lab-1", "stopped") in changes
    assert view.start_button.isVisible()


def test_restart_runs_without_confirmation(view: RunningLabView) -> None:
    view.show_lab(_lab())

    view.restart_button.click()

    assert view.api.calls.count("restart") == 1
    assert "Lab restarted." in view.message_label.text()
    assert view.badge.text() == "\u25cf Running"


def test_lifecycle_buttons_are_disabled_while_a_call_is_in_flight(
    monkeypatch, settings: QSettings
) -> None:
    monkeypatch.setattr(running_view, "CallableWorker", StalledWorker)
    monkeypatch.setattr(embedded_view, "CallableWorker", ImmediateWorker)
    StalledWorker.instances = []
    api = FakeApiClient()
    view = RunningLabView(api, settings, web_view_factory=lambda parent: FakeWebView())
    view.embedded_view._probe = lambda port: ProbeResult(False, detail="not yet")
    view.show()
    view.show_lab(_lab())
    for worker in list(StalledWorker.instances):  # let preview + status land
        worker.finish()
    StalledWorker.instances = []

    view.stop_button.click()

    assert view.busy is True
    assert not view.stop_button.isEnabled()
    assert not view.restart_button.isEnabled()
    assert not view.reset_button.isEnabled()
    assert "Stopping lab" in view.message_label.text()
    # A second click while busy must not queue another call.
    view.reset_button.click()
    stop_workers = [w for w in StalledWorker.instances if w._func == api.stop_lab]
    assert len(stop_workers) == 1
    assert "reset" not in api.calls

    stop_workers[0].finish()
    for worker in list(StalledWorker.instances):
        if worker._func == api.get_status:
            worker.finish()

    assert view.busy is False
    assert view.reset_button.isEnabled()
    view.clear()
    view.close()


def test_busy_api_answer_is_explained_without_changing_state(view: RunningLabView) -> None:
    view.show_lab(_lab())
    view.api.stop_result = StartResult(success=False, detail="Lab is already starting", busy=True)

    view.stop_button.click()

    assert "already starting" in view.message_label.text()
    assert view.message_label.property("banner") == "warn"
    assert view.badge.text() == "\u25cf Running"


def test_failed_stop_shows_error_and_error_badge(view: RunningLabView) -> None:
    view.show_lab(_lab())
    view.api.stop_result = StartResult(
        success=False, detail="Container could not stop", lab_status="error"
    )

    view.stop_button.click()

    assert "Container could not stop" in view.message_label.text()
    assert view.message_label.property("banner") == "error"
    assert view.badge.text() == "\u25cf Error"


# ----- reset -----------------------------------------------------------------------------------


def test_reset_always_asks_first_and_cancel_changes_nothing(
    view: RunningLabView, monkeypatch
) -> None:
    prompts: list[dict] = []
    monkeypatch.setattr(
        running_view, "confirm", lambda *args, **kwargs: prompts.append(kwargs) or False
    )
    view.show_lab(_lab())

    view.reset_button.click()

    assert len(prompts) == 1
    assert prompts[0]["title"] == RESET_TITLE
    assert prompts[0]["destructive"] is True
    assert "more destructive than Stop" in prompts[0]["message"]
    assert "cannot be undone" in prompts[0]["message"]
    assert "reset" not in view.api.calls
    assert view.badge.text() == "\u25cf Running"
    assert view.stop_button.isEnabled()


def test_confirmed_reset_calls_the_api_and_returns_the_lab_to_ready(
    view: RunningLabView, monkeypatch
) -> None:
    monkeypatch.setattr(running_view, "confirm", lambda *args, **kwargs: True)
    view.show_lab(_lab())

    view.reset_button.click()

    assert view.api.calls.count("reset") == 1
    assert view.badge.text() == "\u25cf Ready"
    assert "Lab reset to its original state" in view.message_label.text()
    assert view.start_button.isVisible()
    assert view.restart_button.isHidden()


def test_reset_keeps_manual_progress(view: RunningLabView, monkeypatch, settings) -> None:
    monkeypatch.setattr(running_view, "confirm", lambda *args, **kwargs: True)
    view.show_lab(_lab())
    view.manual_flyout.mark_next_step_complete()
    assert view.manual_flyout.progress() == (1, 2)
    assert settings.value("manual_progress/lab-1/s1/t1") in (True, "true")

    view.reset_button.click()

    assert view.manual_flyout.progress() == (1, 2)
    assert settings.value("manual_progress/lab-1/s1/t1") in (True, "true")


# ----- status polling / progress / nodes -----------------------------------------------------


def test_starting_lab_shows_real_progress_panel(view: RunningLabView) -> None:
    view.api.status = "starting"
    view.api.progress = [
        NodeProgressInfo(
            "host", "ubuntu:22.04", "pulling_image", percent=35, detail="2 of 6 layers"
        )
    ]

    view.show_lab(_lab("starting"))

    assert view.center_stack.currentIndex() == 1
    assert "Downloading ubuntu:22.04" in view.progress_panel.summary_label.text()
    assert view.badge.text() == "\u25cf Starting\u2026"
    assert not view.reset_button.isEnabled()  # transitional: nothing may overlap
    assert view._poll_timer.interval() == running_view.FAST_POLL_MS

    view.api.status = "running"
    view.refresh()

    assert view.center_stack.currentIndex() == 0
    assert view._poll_timer.interval() == running_view.SLOW_POLL_MS


def test_error_status_from_polling_surfaces_last_error(view: RunningLabView) -> None:
    view.api.status = "error"
    view.api.last_error = "node 'host' (ubuntu:22.04): could not pull image"

    view.show_lab(_lab("error"))

    assert view.badge.text() == "\u25cf Error"
    assert "could not pull image" in view.message_label.text()
    assert view.start_button.isVisible()


def test_nodes_table_and_open_shell(view: RunningLabView, monkeypatch) -> None:
    launched: list[tuple[str, str, str, str | None]] = []
    monkeypatch.setattr(
        running_view,
        "open_node_shell",
        lambda name, node, os, shell: (
            launched.append((name, node, os, shell)) or ShellLaunchResult(True, "Opened.")
        ),
    )
    view.show_lab(_lab())

    table = view.nodes_table
    assert table.rowCount() == 1
    assert table.item(0, 0).text() == "host"
    assert table.item(0, 1).text() == "10.90.0.10 (lab-net)"  # the address students need
    assert table.item(0, 3).text() == "running"
    button = table.cellWidget(0, 4)
    assert button.isEnabled()
    assert button.text() == "Open shell"
    assert not button.icon().isNull()  # the design terminal icon
    assert "bash or sh" in button.toolTip() and "'host'" in button.toolTip()
    assert "1 container running" in view.containers_label.text()

    button.click()

    assert launched == [("practicum-lab-1-host", "host", "linux", None)]
    assert view.nodes_status_label.text() == "Opened."


def test_windows_node_offers_open_powershell(view: RunningLabView, monkeypatch) -> None:
    launched: list[tuple[str, str, str, str | None]] = []
    monkeypatch.setattr(
        running_view,
        "open_node_shell",
        lambda name, node, os, shell: (
            launched.append((name, node, os, shell))
            or ShellLaunchResult(True, "Opened PowerShell on 'host' in a new window.")
        ),
    )
    view.api.topology_nodes = [
        TopologyNodeInfo(
            "host", "mcr.microsoft.com/windows/servercore:ltsc2022", "windows", "powershell"
        )
    ]
    view.show_lab(_lab())

    button = view.nodes_table.cellWidget(0, 4)
    assert button.text() == "Open PowerShell"
    assert "PowerShell" in button.toolTip() and "'host'" in button.toolTip()
    assert button.accessibleName() == "Open PowerShell on host"

    button.click()

    assert launched == [("practicum-lab-1-host", "host", "windows", "powershell")]
    assert "Opened PowerShell on 'host'" in view.nodes_status_label.text()

    # A stopped Windows node: the button is disabled and says what to do.
    view.api.status = "stopped"
    view.refresh()
    button = view.nodes_table.cellWidget(0, 4)
    assert button.isEnabled() is False
    assert "Start the lab to open PowerShell on 'host'" == button.toolTip()


def test_embedded_view_loads_the_published_port_when_running(view: RunningLabView) -> None:
    view.show_lab(_lab())

    assert view.embedded_view.current_url == "http://localhost:3001/"
    assert view.web.urls[-1] == "http://localhost:3001/"  # after the about:blank reset
    assert view.embedded_view.stack.currentWidget() is view.web


def test_instructions_toggle_hides_flyout_without_losing_progress(view: RunningLabView) -> None:
    view.show_lab(_lab())
    view.manual_flyout.mark_next_step_complete()

    view.instructions_button.setChecked(False)
    assert view.manual_flyout.isHidden()
    view.instructions_button.setChecked(True)

    assert view.manual_flyout.isVisible()
    assert view.manual_flyout.progress() == (1, 2)
    assert view.web.urls.count("http://localhost:3001/") == 1  # the web view was not reloaded


def test_switching_labs_reloads_preview_and_clears_embedded_view(view: RunningLabView) -> None:
    view.show_lab(_lab())
    view.api.port_mappings = []

    view.show_lab(LabSummary(id="lab-2", name="Other", status="running", origin="designer"))

    assert view.api.calls.count("preview") == 2
    assert view.title_label.text() == "Other"
    assert view.meta_label.text() == "Custom lab"
    assert "no browser-accessible ports" in view.embedded_view.message_title.text()


def test_polling_stops_when_hidden(view: RunningLabView) -> None:
    view.show_lab(_lab())
    assert view._poll_timer.isActive()

    view.hide()

    assert not view._poll_timer.isActive()


def test_container_state_text_wording() -> None:
    from practicum_desktop.running_view import container_state_text

    assert (
        container_state_text(ResourceStatusInfo("container", "a", "n", True, "running"))
        == "running"
    )
    assert container_state_text(ResourceStatusInfo("container", "a", "n", False)) == "not created"
    gone = ResourceStatusInfo("container", "a", "n", False, error="Error: No such object: n")
    assert container_state_text(gone) == "not created"
    down = ResourceStatusInfo("container", "a", "n", False, error="Docker CLI could not be run")
    assert container_state_text(down) == "unknown (Docker CLI could not be run)"


def test_package_install_status_is_visible_in_the_nodes_table(view: RunningLabView) -> None:
    """designer-windows-quick-start-packages (and the Ubuntu marker before it): the node's
    self-reported install marker shows as state suffix, tooltip and status line."""
    view.api.note = (
        "Practicum: installing tools (git 7zip) with Chocolatey - this takes several minutes; "
        "re-open PowerShell to check"
    )
    view.show_lab(_lab())

    state = view.nodes_table.item(0, 3)
    assert state.text() == "running \u00b7 installing\u2026"
    assert "Chocolatey" in state.toolTip()
    status_text = view.nodes_status_label.text()
    assert status_text.startswith("host: Practicum: installing tools (git 7zip)")

    view.api.note = (
        "Practicum: tool install FAILED for 7zip - check each package id at "
        "community.chocolatey.org and that the container is online "
        "(see C:\\practicum\\packages.log)"
    )
    view.refresh()
    assert view.nodes_table.item(0, 3).text() == "running \u00b7 install failed"
    assert "FAILED for 7zip" in view.nodes_status_label.text()

    view.api.note = "Practicum: tools ready (git 7zip)"
    view.refresh()
    assert view.nodes_table.item(0, 3).text() == "running"
    assert "tools ready (git 7zip)" in view.nodes_status_label.text()


def test_shell_launch_failure_is_shown_with_the_command_to_copy(
    view: RunningLabView, monkeypatch
) -> None:
    """windows-desktop-open-windows-shell: a stopped/missing container never ends in a silent
    console flash - the in-app status line carries the reason and the docker command."""
    monkeypatch.setattr(
        running_view,
        "open_node_shell",
        lambda name, node, os, shell: ShellLaunchResult(
            False,
            "Cannot open PowerShell on 'host': its container is not running (state: exited). "
            "Start the lab (or Reset it if it is in an error state), wait until the node shows "
            "'running', then try again.",
            ["docker", "exec", "-it", name, "powershell.exe", "-NoLogo"],
        ),
    )
    view.api.topology_nodes = [TopologyNodeInfo("host", "servercore", "windows", "powershell")]
    view.show_lab(_lab())

    view.nodes_table.cellWidget(0, 4).click()

    text = view.nodes_status_label.text()
    assert "Cannot open PowerShell on 'host'" in text
    assert "not running (state: exited)" in text
    assert "docker exec -it practicum-lab-1-host powershell.exe -NoLogo" in text


def test_lifecycle_toolbar_buttons_carry_design_icons(view: RunningLabView) -> None:
    view.show_lab(_lab())

    assert view.start_button.text() == "Start lab" and not view.start_button.icon().isNull()
    assert view.restart_button.text() == "Restart" and not view.restart_button.icon().isNull()
    assert view.stop_button.text() == "Stop lab" and not view.stop_button.icon().isNull()
    assert view.back_button.accessibleName() == "Back to my labs"


def test_two_desktops_are_offered_by_machine_name_in_the_lab_view(view: RunningLabView) -> None:
    view.api.port_mappings = [  # the flat lab-wide list the API also sends
        PortMappingInfo(3000, 3000, "tcp"),
        PortMappingInfo(3001, 3001, "tcp"),
        PortMappingInfo(3002, 3000, "tcp"),
        PortMappingInfo(3003, 3001, "tcp"),
    ]
    view.api.topology_nodes = [
        TopologyNodeInfo(
            "desktop-1",
            "lscr.io/linuxserver/webtop:ubuntu-xfce",
            port_mappings=[
                PortMappingInfo(3000, 3000, "tcp", node_id="desktop-1"),
                PortMappingInfo(3001, 3001, "tcp", node_id="desktop-1"),
            ],
        ),
        TopologyNodeInfo(
            "desktop-2",
            "lscr.io/linuxserver/webtop:ubuntu-xfce",
            port_mappings=[
                PortMappingInfo(3002, 3000, "tcp", node_id="desktop-2"),
                PortMappingInfo(3003, 3001, "tcp", node_id="desktop-2"),
            ],
        ),
    ]
    view.show_lab(_lab())

    picker = view.embedded_view.port_picker
    assert picker.isVisibleTo(view.embedded_view)
    assert picker.itemText(0) == "desktop-1 \u00b7 localhost:3000"
    assert picker.itemText(2) == "desktop-2 \u00b7 localhost:3002"
    assert view.web.urls[-1] == "http://localhost:3000/"

    picker.setCurrentIndex(2)

    assert view.embedded_view.current_url == "http://localhost:3002/"
    assert view.web.urls[-1] == "http://localhost:3002/"


def test_export_results_request_carries_the_results_document(view: RunningLabView) -> None:
    requests: list[tuple[str, dict]] = []
    view.export_results_requested.connect(
        lambda lab_id, results: requests.append((lab_id, results))
    )
    view.show_lab(_lab())
    view.manual_flyout.mark_next_step_complete()

    view.manual_flyout.export_button.click()

    lab_id, results = requests[0]
    assert lab_id == "lab-1"
    assert results["lab"]["name"] == "Build a Python API"
    assert results["lab"]["origin"] == "imported"
    assert results["lab"]["source_file"] == "python-api-lab.json"
    assert results["summary"] == {
        "completed": 1,
        "total": 2,
        "all_complete": False,
        "percent": 50,
        "screenshots_required": 0,
        "screenshots_attached": 0,
        "first_completed_at": results["steps"][0]["tasks"][0]["completed_at"],
        "last_completed_at": results["steps"][0]["tasks"][0]["completed_at"],
    }
    assert [s["title"] for s in results["steps"]] == ["Install", "Run"]
    assert results["student"]["name"] == ""  # the owner asks for it

    view.show_export_note("Results saved to /tmp/x.json", "ok")
    assert "Results saved" in view.message_label.text()


def test_capture_and_upload_attach_screenshots_to_the_requesting_step(
    view: RunningLabView, tmp_path: Path
) -> None:
    view.api.sections = [
        ManualSectionInfo(
            "s1",
            "Show it",
            "Open the desktop",
            [ManualTaskInfo("t1", "Opened")],
            requires_screenshot=True,
        )
    ]
    uploads: list[tuple[str, str]] = []
    view.screenshot_upload_requested.connect(lambda lab, sec: uploads.append((lab, sec)))
    view.show_lab(_lab())
    row = view.manual_flyout._screenshot_rows["s1"]
    assert view.embedded_view.stack.currentWidget() is view.web  # the lab view is showing

    row.capture_button.click()

    shots = view.manual_flyout.screenshots()
    assert len(shots) == 1 and shots[0].source == "lab_view" and shots[0].path.is_file()
    assert view.results()["summary"]["screenshots_attached"] == 1

    row.upload_button.click()
    assert uploads == [("lab-1", "s1")]
    image = tmp_path / "own.png"
    pix = QPixmap(4, 4)
    pix.fill(QColor("black"))
    pix.save(str(image), "PNG")
    assert view.attach_uploaded_screenshot("s1", image) is True
    assert view.manual_flyout.screenshots()[0].source == "upload"

    # a lab without a web page: capture explains, nothing is attached
    view.api.port_mappings = []
    view.api.status = "running"
    view.show_lab(LabSummary("lab-2", "Terminal lab", "running", "quick_start"))
    view.manual_flyout._screenshot_rows["s1"].capture_button.click()
    assert view.manual_flyout.screenshots() == []
    assert "Upload image" in view.manual_flyout._screenshot_rows["s1"].status_label.text()
