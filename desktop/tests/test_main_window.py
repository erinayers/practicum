from __future__ import annotations

import json
from pathlib import Path
from typing import ClassVar

import pytest
from PySide6.QtCore import QObject, QSettings, Signal
from PySide6.QtWidgets import QDialog, QTextBrowser
from qt_helpers import ImmediateWorker

from practicum_desktop import designer, embedded_view, main_window, running_view
from practicum_desktop.api_client import (
    CreateLabResult,
    DeleteResult,
    HealthStatus,
    LabDefinitionResult,
    LabsResult,
    LabSummary,
    PortCheckResult,
    PreviewResult,
    ResourceStatusInfo,
    StartResult,
    StatusResult,
)
from practicum_desktop.app_status import AppStatus
from practicum_desktop.docker_status import DockerStatus
from practicum_desktop.embedded_view import ProbeResult
from practicum_desktop.import_lab import ImportOutcome
from practicum_desktop.main_window import MainWindow
from practicum_desktop.quickstart import QuickStartDraft


def _ready_status() -> AppStatus:
    return AppStatus(
        readiness="ready",
        api=HealthStatus(reachable=True, healthy=True, detail="The Practicum API is healthy."),
        docker=DockerStatus(available=True, detail="Docker is available."),
        next_action="",
    )


def _blocked_status() -> AppStatus:
    return AppStatus(
        readiness="blocked",
        api=HealthStatus(reachable=False, healthy=False, detail="down"),
        docker=DockerStatus(available=True, detail="ok"),
        next_action="Start the API.",
    )


class FakeApiClient:
    """Serves a mutable lab list so tests can make labs appear, start, stop or vanish."""

    def __init__(self) -> None:
        self.labs: list[LabSummary] = []
        self.base_url = "http://127.0.0.1:8000"
        self.deleted: list[str] = []
        self.reset_calls: list[str] = []
        self.created: list[tuple[dict, str]] = []
        self.updated: list[tuple[str, dict]] = []
        self.delete_result = DeleteResult(success=True, detail="Lab deleted.")
        self.reset_result = StartResult(success=True, detail="Lab reset.", lab_status="defined")
        self.create_result = CreateLabResult(success=True, lab_id="qs-1")

    def list_labs(self) -> LabsResult:
        return LabsResult(success=True, labs=list(self.labs))

    def check_ports(self, lab_id: str) -> PortCheckResult:
        return PortCheckResult(success=True, has_conflicts=False)

    def get_preview(self, lab_id: str) -> PreviewResult:
        return PreviewResult(success=True, name=f"Lab {lab_id}")

    def get_status(self, lab_id: str) -> StatusResult:
        lab = next((lab for lab in self.labs if lab.id == lab_id), None)
        running = lab is not None and lab.status == "running"
        return StatusResult(
            success=True,
            lab_status=lab.status if lab else "",
            resources=[
                ResourceStatusInfo(
                    kind="container",
                    id="host-a",
                    name=f"practicum-{lab_id}-host-a",
                    exists=running,
                    status="running" if running else None,
                ),
            ],
        )

    def delete_lab(self, lab_id: str) -> DeleteResult:
        self.deleted.append(lab_id)
        if self.delete_result.success:
            self.labs = [lab for lab in self.labs if lab.id != lab_id]
        return self.delete_result

    def reset_lab(self, lab_id: str) -> StartResult:
        self.reset_calls.append(lab_id)
        for lab in self.labs:
            if lab.id == lab_id and self.reset_result.success:
                lab.status = "defined"
        return self.reset_result

    def create_lab(self, definition: dict, origin: str = "designer") -> CreateLabResult:
        self.created.append((definition, origin))
        return self.create_result

    def get_lab(self, lab_id: str) -> LabDefinitionResult:
        lab = next((lab for lab in self.labs if lab.id == lab_id), None)
        if lab is None:
            return LabDefinitionResult(success=False, detail="That lab is no longer in the list.")
        return LabDefinitionResult(
            success=True,
            name=lab.name,
            status=lab.status,
            definition={
                "id": lab.id,
                "status": lab.status,
                "name": lab.name,
                "nodes": [{"id": "host", "image": "alpine:3.21"}],
                "networks": [{"id": "lan", "subnet": "10.0.1.0/24"}],
                "interfaces": [{"node": "host", "network": "lan", "address": "10.0.1.10/24"}],
            },
        )

    def export_lab(self, lab_id: str) -> LabDefinitionResult:
        result = self.get_lab(lab_id)
        if result.success:
            result.definition = {
                k: v for k, v in result.definition.items() if k not in ("id", "status")
            }
        return result

    def update_lab(self, lab_id: str, definition: dict) -> CreateLabResult:
        self.updated.append((lab_id, definition))
        return CreateLabResult(success=True, lab_id=lab_id)


