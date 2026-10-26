"""Import a lab file and launch it (windows-desktop-import-lab-file).

`ImportLabDialog` is the in-app "Open Lab File" modal: a list of recent and sample lab
files plus "Browse computer…", which opens the system file picker — the one native dialog
the app is allowed to use (windows-desktop-in-app-dialogs). Once a file is chosen the same
dialog turns into a staged progress view: read file → POST /labs/import → check host ports
and subnets → start. The outcome tells the caller whether the lab started, or whether it must
open the pre-start gate because port or subnet conflicts were found (the gate stays the single
authority for starting a lab with conflicts; see prestart_gate.py).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import (
    QModelIndex,
    QPersistentModelIndex,
    QRect,
    QSettings,
    QSize,
    Qt,
    QTimer,
)
from PySide6.QtGui import QCloseEvent, QColor, QFont, QPainter, QPalette
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QStackedWidget,
    QStyle,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QVBoxLayout,
    QWidget,
)

from practicum_desktop.api_client import (
    ApiClient,
    DockerEngineResult,
    ImportLabResult,
    NetworkCheckResult,
    PortCheckResult,
    StartResult,
    StatusResult,
)
from practicum_desktop.dialogs import COPYABLE_TEXT_FLAGS
from practicum_desktop.lab_file import (
    LabFileEntry,
    LabFileReadResult,
    describe_lab_file,
    format_issue,
    read_lab_file,
    sample_lab_files,
)
from practicum_desktop.progress_panel import summarize_progress
from practicum_desktop.workers import CallableWorker

RECENT_FILES_KEY = "recent_lab_files"
MAX_RECENT_FILES = 8
FILE_DIALOG_TITLE = "Open Lab File"
FILE_DIALOG_FILTER = "Practicum lab files (*.json);;All files (*)"

STAGE_READING = "Reading lab file…"
STAGE_IMPORTING = "Importing lab definition…"
STAGE_CHECKING_PORTS = "Checking host ports and networks…"
STAGE_STARTING = "Starting containers…"
STAGE_FAILED = "Import did not complete"
STAGE_DONE = "Lab started"
START_POLL_MS = 1000
START_STAGE_BASE = 60  # the start stage spans 60 → 100 % of the bar

START_HINT = (
    "The first start can take a few minutes while Docker downloads the lab's images. "
    "The window will update as soon as the lab is running."
)
API_UNAVAILABLE_MESSAGE = (
    "The Practicum API is not available, so lab files can't be imported right now. "
    "Check the status at the top of the main window and use Retry once the API is running."
)


class RecentLabFiles:
    """Most-recently-imported lab files, newest first, persisted in QSettings."""

    def __init__(self, settings: QSettings) -> None:
        self._settings = settings

    def paths(self) -> list[Path]:
        stored = self._settings.value(RECENT_FILES_KEY, [])
        # QSettings hands a one-element list back as a plain string on some backends
        # (e.g. the Windows registry); normalise before use.
        if isinstance(stored, str):
            stored = [stored] if stored else []
        if not isinstance(stored, (list, tuple)):
            return []
        return [Path(item) for item in stored if isinstance(item, str) and item]

    def add(self, path: Path) -> None:
        path = Path(path).resolve()
        remaining = [p for p in self.paths() if p != path]
        updated = [path, *remaining][:MAX_RECENT_FILES]
        self._settings.setValue(RECENT_FILES_KEY, [str(p) for p in updated])


@dataclass
class ImportOutcome:
    """What the import flow achieved. Set as soon as the lab exists in the API, so a
    caller can refresh its lab list even when a later stage (start) failed."""

    lab_id: str
    lab_name: str
    source_path: Path
    started: bool = False
    # True when host port / subnet conflicts were found, the Docker engine serves the other
    # kind of container than the lab needs, or a check could not be answered: the caller
    # must open PreStartGateDialog for this lab instead of starting it blind.
    gate_required: bool = False
    container_os: str = "linux"


def _copyable_label(text: str = "") -> QLabel:
    label = QLabel(text)
    label.setWordWrap(True)
    label.setTextInteractionFlags(COPYABLE_TEXT_FLAGS)
    return label


FILE_HINT_ROLE = Qt.ItemDataRole.UserRole
ROW_HEIGHT = 46
ROW_PADDING = 8
ICON_SIZE = 20


class LabFileRowDelegate(QStyledItemDelegate):
    """Paints a list row in the mockup's style — file icon, bold file name, muted hint
    line — while keeping the view's own selection/disabled colours."""

    def sizeHint(
        self, option: QStyleOptionViewItem, index: QModelIndex | QPersistentModelIndex
    ) -> QSize:
        return QSize(option.rect.width(), ROW_HEIGHT)

    def paint(
        self,
        painter: QPainter,
        option: QStyleOptionViewItem,
        index: QModelIndex | QPersistentModelIndex,
    ) -> None:
        opt = QStyleOptionViewItem(option)
        self.initStyleOption(opt, index)
        opt.text = ""  # background + selection only; the text is drawn below
        style = opt.widget.style() if opt.widget is not None else QApplication.style()
        style.drawControl(QStyle.ControlElement.CE_ItemViewItem, opt, painter, opt.widget)

        selected = bool(opt.state & QStyle.StateFlag.State_Selected)
        enabled = bool(opt.state & QStyle.StateFlag.State_Enabled)
        group = QPalette.ColorGroup.Normal if enabled else QPalette.ColorGroup.Disabled
        role = QPalette.ColorRole.HighlightedText if selected else QPalette.ColorRole.Text
        text_color = opt.palette.color(group, role)
        hint_color = QColor(text_color)
        hint_color.setAlphaF(0.72)

        content = opt.rect.adjusted(ROW_PADDING, 0, -ROW_PADDING, 0)
        icon_rect = QRect(
            content.left(),
            content.top() + (content.height() - ICON_SIZE) // 2,
            ICON_SIZE,
            ICON_SIZE,
        )
        style.standardIcon(QStyle.StandardPixmap.SP_FileIcon).paint(painter, icon_rect)

        text_left = icon_rect.right() + 10
        half = content.height() // 2
        name_rect = QRect(text_left, content.top(), content.right() - text_left, half)
        hint_rect = QRect(text_left, content.top() + half, content.right() - text_left, half)
        align = Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter

        painter.save()
        name_font = QFont(opt.font)
        name_font.setBold(True)
        painter.setFont(name_font)
        painter.setPen(text_color)
        painter.drawText(name_rect, align, str(index.data(Qt.ItemDataRole.DisplayRole) or ""))

        hint_font = QFont(opt.font)
        if hint_font.pointSizeF() > 0:
            hint_font.setPointSizeF(max(7.0, hint_font.pointSizeF() - 1))
        painter.setFont(hint_font)
        painter.setPen(hint_color)
        painter.drawText(hint_rect, align, str(index.data(FILE_HINT_ROLE) or ""))
        painter.restore()


