"""Application shell (windows-desktop-launch, windows-desktop-local-api,
windows-desktop-labs-dashboard, and the navigation between every other screen).

`MainWindow` is the mockup's `.window`: a title bar with the brand and a connection status
chip, then one of the screens in a `QStackedWidget`:

    welcome     zero labs (or API blocked) - Create / Import / "view your labs dashboard"
    dashboard   lab cards - Open / Start / Delete / Reset, Import, + Create New Lab
    create      Quick start vs Custom Lab chooser
    quickstart  Quick start configuration
    designer    Custom Lab designer
    running     the running-lab view (lifecycle toolbar, embedded view, instructions)

The window owns every API call the screens ask for (they only emit signals), routes every
Start through `PreStartGateDialog` (D-4), confirms destructive actions with
`dialogs.confirm()` (D-3) and keeps a cached lab list that the dashboard renders.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import QSettings, QStandardPaths, Qt, QTimer
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from practicum_desktop import icons, theme
from practicum_desktop.api_client import (
    DEFAULT_BASE_URL,
    ApiClient,
    CreateLabResult,
    DeleteResult,
    LabDefinitionResult,
    LabsResult,
    LabSummary,
    StartResult,
)
from practicum_desktop.app_status import AppStatus, evaluate_app_status
from practicum_desktop.create_lab import CreateLabScreen, QuickStartScreen
from practicum_desktop.dashboard import DashboardScreen, WelcomeScreen
from practicum_desktop.designer import DesignerView
from practicum_desktop.dialogs import ResultsExportDialog, confirm
from practicum_desktop.docker_status import (
    DockerStatus,
    check_docker,
    windows_container_readiness,
)
from practicum_desktop.embedded_view import default_web_view_factory
from practicum_desktop.import_lab import ImportLabDialog
from practicum_desktop.lab_results import RESULTS_FILTER, results_file_name, write_results
from practicum_desktop.prestart_gate import PreStartGateDialog
from practicum_desktop.quickstart import QuickStartDraft, create_quick_start_lab
from practicum_desktop.running_view import RunningLabView
from practicum_desktop.screenshots import IMAGE_FILTER
from practicum_desktop.startup import StartupWorker
from practicum_desktop.widgets import copyable_label, make_button, role_label, style_frame
from practicum_desktop.workers import CallableWorker, ManagedThread

ORG_NAME = "Practicum"
APP_NAME = "Practicum Desktop"

READINESS_LABELS = {
    "ready": "Ready",
    "degraded": "Degraded",
    "blocked": "Blocked",
}
READINESS_CHIP = {
    "ready": ("Ready", theme.GREEN),
    "degraded": ("Docker unavailable", theme.AMBER),
    "blocked": ("API unreachable", theme.DANGER),
}
READINESS_ICON = {"ready": "success", "degraded": "warning", "blocked": "error"}
API_BLOCKED_MESSAGE = (
    "Practicum can't reach its local API, so your labs can't be loaded yet. "
    "Open the connection panel (top right) for details and Retry."
)
# Home screens: the ones a status refresh may switch between (never yank the user out of
# the designer or a running lab).
HOME_SCREENS = ("welcome", "dashboard")
EXPORT_FILTER = "Practicum lab files (*.json);;All files (*)"


def export_file_name(lab_name: str) -> str:
    """'Static Routing Fundamentals' → 'static-routing-fundamentals.json'."""
    slug = re.sub(r"[^a-z0-9]+", "-", lab_name.lower()).strip("-") or "lab"
    return f"{slug}.json"


def ask_image_path(parent: QWidget) -> Path | None:
    """The system open-file picker for a student's own screenshot (the third and last
    sanctioned native dialog: open lab file, save file, open image)."""
    pictures = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.PicturesLocation)
    path, _selected = QFileDialog.getOpenFileName(
        parent, "Upload a screenshot", pictures or str(Path.home()), IMAGE_FILTER
    )
    return Path(path) if path else None


def ask_save_path(
    parent: QWidget, suggested: Path, name_filter: str = EXPORT_FILTER, title: str = "Export Lab"
) -> Path | None:
    """The system save-file picker - with the open-file picker, the only native dialogs the app
    uses (windows-desktop-in-app-dialogs)."""
    path, _selected = QFileDialog.getSaveFileName(parent, title, str(suggested), name_filter)
    return Path(path) if path else None


class MainWindow(QMainWindow):
    def __init__(
        self,
        web_view_factory: Callable = default_web_view_factory,
        screenshot_dir: Path | None = None,
    ) -> None:
        super().__init__()
        self.setWindowTitle("Practicum")
        self.resize(1200, 760)
        self.setMinimumSize(960, 620)

        self._settings = QSettings(ORG_NAME, APP_NAME)
        base_url = self._settings.value("api_base_url", DEFAULT_BASE_URL)
        self._api_client = ApiClient(base_url=base_url)
        self._worker: StartupWorker | None = None
        self._workers: list[CallableWorker] = []
        self._labs: list[LabSummary] = []
        self._last_status: AppStatus | None = None
        self._first_load_done = False
        # (lab_id, message, open_running) to apply once the next lab-list refresh lands.
        self._pending_selection: tuple[str, str, bool] | None = None
        self._web_view_factory = web_view_factory
        self._screenshot_dir = screenshot_dir

        self._build_ui(base_url)
        self.check_status()

    # ----- UI --------------------------------------------------------------------------

    def _build_ui(self, base_url: str) -> None:
        central = QWidget()
        central.setObjectName("screen")
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # title bar ------------------------------------------------------------------
        titlebar = QFrame()
        titlebar.setObjectName("titlebar")
        titlebar.setFixedHeight(46)
        title_row = QHBoxLayout(titlebar)
        title_row.setContentsMargins(14, 0, 14, 0)
        title_row.setSpacing(8)
        brand_badge = QLabel("PR")
        brand_badge.setObjectName("brandBadge")
        brand_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_row.addWidget(brand_badge)
        brand_name = QLabel("practicum")
        brand_name.setObjectName("brandName")
        title_row.addWidget(brand_name)
        title_row.addStretch(1)
        self.status_chip = make_button("\u25cf Checking\u2026", kind="ghost", small=True)
        self.status_chip.setCheckable(True)
        self.status_chip.setToolTip("Connection to the local Practicum API and Docker")
        self.status_chip.setAccessibleName("Connection status")
        self.status_chip.toggled.connect(self._on_status_chip_toggled)
        title_row.addWidget(self.status_chip)
        layout.addWidget(titlebar)

        # connection panel (collapsible) ---------------------------------------------------
        self.connection_panel = QFrame()
        style_frame(
            self.connection_panel, f"background: #f8fafc; border-bottom: 1px solid {theme.LINE};"
        )
        panel_layout = QVBoxLayout(self.connection_panel)
        panel_layout.setContentsMargins(20, 10, 20, 10)
        panel_layout.setSpacing(4)
        self.readiness_label = role_label("Checking Practicum status\u2026", "label")
        panel_layout.addWidget(self.readiness_label)
        self.api_status_label = role_label("Practicum API: checking\u2026", "muted")
        panel_layout.addWidget(self.api_status_label)
        self.docker_status_label = role_label("Docker: checking\u2026", "muted")
        panel_layout.addWidget(self.docker_status_label)
        self.next_action_label = copyable_label("", role="muted")
        panel_layout.addWidget(self.next_action_label)
        url_row = QHBoxLayout()
        url_row.setSpacing(8)
        url_row.addWidget(role_label("API base URL", "label"))
        self.base_url_field = QLineEdit(base_url)
        self.base_url_field.setMaximumWidth(360)
        url_row.addWidget(self.base_url_field)
        self.retry_button = make_button("Retry", small=True)
        self.retry_button.clicked.connect(self._on_retry_clicked)
        url_row.addWidget(self.retry_button)
        url_row.addStretch(1)
        panel_layout.addLayout(url_row)
        self.connection_panel.hide()
        layout.addWidget(self.connection_panel)

        # screens ------------------------------------------------------------------------
        self.stack = QStackedWidget()
        layout.addWidget(self.stack, 1)

        self.welcome = WelcomeScreen()
        self.welcome.create_requested.connect(self.show_create)
        self.welcome.import_requested.connect(self._on_import_clicked)
        self.welcome.dashboard_requested.connect(self.show_dashboard)

        self.dashboard = DashboardScreen()
        self.dashboard.create_requested.connect(self.show_create)
        self.dashboard.import_requested.connect(self._on_import_clicked)
        self.dashboard.open_requested.connect(self.open_lab)
        self.dashboard.start_requested.connect(self._on_start_requested)
        self.dashboard.delete_requested.connect(self._on_delete_requested)
        self.dashboard.reset_requested.connect(self._on_reset_requested)
        self.dashboard.edit_requested.connect(self._on_edit_requested)
        self.dashboard.export_requested.connect(self._on_export_requested)

        self.create_screen = CreateLabScreen()
        self.create_screen.back_requested.connect(self.show_home)
        self.create_screen.quick_start_requested.connect(self.show_quick_start)
        self.create_screen.custom_requested.connect(self.show_designer)
        self.create_screen.readiness_retry_requested.connect(self.refresh_engine)

        self.quick_start_screen = QuickStartScreen()
        self.quick_start_screen.back_requested.connect(self.show_create)
        self.quick_start_screen.change_template_requested.connect(self.show_create)
        self.quick_start_screen.cancel_requested.connect(self.show_home)
        self.quick_start_screen.create_requested.connect(self._on_quick_start_create)

        self.designer = DesignerView(self._api_client)
        self.designer.back_requested.connect(self.show_create)
        self.designer.cancel_requested.connect(self.show_home)
        self.designer.saved.connect(self._on_designer_saved)

        self.running_view = RunningLabView(
            self._api_client,
            self._settings,
            web_view_factory=self._web_view_factory,
            screenshot_dir=self._screenshot_dir,
        )
        self.running_view.back_requested.connect(self.show_home)
        self.running_view.start_requested.connect(self._on_running_start_requested)
        self.running_view.lab_changed.connect(self._on_running_lab_changed)
        self.running_view.export_results_requested.connect(self._on_export_results_requested)
        self.running_view.screenshot_upload_requested.connect(self._on_screenshot_upload_requested)

        self._screens = {
            "welcome": self.welcome,
            "dashboard": self.dashboard,
            "create": self.create_screen,
            "quickstart": self.quick_start_screen,
            "designer": self.designer,
            "running": self.running_view,
        }
        for screen in self._screens.values():
            self.stack.addWidget(screen)
        self.stack.setCurrentWidget(self.welcome)

        self.setCentralWidget(central)

    # ----- navigation --------------------------------------------------------------------

    @property
    def current_screen(self) -> str:
        widget = self.stack.currentWidget()
        return next((name for name, screen in self._screens.items() if screen is widget), "")

    def show_screen(self, name: str) -> None:
        self.stack.setCurrentWidget(self._screens[name])

    def show_home(self) -> None:
        """Welcome when there are no labs (or the API is unreachable), else the dashboard."""
        self._notify("")
        if self._labs and self._api_available:
            self.show_dashboard()
        else:
            self.show_welcome()
            self.refresh_labs()

    def show_welcome(self) -> None:
        self.show_screen("welcome")

    def show_dashboard(self) -> None:
        self._notify("")
        self.show_screen("dashboard")
        self.refresh_labs()

    def _notify(self, text: str, banner: str = "info") -> None:
        """Shows a transient note on whichever home screen is (or will be) visible."""
        self.dashboard.show_message(text, banner)
        self.welcome.show_note(text, banner)

    def show_create(self) -> None:
        # Hand the create screen the engine mode we know, then refresh it: the user may have
        # switched Docker Desktop's mode since the last check.
        docker = self._last_status.docker if self._last_status is not None else None
        self.create_screen.set_docker_status(docker)
        self.show_screen("create")
        self.refresh_engine()

    def show_quick_start(self, template_key: str = "ubuntu") -> None:
        option = self.create_screen.template_option(template_key)
        if not option.available:
            # Defensive: the create screen disables the CTA, but a stale signal must never
            # open a Windows draft while the engine cannot run it.
            self.show_create()
            return
        self.quick_start_screen.reset(template_key)
        docker = self.create_screen.docker_status
        self.quick_start_screen.set_windows_host_build(
            docker.host_build if docker is not None else None
        )
        self.show_screen("quickstart")

    def show_designer(self) -> None:
        self.designer.reset()
        self.show_screen("designer")

    def open_lab(self, lab_id: str) -> None:
        """Shows the running view for `lab_id` (no Start call; the view reads live status)."""
        lab = self.lab_summary(lab_id)
        if lab is None:
            self.dashboard.show_message("That lab is no longer in the list.", "warn")
            return
        self.running_view.show_lab(lab)
        self.show_screen("running")

    def lab_summary(self, lab_id: str) -> LabSummary | None:
        return next((lab for lab in self._labs if lab.id == lab_id), None)

    @property
    def _api_available(self) -> bool:
        return self._last_status is None or self._last_status.readiness != "blocked"

    # ----- status / labs ---------------------------------------------------------------------

    def _on_status_chip_toggled(self, checked: bool) -> None:
        self.connection_panel.setVisible(checked)

    def _on_retry_clicked(self) -> None:
        new_base_url = self.base_url_field.text().strip() or DEFAULT_BASE_URL
        self._settings.setValue("api_base_url", new_base_url)
        self._api_client.base_url = new_base_url.rstrip("/")
        self.check_status()

    def check_status(self) -> None:
        self.retry_button.setEnabled(False)
        self.readiness_label.setText("Checking Practicum status\u2026")
        self.api_status_label.setText("Practicum API: checking\u2026")
        self.docker_status_label.setText("Docker: checking\u2026")
        self.next_action_label.setText("")
        self._set_status_chip("Checking\u2026", theme.MUTED_2)

        self._worker = StartupWorker(self._api_client)
        self._worker.finished_check.connect(self._on_status_checked)
        self._worker.start()

    def _set_status_chip(self, text: str, colour: str, icon_name: str | None = None) -> None:
        if icon_name is not None and icons.icon_available(icon_name):
            self.status_chip.setText(text)
            icons.set_button_icon(self.status_chip, icon_name, 13)
        else:
            self.status_chip.setText(f"\u25cf {text}")
            self.status_chip.setIcon(QIcon())
        self.status_chip.setStyleSheet(
            f"QPushButton {{ color: {colour}; font-weight: 600; }}"
            f"QPushButton:checked {{ background: {theme.LINE_SOFT}; }}"
        )

    @staticmethod
    def _set_check_line(label: QLabel, subject: str, ok: bool, detail: str) -> None:
        state = "OK" if ok else "Problem"
        colour = theme.GREEN if ok else theme.DANGER
        # Words + colour + the design icon: none of them carries the meaning alone.
        mark = icons.icon_html("success" if ok else "error", 13)
        label.setText(
            f'{mark} {subject}: <span style="color:{colour}; font-weight:600;">{state}</span> '
            f'<span style="color:{theme.MUTED};">\u2014 {detail}</span>'
        )

    def _on_status_checked(self, status: AppStatus, labs_result: LabsResult | None) -> None:
        self._apply_status(status)
        blocked = status.readiness == "blocked"
        self.welcome.set_blocked(API_BLOCKED_MESSAGE if blocked else None)
        self.dashboard.set_actions_enabled(not blocked)
        if blocked:
            self.status_chip.setChecked(True)  # show the details without being asked
            self._labs = []
            self.welcome.set_lab_count(0)
            if self.current_screen in HOME_SCREENS:
                self.show_welcome()
            self._pending_selection = None
            return

        if labs_result is not None:
            self._on_labs_loaded(labs_result)

    def _apply_status(self, status: AppStatus) -> None:
        """Renders an API + Docker status everywhere it shows: the connection panel, the
        title-bar chip, the running view's Docker light and the create screen's templates."""
        self._last_status = status
        self.retry_button.setEnabled(True)
        self.readiness_label.setText(f"Status: {READINESS_LABELS[status.readiness]}")
        self._set_check_line(
            self.api_status_label, "Practicum API", status.api.healthy, status.api.detail
        )
        self._set_check_line(
            self.docker_status_label, "Docker", status.docker.available, status.docker.detail
        )
        self.next_action_label.setText(status.next_action)
        chip_text, chip_colour = READINESS_CHIP[status.readiness]
        if status.readiness == "ready" and status.docker.os_type == "windows":
            chip_text = "Ready \u00b7 Windows containers"
        self._set_status_chip(chip_text, chip_colour, READINESS_ICON[status.readiness])
        self.running_view.set_docker_available(status.docker.available)
        self.create_screen.set_docker_status(status.docker)

    def refresh_engine(self) -> None:
        """Re-probes Docker only (read-only `docker info`): what the create screen's Retry
        and every visit to it run, so switching Docker Desktop's engine mode shows up without
        restarting Practicum or re-checking the API."""
        if self._last_status is None:
            return  # the startup check is still running; it will report everything
        self.create_screen.set_checking()
        self._run(check_docker, on_done=self._on_engine_checked)

    def _on_engine_checked(self, docker: DockerStatus) -> None:
        if self._last_status is None:
            return
        self._apply_status(evaluate_app_status(self._last_status.api, docker))

    def refresh_labs(self) -> None:
        if not self._api_available:
            return
        self._run(self._api_client.list_labs, on_done=self._on_labs_loaded)

    def _on_labs_loaded(self, result: LabsResult) -> None:
        if not result.success:
            self.dashboard.show_message(result.detail, "error")
            return
        self._labs = list(result.labs)
        self.welcome.set_lab_count(len(self._labs))
        self.dashboard.set_labs(self._labs)

        if self.current_screen in HOME_SCREENS and (
            not self._first_load_done or self.current_screen == "welcome" or not self._labs
        ):
            self.show_screen("dashboard" if self._labs else "welcome")
        self._first_load_done = True

        pending, self._pending_selection = self._pending_selection, None
        if pending is not None:
            self._apply_pending_selection(*pending)

    def _apply_pending_selection(self, lab_id: str, message: str, open_running: bool) -> None:
        """Lands on a just-created/imported lab: the running view when it started, else the
        dashboard with a note."""
        if self.lab_summary(lab_id) is None:
            self.show_home()
            return
        if open_running:
            self.open_lab(lab_id)
            return
        self.show_screen("dashboard" if self._labs else "welcome")
        self._notify(message, "info")

    def _run(self, func, *args, on_done, **kwargs) -> None:
        worker = CallableWorker(func, *args, **kwargs)
        worker.finished_call.connect(on_done)
        self._workers.append(worker)
        if len(self._workers) > 32:
            self._workers = [w for w in self._workers if w.isRunning()] + [worker]
        worker.start()

    # ----- import ------------------------------------------------------------------------

    def _on_import_clicked(self) -> None:
        dialog = ImportLabDialog(
            self._api_client, self._settings, parent=self, api_available=self._api_available
        )
        dialog.exec()
        outcome = dialog.outcome
        if outcome is None:
            return  # cancelled, or the file never became a lab; the dialog already said why

        started = outcome.started
        if outcome.gate_required:
            # Conflicts (or an unanswered port check): the gate owns the Start decision.
            started = self._run_gate(outcome.lab_id)

        name = outcome.lab_name or outcome.source_path.name
        if started:
            message = f"'{name}' imported and started."
        else:
            message = f"'{name}' imported. Use Start on its card when ready."
        self._pending_selection = (outcome.lab_id, message, started)
        self.refresh_labs()

    def _run_gate(self, lab_id: str) -> bool:
        gate = PreStartGateDialog(self._api_client, lab_id, parent=self)
        return gate.exec() == PreStartGateDialog.DialogCode.Accepted

    # ----- create: quick start / designer ---------------------------------------------------

    def _on_quick_start_create(self, draft: QuickStartDraft) -> None:
        if draft.template.os == "windows":
            # Readiness can be lost between choosing the template and Create (the engine
            # was switched back): re-check, and refuse with the specific reason if so.
            self.quick_start_screen.set_busy(True, "Checking Windows containers\u2026")
            self._run(self._check_then_create, draft, on_done=self._on_quick_start_created)
            return
        self.quick_start_screen.set_busy(True, "Creating lab\u2026")
        self._run(
            create_quick_start_lab, self._api_client, draft, on_done=self._on_quick_start_created
        )

    def _check_then_create(self, draft: QuickStartDraft) -> CreateLabResult:
        """Worker body for Windows drafts: readiness first, then the normal create."""
        docker = check_docker()
        readiness = windows_container_readiness(docker)
        if not readiness.ready:
            return CreateLabResult(
                success=False,
                detail=(
                    f"Windows containers are not available right now: {readiness.detail} "
                    f"{readiness.next_action} Then use Create Lab again, or go back to "
                    "Change template."
                ),
            )
        draft.windows_host_build = docker.host_build
        return create_quick_start_lab(self._api_client, draft)

    def _on_quick_start_created(self, result: CreateLabResult) -> None:
        if not result.success or not result.lab_id:
            detail = result.detail or "Could not create the quick-start lab."
            if result.errors:
                detail = "; ".join(f"{'.'.join(e.location)}: {e.message}" for e in result.errors)
            self.quick_start_screen.show_error(detail)
            return
        self.quick_start_screen.set_busy(False)
        self._start_new_lab(result.lab_id, "Quick start lab created.")

    def _on_designer_saved(self, lab_id: str, start: bool) -> None:
        if start:
            self._start_new_lab(lab_id, "Lab saved.")
            return
        self._pending_selection = (
            lab_id,
            "Lab saved. Use Start on its card when ready.",
            False,
        )
        self.refresh_labs()

    def _start_new_lab(self, lab_id: str, saved_message: str) -> None:
        """Save/Create flows end here: review in the gate, then land on the lab (D-4)."""
        started = self._run_gate(lab_id)
        message = (
            f"{saved_message} Lab started."
            if started
            else f"{saved_message} Use Start on its card when ready."
        )
        self._pending_selection = (lab_id, message, started)
        self.refresh_labs()

    # ----- dashboard card actions --------------------------------------------------------------

    def _on_start_requested(self, lab_id: str) -> None:
        started = self._run_gate(lab_id)
        if started:
            self._pending_selection = (lab_id, "", True)
        self.refresh_labs()

    def _on_delete_requested(self, lab_id: str) -> None:
        lab = self.lab_summary(lab_id)
        if lab is None:
            return
        if not confirm(
            self,
            title=f'Delete "{lab.name}"?',
            message=(
                "This removes the lab from Practicum along with any containers and networks "
                "it created on this computer. Files you exported or imported are not touched. "
                "This cannot be undone."
            ),
            confirm_label="Delete",
            destructive=True,
        ):
            return
        self._notify(f"Deleting '{lab.name}'\u2026", "info")
        self._run(self._delete_named, lab_id, lab.name, on_done=self._on_lab_deleted)

    def _delete_named(self, lab_id: str, name: str) -> tuple[DeleteResult, str]:
        """Worker body: carries the lab's name along so the result can be worded."""
        return self._api_client.delete_lab(lab_id), name

    def _on_lab_deleted(self, outcome: tuple[DeleteResult, str]) -> None:
        result, name = outcome
        if result.success:
            remaining = sum(1 for lab in self._labs if lab.name != name)
            tail = (
                " You have no labs left - create a new lab or import one to get started."
                if remaining == 0
                else ""
            )
            self._notify(
                f"Deleted '{name}'. Its containers and networks were removed from Docker; "
                f"any lab file you imported or exported is untouched.{tail}",
                "ok",
            )
        else:
            self._notify(result.detail, "error")
        self.refresh_labs()

    def _on_reset_requested(self, lab_id: str) -> None:
        lab = self.lab_summary(lab_id)
        if lab is None:
            return
        if not confirm(
            self,
            title=f'Reset "{lab.name}"?',
            message=(
                "Reset removes every container and network this lab created and returns it "
                "to its original state. Anything changed inside the lab's machines is lost. "
                "This cannot be undone. Your instruction progress on this computer is kept."
            ),
            confirm_label="Reset lab",
            destructive=True,
        ):
            return
        self._notify(f"Resetting '{lab.name}'\u2026", "info")
        self._run(self._reset_named, lab_id, lab.name, on_done=self._on_lab_reset)

    def _reset_named(self, lab_id: str, name: str) -> tuple[StartResult, str]:
        return self._api_client.reset_lab(lab_id), name

    def _on_lab_reset(self, outcome: tuple[StartResult, str]) -> None:
        result, name = outcome
        if result.success:
            self._notify(f"'{name}' reset to its original state.", "ok")
        else:
            self._notify(f"{result.detail}", "error")
        self.refresh_labs()

    # ----- edit / export -----------------------------------------------------------------------

    def _on_edit_requested(self, lab_id: str) -> None:
        lab = self.lab_summary(lab_id)
        if lab is None:
            return
        if lab.status == "running":
            self._notify(f"Stop '{lab.name}' before editing it.", "warn")
            return
        self._notify(f"Loading '{lab.name}'\u2026", "info")
        self._run(self._load_for_edit, lab_id, on_done=self._on_lab_loaded_for_edit)

    def _load_for_edit(self, lab_id: str) -> tuple[str, LabDefinitionResult]:
        return lab_id, self._api_client.get_lab(lab_id)

    def _on_lab_loaded_for_edit(self, outcome: tuple[str, LabDefinitionResult]) -> None:
        lab_id, result = outcome
        if not result.success:
            self._notify(result.detail, "error")
            return
        self._notify("")
        self.designer.load_lab(lab_id, result.definition)
        self.show_screen("designer")

    def _on_export_requested(self, lab_id: str) -> None:
        lab = self.lab_summary(lab_id)
        if lab is None:
            return
        self._run(self._api_client.export_lab, lab_id, on_done=self._on_lab_exported)

    def _on_lab_exported(self, result: LabDefinitionResult) -> None:
        if not result.success:
            self._notify(result.detail, "error")
            return
        documents = QStandardPaths.writableLocation(
            QStandardPaths.StandardLocation.DocumentsLocation
        )
        suggested = Path(documents or Path.home()) / export_file_name(result.name)
        path = ask_save_path(self, suggested)
        if path is None:
            return
        try:
            path.write_text(
                json.dumps(result.definition, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
        except OSError as exc:
            self._notify(f"Could not write {path}: {exc}", "error")
            return
        self._notify(
            f"'{result.name}' exported to {path}. Share that file; students import it with "
            "Import Existing Lab.",
            "ok",
        )

    # ----- lab results (hand-in) ---------------------------------------------------------------

    def _on_export_results_requested(self, lab_id: str, results: dict) -> None:
        """Student name (in-app dialog, remembered) → save picker → JSON or Markdown file."""
        summary = results["summary"]
        dialog = ResultsExportDialog(
            self,
            results["lab"]["name"],
            summary["completed"],
            summary["total"],
            student_name=str(self._settings.value("student_name", "") or ""),
        )
        if dialog.exec() != ResultsExportDialog.DialogCode.Accepted:
            return
        student = dialog.student_name
        self._settings.setValue("student_name", student)
        results["student"]["name"] = student
        documents = QStandardPaths.writableLocation(
            QStandardPaths.StandardLocation.DocumentsLocation
        )
        suggested = Path(documents or Path.home()) / results_file_name(
            results["lab"]["name"], student
        )
        path = ask_save_path(self, suggested, RESULTS_FILTER, "Export Lab Results")
        if path is None:
            return
        try:
            write_results(path, results)
        except OSError as exc:
            self.running_view.show_export_note(f"Could not write {path}: {exc}", "error")
            return
        self.running_view.show_export_note(
            f"Results saved to {path} ({summary['completed']} of {summary['total']} tasks "
            "complete). Hand that file to your instructor.",
            "ok",
        )

    def _on_screenshot_upload_requested(self, lab_id: str, section_id: str) -> None:
        path = ask_image_path(self)
        if path is None:
            return
        self.running_view.attach_uploaded_screenshot(section_id, path)

    def closeEvent(self, event) -> None:
        # Let in-flight API calls finish (briefly) instead of destroying running threads.
        self.running_view.clear()
        ManagedThread.wait_for_all(1500)
        super().closeEvent(event)

    # ----- running view ------------------------------------------------------------------------

    def _on_running_start_requested(self, lab_id: str) -> None:
        self._run_gate(lab_id)
        self.running_view.refresh()
        self.refresh_labs()

    def _on_running_lab_changed(self, lab_id: str, status: str) -> None:
        lab = self.lab_summary(lab_id)
        if lab is not None:
            lab.status = status
        # Keep the cached cards fresh for when the user goes back; cheap and off-thread.
        QTimer.singleShot(0, self.refresh_labs)