class FakeStartupWorker(QObject):
    finished_check = Signal(object, object)
    status_to_return: ClassVar[AppStatus] = _ready_status()

    def __init__(self, api_client, parent=None) -> None:
        super().__init__()
        self._api_client = api_client

    def start(self) -> None:
        status = FakeStartupWorker.status_to_return
        labs = self._api_client.list_labs() if status.readiness != "blocked" else None
        self.finished_check.emit(status, labs)


class FakeImportDialog:
    outcome_to_return: ImportOutcome | None = None
    last_kwargs: ClassVar[dict] = {}

    def __init__(self, api_client, settings, parent=None, api_available=True) -> None:
        FakeImportDialog.last_kwargs = {"api_available": api_available}
        self.outcome = FakeImportDialog.outcome_to_return

    def exec(self) -> int:
        return int(QDialog.DialogCode.Accepted if self.outcome else QDialog.DialogCode.Rejected)


class FakeGateDialog:
    result_to_return = QDialog.DialogCode.Accepted
    opened_for: ClassVar[list[str]] = []
    DialogCode = QDialog.DialogCode
    api: ClassVar[FakeApiClient | None] = None

    def __init__(self, api_client, lab_id, parent=None) -> None:
        FakeGateDialog.opened_for.append(lab_id)
        self._lab_id = lab_id

    def exec(self) -> int:
        if FakeGateDialog.result_to_return == QDialog.DialogCode.Accepted and FakeGateDialog.api:
            for lab in FakeGateDialog.api.labs:
                if lab.id == self._lab_id:
                    lab.status = "running"  # the gate started it
        return int(FakeGateDialog.result_to_return)


class FakeWebView(QTextBrowser):
    def setUrl(self, url) -> None:
        self.setPlainText(url.toString())

    def reload(self) -> None:
        pass


@pytest.fixture
def window(monkeypatch, tmp_path: Path):
    api = FakeApiClient()
    monkeypatch.setattr(main_window, "ApiClient", lambda base_url: api)
    monkeypatch.setattr(
        main_window,
        "QSettings",
        lambda org, app: QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat),
    )
    monkeypatch.setattr(main_window, "StartupWorker", FakeStartupWorker)
    monkeypatch.setattr(main_window, "CallableWorker", ImmediateWorker)
    monkeypatch.setattr(running_view, "CallableWorker", ImmediateWorker)
    monkeypatch.setattr(embedded_view, "CallableWorker", ImmediateWorker)
    monkeypatch.setattr(designer, "CallableWorker", ImmediateWorker)
    monkeypatch.setattr(main_window, "ImportLabDialog", FakeImportDialog)
    monkeypatch.setattr(main_window, "PreStartGateDialog", FakeGateDialog)
    monkeypatch.setattr(main_window, "confirm", lambda *args, **kwargs: True)
    FakeImportDialog.outcome_to_return = None
    FakeGateDialog.opened_for = []
    FakeGateDialog.result_to_return = QDialog.DialogCode.Accepted
    FakeGateDialog.api = api
    FakeStartupWorker.status_to_return = _ready_status()

    win = MainWindow(web_view_factory=lambda parent: FakeWebView())
    win.running_view.embedded_view._probe = lambda port: ProbeResult(False, detail="n/a")
    win.api = api
    win.show()
    yield win
    # Stop the running view's poll timer before the monkeypatched worker is restored, or a
    # late tick would spin up a real QThread against the fake client.
    win.running_view.clear()
    win.close()
    win.deleteLater()


def _lab_added(window: MainWindow, lab_id: str, name: str, status: str = "running") -> None:
    window.api.labs.append(LabSummary(id=lab_id, name=name, status=status))


# ----- home: welcome vs dashboard ------------------------------------------------------------


def test_zero_labs_shows_the_welcome_screen(window: MainWindow) -> None:
    assert window.current_screen == "welcome"
    assert window.welcome.dashboard_link.isHidden()
    assert window.status_chip.text() == "\u25cf Ready"


def test_existing_labs_show_the_dashboard_with_their_status(window: MainWindow) -> None:
    _lab_added(window, "a", "Routing", status="running")
    _lab_added(window, "b", "Quick", status="defined")

    window.check_status()

    assert window.current_screen == "dashboard"
    cards = window.dashboard.cards
    assert [(c.lab.name, c.badge.text()) for c in cards] == [
        ("Routing", "\u25cf Running"),
        ("Quick", "\u25cf Ready"),
    ]
    assert window.welcome.dashboard_link.text().startswith("You have 2 labs")