class ImportLabDialog(QDialog):
    """In-app "Open Lab File" modal followed by the import-and-launch progress view.

    After `exec()` returns, read `outcome`:
      * None                     – nothing was imported (cancelled, unreadable or invalid file,
                                   API unreachable).
      * outcome.started          – the lab was imported and is running.
      * outcome.gate_required    – the lab was imported but has port conflicts (or the check
                                   failed); open PreStartGateDialog(outcome.lab_id).
      * neither                  – imported, but starting failed; the lab is in the list and
                                   the error was shown here.
    The dialog result is Accepted only for the two success paths.
    """

    def __init__(
        self,
        api_client: ApiClient,
        settings: QSettings,
        parent: QWidget | None = None,
        api_available: bool = True,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(FILE_DIALOG_TITLE)
        self.setModal(True)
        self.resize(520, 420)

        self._api_client = api_client
        self._recent = RecentLabFiles(settings)
        self._api_available = api_available
        self._entries: list[LabFileEntry] = []
        self._busy = False
        self._source_path: Path | None = None
        # Every stage's worker is kept until the dialog goes away. Replacing a single
        # attribute from inside the previous stage's completion slot could destroy a
        # QThread that has not quite finished (Tigre/06 #6).
        self._workers: list[CallableWorker] = []
        self.outcome: ImportOutcome | None = None
        self._poll_timer = QTimer(self)
        self._poll_timer.setSingleShot(True)
        self._poll_timer.timeout.connect(self._poll_start_status)

        self._build_ui()
        self._populate_files()

    # ----- UI -------------------------------------------------------------------------

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        self.stack = QStackedWidget()
        layout.addWidget(self.stack)
        self.stack.addWidget(self._build_choose_page())
        self.stack.addWidget(self._build_progress_page())
        self.stack.setCurrentIndex(0)

    def _build_choose_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)

        title = QLabel(FILE_DIALOG_TITLE)
        title.setStyleSheet("font-size: 16px; font-weight: 600;")
        layout.addWidget(title)
        layout.addWidget(QLabel("Choose a .json lab export to import and launch."))

        self.api_banner = _copyable_label(API_UNAVAILABLE_MESSAGE)
        self.api_banner.setStyleSheet(
            "background-color: #fef3c7; color: #92400e; padding: 6px; border-radius: 4px;"
        )
        self.api_banner.setVisible(not self._api_available)
        layout.addWidget(self.api_banner)

        self.files_list = QListWidget()
        self.files_list.setItemDelegate(LabFileRowDelegate(self.files_list))
        self.files_list.currentRowChanged.connect(self._on_file_row_changed)
        self.files_list.itemDoubleClicked.connect(self._on_file_double_clicked)
        layout.addWidget(self.files_list, 1)

        self.browse_button = QPushButton("Browse computer…")
        self.browse_button.clicked.connect(self._on_browse_clicked)
        self.browse_button.setEnabled(self._api_available)
        layout.addWidget(self.browse_button)

        buttons_row = QHBoxLayout()
        buttons_row.addStretch(1)
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self.reject)
        buttons_row.addWidget(self.cancel_button)
        self.open_button = QPushButton("Open")
        self.open_button.setDefault(True)
        self.open_button.setEnabled(False)
        self.open_button.clicked.connect(self._on_open_clicked)
        buttons_row.addWidget(self.open_button)
        layout.addLayout(buttons_row)
        return page

    def _build_progress_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)

        self.stage_label = QLabel("")
        self.stage_label.setStyleSheet("font-size: 16px; font-weight: 600;")
        layout.addWidget(self.stage_label)

        self.file_label = _copyable_label()
        layout.addWidget(self.file_label)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setTextVisible(False)
        layout.addWidget(self.progress_bar)

        self.detail_label = _copyable_label()
        layout.addWidget(self.detail_label)

        self.errors_box = QPlainTextEdit()
        self.errors_box.setReadOnly(True)
        self.errors_box.setVisible(False)
        layout.addWidget(self.errors_box, 1)

        layout.addStretch(1)

        buttons_row = QHBoxLayout()
        buttons_row.addStretch(1)
        self.back_button = QPushButton("Choose another file")
        self.back_button.clicked.connect(self._show_choose_page)
        self.back_button.setVisible(False)
        buttons_row.addWidget(self.back_button)
        self.close_button = QPushButton("Close")
        self.close_button.clicked.connect(self.reject)
        self.close_button.setEnabled(False)
        buttons_row.addWidget(self.close_button)
        layout.addLayout(buttons_row)
        return page

    def _populate_files(self) -> None:
        self.files_list.clear()
        self._entries = []
        recent_paths = self._recent.paths()
        self._entries.extend(describe_lab_file(path, "recent") for path in recent_paths)
        recent_set = {path.resolve() for path in recent_paths}
        self._entries.extend(
            entry for entry in sample_lab_files() if entry.path.resolve() not in recent_set
        )

        for entry in self._entries:
            item = QListWidgetItem(entry.name)
            item.setData(FILE_HINT_ROLE, entry.hint)
            item.setToolTip(str(entry.path))
            if not entry.exists:
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEnabled)
            self.files_list.addItem(item)

    def _show_choose_page(self) -> None:
        self.stack.setCurrentIndex(0)
        self._source_path = None
        self._populate_files()
        self.open_button.setEnabled(False)

    # ----- choosing a file --------------------------------------------------------------

    def selected_entry(self) -> LabFileEntry | None:
        row = self.files_list.currentRow()
        if row < 0 or row >= len(self._entries):
            return None
        return self._entries[row]

    def _on_file_row_changed(self, row: int) -> None:
        entry = self.selected_entry()
        self.open_button.setEnabled(self._api_available and entry is not None and entry.exists)

    def _on_file_double_clicked(self, _item) -> None:
        self._on_open_clicked()

    def _on_open_clicked(self) -> None:
        entry = self.selected_entry()
        if entry is None or not entry.exists or not self._api_available:
            return
        self.start_import(entry.path)

    def _browse_start_dir(self) -> str:
        for path in self._recent.paths():
            if path.parent.is_dir():
                return str(path.parent)
        return str(Path.home())

    def _on_browse_clicked(self) -> None:
        if not self._api_available:
            return
        # The system file picker is the only native dialog the app may use
        # (windows-desktop-in-app-dialogs). Picking a file there is the confirmation: the
        # flow continues immediately rather than asking for a second "Open".
        path, _selected_filter = QFileDialog.getOpenFileName(
            self, FILE_DIALOG_TITLE, self._browse_start_dir(), FILE_DIALOG_FILTER
        )
        if path:
            self.start_import(Path(path))

    # ----- staged import flow -----------------------------------------------------------

    def start_import(self, path: Path) -> None:
        """Begins the read → import → port check → start sequence for `path`."""
        self._source_path = Path(path)
        self.outcome = None
        self.errors_box.clear()
        self.errors_box.setVisible(False)
        self.back_button.setVisible(False)
        self.detail_label.setText("")
        self.file_label.setText(str(self._source_path))
        self.stack.setCurrentIndex(1)
        self._set_busy(True)

        self._set_stage(STAGE_READING, 10)
        self._run(read_lab_file, self._source_path, on_done=self._on_file_read)

    def _run(self, func, *args, on_done, **kwargs) -> None:
        worker = CallableWorker(func, *args, **kwargs)
        worker.finished_call.connect(on_done)
        self._workers.append(worker)
        worker.start()

    def _set_stage(self, text: str, percent: int) -> None:
        self.stage_label.setText(text)
        self.progress_bar.setValue(percent)

    def _set_busy(self, busy: bool) -> None:
        self._busy = busy
        self.close_button.setEnabled(not busy)

    def _on_file_read(self, result: LabFileReadResult) -> None:
        if not result.success or result.definition is None:
            self._show_failure(result.error)
            return
        self._set_stage(STAGE_IMPORTING, 35)
        assert self._source_path is not None
        self._run(
            self._api_client.import_lab,
            result.definition,
            self._source_path.name,
            on_done=self._on_imported,
        )

    def _on_imported(self, result: ImportLabResult) -> None:
        if not result.success or not result.lab_id:
            self._show_failure(result.detail, issues=[format_issue(i) for i in result.errors])
            return

        assert self._source_path is not None
        self.outcome = ImportOutcome(
            lab_id=result.lab_id,
            lab_name=result.lab_name,
            source_path=self._source_path,
            container_os=result.container_os,
        )
        self._recent.add(self._source_path)
        self.file_label.setText(result.lab_name or self._source_path.name)

        self._set_stage(STAGE_CHECKING_PORTS, 60)
        self._run(self._api_client.check_ports, result.lab_id, on_done=self._on_ports_checked)

    def _on_ports_checked(self, result: PortCheckResult) -> None:
        assert self.outcome is not None
        if not result.success or result.has_conflicts:
            self._hand_over_to_gate()
            return
        self._run(
            self._api_client.check_networks, self.outcome.lab_id, on_done=self._on_networks_checked
        )

    def _on_networks_checked(self, result: NetworkCheckResult) -> None:
        assert self.outcome is not None
        if not result.success or result.has_conflicts:
            self._hand_over_to_gate()
            return
        self._run(self._api_client.get_docker_engine, on_done=self._on_engine_checked)

    def _on_engine_checked(self, result: DockerEngineResult) -> None:
        """A lab built for the other kind of container than Docker Desktop serves (a Windows
        lab in Linux-container mode, or vice versa) goes to the gate, which explains the
        switch and offers Retry, instead of failing mid-start."""
        assert self.outcome is not None
        mismatch = result.os_type != self.outcome.container_os
        if not result.success or not result.available or mismatch:
            self._hand_over_to_gate()
            return

        self._set_stage(STAGE_STARTING, START_STAGE_BASE)
        self.detail_label.setText(START_HINT)
        self._run(
            self._api_client.start_lab, self.outcome.lab_id, wait=False, on_done=self._on_started
        )

    def _hand_over_to_gate(self) -> None:
        """Never start blind: with port/subnet conflicts, the wrong engine mode (or no answer
        from a check) hand over to the gate, which shows the problem and the fixes and owns
        the Start decision."""
        assert self.outcome is not None
        self.outcome.gate_required = True
        self._set_busy(False)
        self.accept()

    def _on_started(self, result: StartResult) -> None:
        assert self.outcome is not None
        if result.success and result.pending:
            # The API starts the lab in the background: follow the real per-node progress
            # (image downloads, container creation) until its status settles.
            self._poll_start_status()
            return
        self._finish_start(result.success, result.detail)

    def _poll_start_status(self) -> None:
        assert self.outcome is not None
        if self._workers and self._workers[-1].isRunning():
            self._poll_timer.start(START_POLL_MS)  # previous poll still running; try later
            return
        self._run(self._api_client.get_status, self.outcome.lab_id, on_done=self._on_start_polled)

    def _on_start_polled(self, result: StatusResult) -> None:
        if not self._busy:
            return
        if result.success:
            text, overall = summarize_progress(result.progress)
            span = 100 - START_STAGE_BASE
            self._set_stage(text, START_STAGE_BASE + round(overall * span / 100))
        if not result.success or result.lab_status == "starting":
            self._poll_timer.start(START_POLL_MS)
            return
        if result.lab_status == "running":
            self._finish_start(True, "Lab started.")
            return
        failed = next((p for p in result.progress if p.step == "failed"), None)
        detail = (
            result.last_error
            or (failed.detail if failed else None)
            or "The lab failed to start."
        )
        self._finish_start(False, detail)

    def _finish_start(self, success: bool, detail: str) -> None:
        assert self.outcome is not None
        self._poll_timer.stop()
        if success:
            self.outcome.started = True
            self._set_stage(STAGE_DONE, 100)
            self._set_busy(False)
            self.accept()
            return

        self._show_failure(
            f"'{self.outcome.lab_name}' was imported but could not be started: {detail}",
            hint=(
                "The lab is in your lab list — use Start on its card once the problem is fixed."
            ),
        )

    def _show_failure(self, message: str, issues: list[str] | None = None, hint: str = "") -> None:
        self._set_stage(STAGE_FAILED, self.progress_bar.value())
        text = message if message else "The import did not complete."
        if hint:
            text = f"{text}\n\n{hint}"
        self.detail_label.setText(text)
        if issues:
            self.errors_box.setPlainText("\n".join(f"• {issue}" for issue in issues))
            self.errors_box.setVisible(True)
        # Offer to pick a different file only while nothing has been imported yet; once a lab
        # exists, re-importing from here would silently create a second copy.
        self.back_button.setVisible(self.outcome is None)
        self._set_busy(False)

    # ----- closing ---------------------------------------------------------------------

    def reject(self) -> None:
        # A stage is still talking to the API; closing now would lose its result and could
        # leave a half-imported lab without telling the user. Wait for the stage to finish.
        if self._busy:
            return
        super().reject()

    def closeEvent(self, event: QCloseEvent) -> None:
        if self._busy:
            event.ignore()
            return
        super().closeEvent(event)
