"""Running-lab screen (windows-desktop-lab-lifecycle-controls, windows-desktop-embedded-lab-view,
windows-desktop-open-node-shell, windows-desktop-status-polling).

Layout follows the mockup's `screen-running`: a header with back / title / meta / status
badge and the lifecycle toolbar, a body made of the embedded lab view (left) and the
instructions flyout (right, toggleable), the Lab nodes table with Open shell under the
browser pane, and a status bar ("Docker connected · <lab> · N containers running").

Lifecycle rules (D-5): Restart and Stop are routine and unconfirmed; Reset is styled as
destructive and always confirmed through `dialogs.confirm()`; Reset never touches the
locally-stored manual progress. While any lifecycle call is in flight every lifecycle button
is disabled (no overlapping calls on the same lab), and the screen keeps polling
`GET /labs/{id}/status` so the badge, node states and start progress stay honest even when
containers change outside Practicum.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QSplitter,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from practicum_desktop import icons, theme
from practicum_desktop.api_client import (
    ApiClient,
    LabSummary,
    PreviewResult,
    ResourceStatusInfo,
    StartResult,
    StatusResult,
    TopologyNodeInfo,
)
from practicum_desktop.dialogs import confirm
from practicum_desktop.embedded_view import EmbeddedLabView, default_web_view_factory
from practicum_desktop.lab_results import LabFacts, build_results
from practicum_desktop.labels import origin_meta, plural
from practicum_desktop.manual import ManualFlyout
from practicum_desktop.node_shell import ShellLaunchResult, open_node_shell, shell_label
from practicum_desktop.progress_panel import StartProgressPanel
from practicum_desktop.screenshots import SOURCE_LAB_VIEW
from practicum_desktop.widgets import (
    BackLink,
    Badge,
    MessageBanner,
    Panel,
    bind,
    copyable_label,
    edge_frame,
    make_button,
    payload_of,
)
from practicum_desktop.workers import CallableWorker

FAST_POLL_MS = 1000  # while starting / stopping / an action is in flight
SLOW_POLL_MS = 5000  # while the screen is visible and idle
FLYOUT_WIDTH = 320
FLYOUT_MIN_WIDTH = 240
BUSY_STATUSES = {"starting", "stopping"}
NODE_ROW_HEIGHT = 34
MAX_VISIBLE_NODE_ROWS = 6

RESET_TITLE = "Reset this lab?"
RESET_MESSAGE = (
    "Reset removes every container and network this lab created and returns it to the "
    "original state the instructor provided. Anything you changed inside the lab's machines "
    "is lost. This is more destructive than Stop and cannot be undone.\n\n"
    "Your checked-off instruction steps on this computer are kept."
)


def container_state_text(container: ResourceStatusInfo) -> str:
    if not container.exists:
        # `docker inspect` on a container that was never created (or was removed by Reset)
        # reports "No such object"; that is the normal "not created" state, not an error.
        if container.error and "no such" not in container.error.lower():
            return f"unknown ({container.error})"
        return "not created"
    if container.error:
        return f"unknown ({container.error})"
    return container.status or "unknown"


class RunningLabView(QWidget):
    """The screen a lab is used from. Drive it with `show_lab(summary)`; it loads the
    preview (manual, published ports) and status itself and keeps them fresh."""

    back_requested = Signal()
    start_requested = Signal(str)  # lab_id - the owner routes this through the gate (D-4)
    lab_changed = Signal(str, str)  # lab_id, new status - after a lifecycle action
    # The student wants to hand in their results: (lab_id, results document without the
    # student's name yet - the owner asks for it and writes the file).
    export_results_requested = Signal(str, object)
    # A step asks for a screenshot and the student wants to upload one: (lab_id, section_id);
    # the owner shows the image picker and calls `attach_uploaded_screenshot`.
    screenshot_upload_requested = Signal(str, str)

    def __init__(
        self,
        api_client: ApiClient,
        settings,
        parent: QWidget | None = None,
        web_view_factory: Callable = default_web_view_factory,
        screenshot_dir: Path | None = None,
    ) -> None:
        super().__init__(parent)
        self._api_client = api_client
        self._lab: LabSummary | None = None
        self._addresses: dict[str, list[str]] = {}  # node id -> "ip (network)" entries
        self._nodes: dict[str, TopologyNodeInfo] = {}  # node id -> declared image/os/shell
        self._preview: PreviewResult | None = None
        self._lab_status = ""
        self._busy = False
        self._docker_available = True
        self._last_running: bool | None = None
        self._workers: list[CallableWorker] = []
        self._status_worker: CallableWorker | None = None
        self._poll_timer = QTimer(self)
        self._poll_timer.timeout.connect(self.refresh)
        self._screenshot_dir = screenshot_dir
        self._build_ui(settings, web_view_factory)

    # ----- UI --------------------------------------------------------------------------

    def _build_ui(self, settings, web_view_factory) -> None:
        self.setObjectName("screen")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # header -------------------------------------------------------------------
        header = edge_frame("bottom", theme.LINE)
        header_row = QHBoxLayout(header)
        header_row.setContentsMargins(14, 10, 20, 10)
        header_row.setSpacing(12)

        self.back_button = BackLink("")  # icon-only: meaning in the tooltip/accessible name
        self.back_button.setToolTip("Back to my labs")
        self.back_button.setAccessibleName("Back to my labs")
        self.back_button.setStyleSheet("padding: 2px 8px; font-size: 16px;")
        self.back_button.clicked.connect(self.back_requested.emit)
        header_row.addWidget(self.back_button)

        title_column = QVBoxLayout()
        title_column.setSpacing(1)
        self.title_label = QLabel("")
        self.title_label.setProperty("role", "title")
        title_column.addWidget(self.title_label)
        self.meta_label = QLabel("")
        self.meta_label.setProperty("role", "muted")
        title_column.addWidget(self.meta_label)
        header_row.addLayout(title_column)

        self.badge = Badge("defined")
        header_row.addWidget(self.badge)
        header_row.addStretch(1)

        self.start_button = make_button("Start lab", kind="primary", small=True, icon="play")
        self.start_button.clicked.connect(self._on_start_clicked)
        header_row.addWidget(self.start_button)
        self.restart_button = make_button("Restart", small=True, icon="refresh")
        self.restart_button.clicked.connect(self._on_restart_clicked)
        header_row.addWidget(self.restart_button)
        self.stop_button = make_button("Stop lab", small=True, icon="stop")
        self.stop_button.clicked.connect(self._on_stop_clicked)
        header_row.addWidget(self.stop_button)
        self.reset_button = make_button("Reset", kind="danger", small=True)
        self.reset_button.setToolTip(
            "Remove the lab's containers and networks and return it to its original state"
        )
        self.reset_button.clicked.connect(self._on_reset_clicked)
        header_row.addWidget(self.reset_button)
        self.instructions_button = make_button("Instructions", small=True)
        self.instructions_button.setCheckable(True)
        self.instructions_button.setChecked(True)
        self.instructions_button.toggled.connect(self._on_instructions_toggled)
        header_row.addWidget(self.instructions_button)
        layout.addWidget(header)

        # action feedback ------------------------------------------------------------
        self.message_label = MessageBanner("info")
        self.message_label.hide()
        message_wrap = QWidget()
        message_layout = QVBoxLayout(message_wrap)
        message_layout.setContentsMargins(20, 10, 20, 0)
        message_layout.addWidget(self.message_label)
        self._message_wrap = message_wrap
        message_wrap.hide()
        layout.addWidget(message_wrap)

        # body: browser + nodes on the left, instructions on the right, user-resizable ----
        self.body_splitter = QSplitter(Qt.Orientation.Horizontal)
        self.body_splitter.setChildrenCollapsible(False)
        self.body_splitter.setHandleWidth(6)
        self.body_splitter.setStyleSheet(
            f"QSplitter::handle {{ background: {theme.LINE_SOFT}; }}"
            f"QSplitter::handle:hover {{ background: {theme.LINE}; }}"
        )

        left = QVBoxLayout()
        left.setContentsMargins(0, 0, 0, 0)
        left.setSpacing(0)

        self.center_stack = QStackedWidget()
        self.embedded_view = EmbeddedLabView(web_view_factory=web_view_factory)
        self.center_stack.addWidget(self.embedded_view)
        progress_host = QWidget()
        progress_layout = QVBoxLayout(progress_host)
        progress_layout.setContentsMargins(20, 16, 20, 16)
        self.progress_panel = StartProgressPanel()
        progress_layout.addWidget(self.progress_panel)
        progress_layout.addStretch(1)
        self.center_stack.addWidget(progress_host)
        left.addWidget(self.center_stack, 1)

        self.nodes_panel = Panel("Lab nodes", padding=10)
        self.nodes_panel.setStyleSheet(
            f"QFrame[panel='true'] {{ border: none; border-top: 1px solid {theme.LINE}; "
            "border-radius: 0; }"
        )
        self.nodes_table = QTableWidget(0, 5)
        self.nodes_table.setHorizontalHeaderLabels(["Node", "Address", "Container", "State", ""])
        header_view = self.nodes_table.horizontalHeader()
        header_view.setStretchLastSection(False)
        header_view.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.nodes_table.setColumnWidth(0, 130)
        self.nodes_table.setColumnWidth(1, 190)
        self.nodes_table.setColumnWidth(3, 150)  # "running · installing…" fits
        self.nodes_table.setColumnWidth(4, 174)  # cell widgets are not measured by Qt
        self.nodes_table.verticalHeader().hide()
        self.nodes_table.verticalHeader().setDefaultSectionSize(NODE_ROW_HEIGHT)
        self.nodes_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.nodes_table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self._fit_nodes_table(1)
        self.nodes_panel.body_layout.addWidget(self.nodes_table)
        self.nodes_status_label = copyable_label("", role="hint")
        self.nodes_panel.body_layout.addWidget(self.nodes_status_label)
        left.addWidget(self.nodes_panel)

        left_widget = QWidget()
        left_widget.setLayout(left)
        left_widget.setMinimumWidth(420)
        self.body_splitter.addWidget(left_widget)

        self.manual_flyout = ManualFlyout(settings, screenshot_dir=self._screenshot_dir)
        self.manual_flyout.setMinimumWidth(FLYOUT_MIN_WIDTH)
        self.manual_flyout.close_requested.connect(self._on_flyout_close_requested)
        self.manual_flyout.export_requested.connect(self._on_export_results_clicked)
        self.manual_flyout.screenshot_capture_requested.connect(self._on_capture_screenshot)
        self.manual_flyout.screenshot_upload_requested.connect(
            self._on_upload_screenshot
        )
        self.body_splitter.addWidget(self.manual_flyout)
        self.body_splitter.setStretchFactor(0, 1)
        self.body_splitter.setStretchFactor(1, 0)
        self.body_splitter.setSizes([900, FLYOUT_WIDTH])
        layout.addWidget(self.body_splitter, 1)

        # status bar ---------------------------------------------------------------
        status_bar = edge_frame("top", theme.LINE)
        status_row = QHBoxLayout(status_bar)
        status_row.setContentsMargins(20, 7, 20, 7)
        status_row.setSpacing(14)
        self.docker_dot = icons.icon_label("success", 12, "Docker")
        status_row.addWidget(self.docker_dot)
        self.docker_label = QLabel("Docker connected")
        self.docker_label.setProperty("role", "hint")
        status_row.addWidget(self.docker_label)
        self.containers_label = QLabel("")
        self.containers_label.setProperty("role", "hint")
        status_row.addWidget(self.containers_label)
        status_row.addStretch(1)
        self.saved_label = QLabel("Changes saved locally")
        self.saved_label.setProperty("role", "hint")
        self.saved_label.setToolTip(
            "Your instruction progress is stored on this computer only and survives Reset"
        )
        status_row.addWidget(self.saved_label)
        layout.addWidget(status_bar)

        self.set_docker_available(True)
        self._apply_buttons()

    # ----- public API --------------------------------------------------------------------

    @property
    def lab_id(self) -> str | None:
        return self._lab.id if self._lab else None

    @property
    def lab_status(self) -> str:
        return self._lab_status

    @property
    def busy(self) -> bool:
        return self._busy

    def show_lab(self, lab: LabSummary) -> None:
        """Switches the screen to `lab`, loading its manual, ports and live status."""
        switching = self._lab is None or self._lab.id != lab.id
        self._lab = lab
        self._lab_status = lab.status
        self.title_label.setText(lab.name)
        self.meta_label.setText(origin_meta(lab))
        self.badge.set_status(lab.status)
        self.containers_label.setText(lab.name)
        self._hide_message()
        if switching:
            self._last_running = None
            self._addresses = {}
            self._nodes = {}
            self._preview = None
            self.embedded_view.clear()
            self.nodes_table.setRowCount(0)
            self.nodes_status_label.setText("")
            self.manual_flyout.show_empty("Loading the lab manual\u2026")
            self._run(self._api_client.get_preview, lab.id, on_done=self._on_preview_loaded)
        self._apply_buttons()
        self.refresh()
        self._schedule_polling()

    def clear(self) -> None:
        self._poll_timer.stop()
        self._lab = None
        self._lab_status = ""
        self.embedded_view.clear()
        self.manual_flyout.show_empty("Select a lab to view its manual.")
        self.nodes_table.setRowCount(0)

    def refresh(self) -> None:
        """Re-reads GET /status (also the polling tick). A tick that lands while the previous
        status call is still running (slow `docker inspect`) is skipped rather than stacked."""
        if self._lab is None:
            return
        if self._status_worker is not None and self._status_worker.isRunning():
            return
        self._status_worker = self._run(
            self._api_client.get_status, self._lab.id, on_done=self._on_status_loaded
        )

    def set_docker_available(self, available: bool) -> None:
        self._docker_available = available
        name = "success" if available else "error"
        if icons.icon_available(name):
            icons.set_label_icon(self.docker_dot, name, 12)
        else:
            colour = theme.GREEN if available else theme.DANGER
            self.docker_dot.setStyleSheet(
                f"background: {colour}; border-radius: 6px; margin: 3px;"
            )
        self.docker_label.setText("Docker connected" if available else "Docker unavailable")

    # ----- visibility / polling -----------------------------------------------------------

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self._schedule_polling()

    def hideEvent(self, event) -> None:
        super().hideEvent(event)
        self._poll_timer.stop()

    def _schedule_polling(self) -> None:
        if self._lab is None or not self.isVisible():
            self._poll_timer.stop()
            return
        fast = self._busy or self._lab_status in BUSY_STATUSES
        self._poll_timer.start(FAST_POLL_MS if fast else SLOW_POLL_MS)

    # ----- loading -------------------------------------------------------------------------

    def _run(self, func, *args, on_done) -> CallableWorker:
        worker = CallableWorker(func, *args)
        worker.finished_call.connect(on_done)
        self._workers.append(worker)
        if len(self._workers) > 32:  # keep finished workers from piling up forever
            self._workers = [w for w in self._workers if w.isRunning()] + [worker]
        worker.start()
        return worker

    def _on_preview_loaded(self, result: PreviewResult) -> None:
        if self._lab is None:
            return
        if not result.success:
            self.manual_flyout.show_empty(result.detail)
            self.embedded_view.set_port_mappings([])
            return
        self._preview = result
        self.manual_flyout.show_lab(self._lab.id, result.name, result.manual_sections)
        # Per machine when the preview says who publishes what (several desktops → a picker
        # by machine name); the lab-wide list is the fallback for older API responses.
        per_node = [m for node in result.topology.nodes for m in node.port_mappings]
        self.embedded_view.set_port_mappings(per_node or result.port_mappings)
        self._nodes = {node.id: node for node in result.topology.nodes}
        self._addresses = {}
        for interface in result.topology.interfaces:
            self._addresses.setdefault(interface.node, []).append(
                f"{interface.address.split('/')[0]} ({interface.network})"
            )
        self._apply_addresses()
        self._apply_shell_buttons()
        if result.description:
            self.title_label.setToolTip(result.description)

    def _on_status_loaded(self, result: StatusResult) -> None:
        if self._lab is None:
            return
        if not result.success:
            self.nodes_status_label.setText(result.detail)
            return

        previous = self._lab_status
        self._lab_status = result.lab_status or previous
        self.badge.set_status(self._lab_status)
        self._render_nodes(result)

        running = self._lab_status == "running"
        if running != self._last_running:
            self._last_running = running
            self.embedded_view.set_lab_running(running)

        if self._lab_status == "starting":
            self.progress_panel.set_title("Starting containers\u2026")
            self.progress_panel.set_progress(result.progress)
            self.center_stack.setCurrentIndex(1)
        else:
            self.center_stack.setCurrentIndex(0)

        if self._lab_status == "error" and result.last_error and not self._busy:
            self._show_message(f"{result.last_error}", "error")
        if previous != self._lab_status and not self._busy:
            self.lab_changed.emit(self._lab.id, self._lab_status)
        self._apply_buttons()
        self._schedule_polling()

    def _fit_nodes_table(self, rows: int) -> None:
        """Shows up to MAX_VISIBLE_NODE_ROWS rows without scrolling; more rows scroll."""
        visible = max(1, min(rows, MAX_VISIBLE_NODE_ROWS))
        header = self.nodes_table.horizontalHeader().height() or 30
        self.nodes_table.setFixedHeight(header + visible * NODE_ROW_HEIGHT + 4)

    def _render_nodes(self, result: StatusResult) -> None:
        containers = result.containers
        self.nodes_table.setRowCount(len(containers))
        self._fit_nodes_table(len(containers))
        running = 0
        for row, container in enumerate(containers):
            self.nodes_table.setItem(row, 0, QTableWidgetItem(container.id))
            self.nodes_table.setItem(
                row, 1, QTableWidgetItem(", ".join(self._addresses.get(container.id, [])))
            )
            self.nodes_table.setItem(row, 2, QTableWidgetItem(container.name))
            state_item = QTableWidgetItem(container_state_text(container))
            if container.note:
                state_item.setToolTip(container.note)
                if "installing" in container.note.lower():
                    state_item.setText(f"{container_state_text(container)} \u00b7 installing\u2026")
                elif "failed" in container.note.lower():
                    state_item.setText(f"{container_state_text(container)} \u00b7 install failed")
            self.nodes_table.setItem(row, 3, state_item)
            is_running = container.exists and container.status == "running"
            shell_button = self._shell_button(container, is_running)
            self.nodes_table.setCellWidget(row, 4, shell_button)
            running += int(is_running)

        name = self._lab.name if self._lab else ""
        self.containers_label.setText(
            f"{name} \u00b7 {plural(running, 'container')} running" if containers else name
        )
        notes = [f"{c.id}: {c.note}" for c in containers if c.note]
        if result.detail:
            self.nodes_status_label.setText(result.detail)
        elif notes:
            # e.g. "host: Practicum: installing packages (git curl) - this takes a minute…"
            self.nodes_status_label.setText("\n".join(notes))
        elif not containers:
            self.nodes_status_label.setText("This lab has no nodes.")
        elif running == 0:
            self.nodes_status_label.setText(
                "No node is running. Start the lab, then use Open shell to work inside a node."
            )
        else:
            self.nodes_status_label.setText(
                "Open shell gives you a terminal inside a node. The addresses above are what "
                "the nodes see (reachable from inside the lab, not from this computer)."
            )

    def _node_shell(self, node_id: str) -> tuple[str, str | None]:
        """(os, shell) the node declares; Linux with the bash/sh default until the preview
        has arrived or for nodes the preview does not know."""
        node = self._nodes.get(node_id)
        if node is None:
            return "linux", None
        return node.os, node.shell

    def _shell_button(self, container: ResourceStatusInfo, is_running: bool) -> QPushButton:
        """'Open shell' / 'Open PowerShell' with the terminal icon; the tooltip names the
        node and shell so the action is unambiguous before it is clicked."""
        os, shell = self._node_shell(container.id)
        label = shell_label(os, shell)
        text = "Open PowerShell" if os == "windows" and shell != "cmd" else "Open shell"
        button = make_button(text, small=True, icon="terminal")
        button.setEnabled(is_running)
        button.setAccessibleName(f"{text} on {container.id}")
        button.setToolTip(
            f"Opens {label} inside '{container.id}' in a new terminal window"
            if is_running
            else f"Start the lab to open {label} on '{container.id}'"
        )
        bind(button, self._on_open_shell_clicked, container)
        return button

    def _apply_addresses(self) -> None:
        """Fills the Address column once the preview (topology) has arrived."""
        for row in range(self.nodes_table.rowCount()):
            item = self.nodes_table.item(row, 0)
            if item is None:
                continue
            self.nodes_table.setItem(
                row, 1, QTableWidgetItem(", ".join(self._addresses.get(item.text(), [])))
            )

    def _apply_shell_buttons(self) -> None:
        """Re-labels the shell buttons once the preview says which OS/shell each node has."""
        for row in range(self.nodes_table.rowCount()):
            button = self.nodes_table.cellWidget(row, 4)
            container = payload_of(button) if button is not None else None
            if container is None:
                continue
            enabled = button.isEnabled()
            self.nodes_table.setCellWidget(row, 4, self._shell_button(container, enabled))

    def _on_open_shell_clicked(self) -> None:
        container = payload_of(self.sender())
        if container is None:
            return
        os, shell = self._node_shell(container.id)
        self.nodes_status_label.setText(
            f"Opening {shell_label(os, shell)} on '{container.id}'\u2026"
        )
        self._run(
            open_node_shell, container.name, container.id, os, shell, on_done=self._on_shell_opened
        )

    def _on_shell_opened(self, result: ShellLaunchResult) -> None:
        text = result.detail
        if not result.success and result.command:
            text = f"{text}\n{' '.join(result.command)}"
        self.nodes_status_label.setText(text)

    # ----- lifecycle ---------------------------------------------------------------------

    def _apply_buttons(self) -> None:
        status = self._lab_status
        running = status == "running"
        transitional = status in BUSY_STATUSES
        self.start_button.setVisible(not running and self._lab is not None)
        self.restart_button.setVisible(running)
        self.stop_button.setVisible(running)
        enabled = not self._busy and not transitional and self._lab is not None
        for button in (self.start_button, self.restart_button, self.stop_button):
            button.setEnabled(enabled)
        # Reset is offered whatever the state (even stopped or error), just not mid-action.
        self.reset_button.setEnabled(enabled)
        self.back_button.setEnabled(True)

    def _on_start_clicked(self) -> None:
        if self._lab is None or self._busy:
            return
        self.start_requested.emit(self._lab.id)

    def _on_stop_clicked(self) -> None:
        self._run_lifecycle("Stopping lab\u2026", self._api_client.stop_lab)

    def _on_restart_clicked(self) -> None:
        self._run_lifecycle("Restarting lab\u2026", self._api_client.restart_lab)

    def _on_reset_clicked(self) -> None:
        if self._lab is None or self._busy:
            return
        if not confirm(
            self,
            title=RESET_TITLE,
            message=RESET_MESSAGE,
            confirm_label="Reset lab",
            destructive=True,
        ):
            return
        self._run_lifecycle("Resetting lab\u2026", self._api_client.reset_lab)

    def _run_lifecycle(self, progress_text: str, func) -> None:
        """Runs one lifecycle call with every lifecycle button disabled until it answers."""
        if self._lab is None or self._busy:
            return
        self._busy = True
        self._apply_buttons()
        self._show_message(progress_text, "info")
        self._run(func, self._lab.id, on_done=self._on_lifecycle_done)
        self._schedule_polling()

    def _on_lifecycle_done(self, result: StartResult) -> None:
        self._busy = False
        if self._lab is None:
            return
        if result.success:
            if result.lab_status:
                self._lab_status = result.lab_status
                self.badge.set_status(result.lab_status)
            text = result.detail
            if result.lab_status == "defined":
                text = (
                    "Lab reset to its original state. Your instruction progress is kept; "
                    "use Start lab to run it again."
                )
            self._show_message(f"{text}", "ok")
            self.lab_changed.emit(self._lab.id, self._lab_status)
        elif result.busy:
            self._show_message(f"{result.detail}", "warn")
        else:
            if result.lab_status:
                self._lab_status = result.lab_status
                self.badge.set_status(result.lab_status)
            self._show_message(f"{result.detail}", "error")
            self.lab_changed.emit(self._lab.id, self._lab_status)
        self._apply_buttons()
        self.refresh()

    def _on_flyout_close_requested(self) -> None:
        self.instructions_button.setChecked(False)

    def results(self) -> dict | None:
        """The results document for the current lab (student name left for the owner)."""
        if self._lab is None:
            return None
        preview = self._preview
        facts = LabFacts(
            id=self._lab.id,
            name=self._lab.name,
            description=(preview.description if preview else "") or self._lab.description,
            author=preview.author if preview else "",
            version=preview.version if preview else "",
            origin=self._lab.origin,
            source_file=self._lab.source_file,
        )
        return build_results(
            facts,
            self.manual_flyout.sections,
            self.manual_flyout.task_completions(),
            screenshots=self.manual_flyout.screenshots(),
        )

    # ----- screenshots -------------------------------------------------------------------

    def _on_capture_screenshot(self, section_id: str) -> None:
        """Grabs the embedded lab view for the step (what the student sees right now)."""
        pixmap, problem = self.embedded_view.capture()
        if pixmap is None:
            self.manual_flyout.show_screenshot_problem(section_id, problem)
            return
        self.manual_flyout.attach_screenshot(section_id, pixmap, SOURCE_LAB_VIEW)

    def _on_upload_screenshot(self, section_id: str) -> None:
        if self._lab is not None:
            self.screenshot_upload_requested.emit(self._lab.id, section_id)

    def attach_uploaded_screenshot(self, section_id: str, path: Path) -> bool:
        return self.manual_flyout.attach_screenshot_file(section_id, path)

    def _on_export_results_clicked(self) -> None:
        results = self.results()
        if results is None or self._lab is None:
            return
        self.export_results_requested.emit(self._lab.id, results)

    def show_export_note(self, text: str, kind: str = "ok") -> None:
        self._show_message(text, kind)

    def _on_instructions_toggled(self, checked: bool) -> None:
        # Hiding the flyout only hides it; its task state lives in QSettings and the widget.
        self.manual_flyout.setVisible(checked)

    # ----- messages --------------------------------------------------------------------

    def _show_message(self, text: str, banner: str) -> None:
        self.message_label.set_message(text, banner)
        self._message_wrap.show()

    def _hide_message(self) -> None:
        self.message_label.hide()
        self._message_wrap.hide()