def test_blocked_api_falls_back_to_welcome_with_details_open(window: MainWindow) -> None:
    _lab_added(window, "a", "Routing")
    FakeStartupWorker.status_to_return = _blocked_status()

    window.check_status()

    assert window.current_screen == "welcome"
    assert window.welcome.blocked_banner.isHidden() is False
    assert not window.welcome.create_button.isEnabled()
    assert window.connection_panel.isHidden() is False
    assert window.status_chip.text() == "\u25cf API unreachable"
    assert "Start the API." in window.next_action_label.text()


def test_status_refresh_never_leaves_a_non_home_screen(window: MainWindow) -> None:
    window.show_designer()
    _lab_added(window, "a", "Routing")

    window.check_status()

    assert window.current_screen == "designer"
    assert len(window.dashboard.cards) == 1  # but the cache was refreshed


def test_welcome_link_and_back_links_navigate(window: MainWindow) -> None:
    _lab_added(window, "a", "Routing")
    window.check_status()
    window.show_welcome()

    window.welcome.dashboard_link.click()
    assert window.current_screen == "dashboard"
    window.dashboard.create_button.click()
    assert window.current_screen == "create"
    window.create_screen.quick_card.button.click()
    assert window.current_screen == "quickstart"
    window.quick_start_screen.back_button.click()
    assert window.current_screen == "create"
    window.create_screen.custom_card.button.click()
    assert window.current_screen == "designer"
    window.designer.cancel_button.click()
    assert window.current_screen == "dashboard"


def test_retry_updates_the_api_url_and_rechecks(window: MainWindow) -> None:
    window.base_url_field.setText("http://127.0.0.1:9000/")

    window.retry_button.click()

    assert window.api.base_url == "http://127.0.0.1:9000"
    assert window._settings.value("api_base_url") == "http://127.0.0.1:9000/"


# ----- dashboard card actions -------------------------------------------------------------------


def test_open_running_lab_goes_to_running_view_without_a_start_call(window: MainWindow) -> None:
    _lab_added(window, "a", "Routing", status="running")
    window.check_status()

    window.dashboard.card_for("a").buttons["Open"].click()

    assert window.current_screen == "running"
    assert window.running_view.lab_id == "a"
    assert window.running_view.title_label.text() == "Routing"
    assert FakeGateDialog.opened_for == []


def test_start_stopped_lab_goes_through_the_gate_then_opens_it(window: MainWindow) -> None:
    _lab_added(window, "a", "Routing", status="stopped")
    window.check_status()

    window.dashboard.card_for("a").buttons["Start"].click()

    assert FakeGateDialog.opened_for == ["a"]
    assert window.current_screen == "running"
    assert window.running_view.lab_id == "a"


def test_cancelled_gate_stays_on_the_dashboard(window: MainWindow) -> None:
    _lab_added(window, "a", "Routing", status="stopped")
    window.check_status()
    FakeGateDialog.result_to_return = QDialog.DialogCode.Rejected

    window.dashboard.card_for("a").buttons["Start"].click()

    assert FakeGateDialog.opened_for == ["a"]
    assert window.current_screen == "dashboard"
    assert window.dashboard.card_for("a").badge.text() == "\u25cf Stopped"


def test_delete_asks_in_app_and_removes_the_card(window: MainWindow, monkeypatch) -> None:
    prompts: list[dict] = []
    monkeypatch.setattr(
        main_window, "confirm", lambda *args, **kwargs: prompts.append(kwargs) or True
    )
    _lab_added(window, "a", "Routing", status="stopped")
    _lab_added(window, "b", "Other", status="defined")
    window.check_status()

    window.dashboard.card_for("a").buttons["Delete"].click()

    assert prompts[0]["title"] == 'Delete "Routing"?'
    assert prompts[0]["destructive"] is True
    assert window.api.deleted == ["a"]
    assert [c.lab.id for c in window.dashboard.cards] == ["b"]
    assert "Deleted 'Routing'." in window.dashboard.message_label.text()
    assert "removed from Docker" in window.dashboard.message_label.text()


def test_cancelled_delete_leaves_the_list_unchanged(window: MainWindow, monkeypatch) -> None:
    monkeypatch.setattr(main_window, "confirm", lambda *args, **kwargs: False)
    _lab_added(window, "a", "Routing", status="stopped")
    window.check_status()

    window.dashboard.card_for("a").buttons["Delete"].click()

    assert window.api.deleted == []
    assert [c.lab.id for c in window.dashboard.cards] == ["a"]


def test_failed_delete_keeps_the_card_and_explains(window: MainWindow) -> None:
    _lab_added(window, "a", "Routing", status="stopped")
    window.check_status()
    window.api.delete_result = DeleteResult(
        success=False, detail="Could not remove the lab's Docker resources: boom"
    )

    window.dashboard.card_for("a").buttons["Delete"].click()

    assert [c.lab.id for c in window.dashboard.cards] == ["a"]
    assert "boom" in window.dashboard.message_label.text()


def test_reset_from_an_error_card_confirms_then_resets(window: MainWindow, monkeypatch) -> None:
    prompts: list[dict] = []
    monkeypatch.setattr(
        main_window, "confirm", lambda *args, **kwargs: prompts.append(kwargs) or True
    )
    _lab_added(window, "a", "Routing", status="error")
    window.check_status()

    window.dashboard.card_for("a").buttons["Reset"].click()

    assert prompts[0]["destructive"] is True
    assert window.api.reset_calls == ["a"]
    assert window.dashboard.card_for("a").badge.text() == "\u25cf Ready"


def test_deleting_the_last_lab_returns_to_welcome_with_a_dismissible_note(
    window: MainWindow,
) -> None:
    _lab_added(window, "a", "Routing", status="stopped")
    window.check_status()

    window.dashboard.card_for("a").buttons["Delete"].click()

    assert window.current_screen == "welcome"
    note = window.welcome.note
    assert note.isHidden() is False
    assert "Deleted 'Routing'." in note.text()
    assert "no labs left" in note.text()
    assert note.kind == "ok"
    note.close_button.click()
    assert note.isHidden() is True
    assert window.welcome.note_label.isHidden() is True


# ----- import ------------------------------------------------------------------------------------


def test_cancelled_import_changes_nothing(window: MainWindow) -> None:
    FakeImportDialog.outcome_to_return = None

    window.welcome.import_button.click()

    assert window.current_screen == "welcome"
    assert FakeGateDialog.opened_for == []


def test_started_import_lands_in_the_running_view(window: MainWindow, tmp_path: Path) -> None:
    FakeImportDialog.outcome_to_return = ImportOutcome(
        lab_id="lab-9", lab_name="Static Routing", source_path=tmp_path / "s.json", started=True
    )
    _lab_added(window, "lab-9", "Static Routing")

    window.welcome.import_button.click()

    assert FakeGateDialog.opened_for == []
    assert window.current_screen == "running"
    assert window.running_view.lab_id == "lab-9"
    assert FakeImportDialog.last_kwargs == {"api_available": True}


def test_import_with_conflicts_opens_gate_and_then_the_lab(
    window: MainWindow, tmp_path: Path
) -> None:
    FakeImportDialog.outcome_to_return = ImportOutcome(
        lab_id="lab-2", lab_name="Web Lab", source_path=tmp_path / "w.json", gate_required=True
    )
    _lab_added(window, "lab-2", "Web Lab", status="defined")

    window.welcome.import_button.click()

    assert FakeGateDialog.opened_for == ["lab-2"]
    assert window.current_screen == "running"


def test_import_cancelled_at_gate_shows_the_lab_on_the_dashboard(
    window: MainWindow, tmp_path: Path
) -> None:
    FakeImportDialog.outcome_to_return = ImportOutcome(
        lab_id="lab-2", lab_name="Web Lab", source_path=tmp_path / "w.json", gate_required=True
    )
    FakeGateDialog.result_to_return = QDialog.DialogCode.Rejected
    _lab_added(window, "lab-2", "Web Lab", status="defined")

    window.welcome.import_button.click()

    assert window.current_screen == "dashboard"
    assert window.dashboard.card_for("lab-2") is not None
    assert "'Web Lab' imported." in window.dashboard.message_label.text()


def test_import_dialog_is_told_when_api_is_unavailable(window: MainWindow) -> None:
    FakeStartupWorker.status_to_return = _blocked_status()
    window.check_status()
    window.welcome.set_blocked(None)  # re-enable the button just for the click

    window.welcome.import_button.click()

    assert FakeImportDialog.last_kwargs == {"api_available": False}


# ----- quick start / designer --------------------------------------------------------------


def test_quick_start_create_saves_then_gates_then_opens(window: MainWindow) -> None:
    window.show_quick_start("ubuntu")
    window.api.labs.append(LabSummary("qs-1", "Ubuntu Quick Start", "defined", "quick_start"))

    window.quick_start_screen.create_requested.emit(QuickStartDraft(name="Ubuntu Quick Start"))

    assert window.api.created[0][1] == "quick_start"
    assert FakeGateDialog.opened_for == ["qs-1"]
    assert window.current_screen == "running"
    assert window.running_view.lab_id == "qs-1"


def test_quick_start_create_failure_stays_on_the_form(window: MainWindow) -> None:
    window.show_quick_start("ubuntu")
    window.api.create_result = CreateLabResult(success=False, detail="The lab is invalid.")

    window.quick_start_screen.create_requested.emit(QuickStartDraft(name="x"))

    assert window.current_screen == "quickstart"
    assert "The lab is invalid." in window.quick_start_screen.status_pill.text_label.text()
    assert window.quick_start_screen.create_button.isEnabled()


def test_designer_save_returns_to_dashboard_and_save_and_start_gates(window: MainWindow) -> None:
    window.show_designer()
    window.api.labs.append(LabSummary("lab-new", "Custom", "defined", "designer"))

    window.designer.saved.emit("lab-new", False)
    assert window.current_screen == "dashboard"
    assert "Lab saved." in window.dashboard.message_label.text()
    assert FakeGateDialog.opened_for == []

    window.show_designer()
    window.designer.saved.emit("lab-new", True)
    assert FakeGateDialog.opened_for == ["lab-new"]
    assert window.current_screen == "running"


# ----- running view round trips ----------------------------------------------------------------


def test_running_view_start_request_goes_through_the_gate(window: MainWindow) -> None:
    _lab_added(window, "a", "Routing", status="stopped")
    window.check_status()
    window.open_lab("a")

    window.running_view.start_button.click()

    assert FakeGateDialog.opened_for == ["a"]
    assert window.running_view.badge.text() == "\u25cf Running"


def test_back_from_running_view_refreshes_the_dashboard(window: MainWindow) -> None:
    _lab_added(window, "a", "Routing", status="running")
    window.check_status()
    window.open_lab("a")
    window.api.labs[0].status = "stopped"

    window.running_view.back_button.click()

    assert window.current_screen == "dashboard"
    assert window.dashboard.card_for("a").badge.text() == "\u25cf Stopped"


# ----- edit / export -----------------------------------------------------------------------------


def test_edit_loads_the_lab_into_the_designer_and_saves_with_put(window: MainWindow) -> None:
    _lab_added(window, "a", "Routing", status="stopped")
    window.check_status()

    window.dashboard.card_for("a").buttons["Edit"].click()

    assert window.current_screen == "designer"
    assert window.designer.editing_lab_id == "a"
    assert window.designer.name_field.text() == "Routing"
    assert [n["id"] for n in window.designer.nodes] == ["host"]

    window.designer.save_button.click()

    assert window.api.updated[0][0] == "a"
    assert window.api.created == []
    assert window.current_screen == "dashboard"
    assert "Lab saved." in window.dashboard.message_label.text()


def test_edit_is_refused_for_a_running_lab(window: MainWindow) -> None:
    _lab_added(window, "a", "Routing", status="running")
    window.check_status()

    window._on_edit_requested("a")

    assert window.current_screen == "dashboard"
    assert "Stop 'Routing' before editing" in window.dashboard.message_label.text()


def test_export_writes_the_portable_spec_where_the_user_chooses(
    window: MainWindow, monkeypatch, tmp_path: Path
) -> None:
    _lab_added(window, "a", "Static Routing Fundamentals", status="stopped")
    window.check_status()
    asked: list[Path] = []
    target = tmp_path / "out" / "my-lab.json"
    target.parent.mkdir()

    def fake_ask(parent, suggested: Path) -> Path:
        asked.append(suggested)
        return target

    monkeypatch.setattr(main_window, "ask_save_path", fake_ask)

    window.dashboard.card_for("a").buttons["Export"].click()

    assert asked[0].name == "static-routing-fundamentals.json"
    exported = json.loads(target.read_text(encoding="utf-8"))
    assert exported["name"] == "Static Routing Fundamentals"
    assert "id" not in exported and "status" not in exported
    assert str(target) in window.dashboard.message_label.text()


def test_export_cancelled_in_the_picker_writes_nothing(window: MainWindow, monkeypatch) -> None:
    _lab_added(window, "a", "Routing", status="running")
    window.check_status()
    monkeypatch.setattr(main_window, "ask_save_path", lambda parent, suggested: None)

    window.dashboard.card_for("a").buttons["Export"].click()

    assert window.dashboard.message_label.isHidden()
