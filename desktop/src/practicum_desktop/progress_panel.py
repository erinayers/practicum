"""Real start progress (runtime-image-pull-progress, desktop side).

`StartProgressPanel` renders the per-node progress that `GET /labs/{id}/status` reports
while a lab is starting: one row per node with its current step ("Downloading image…",
"Starting container…", "Ready", "Failed") and, while an image is being pulled, a real
percentage bar. `summarize_progress` folds the same data into the one-line text + overall
percentage used by the import dialog and the gate, replacing their earlier fixed timers.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QGridLayout, QLabel, QProgressBar, QVBoxLayout, QWidget

from practicum_desktop import icons, theme
from practicum_desktop.api_client import NODE_STEP_LABELS, NodeProgressInfo
from practicum_desktop.widgets import discard, role_label

# Rough share of the whole start each step represents, so the overall bar moves even when
# no image needs pulling.
STEP_WEIGHT = {
    "waiting": 0.0,
    "checking_image": 0.1,
    "pulling_image": 0.1,  # + 0.6 * percent
    "creating_container": 0.8,
    "connecting_networks": 0.9,
    "ready": 1.0,
    "failed": 1.0,
}


def node_percent(entry: NodeProgressInfo) -> int:
    if entry.step == "pulling_image":
        return round(100 * (0.1 + 0.6 * (entry.percent or 0) / 100))
    return round(100 * STEP_WEIGHT.get(entry.step, 0.0))


def step_text(entry: NodeProgressInfo) -> str:
    label = NODE_STEP_LABELS.get(entry.step, entry.step)
    if entry.step == "pulling_image":
        parts = [f"Downloading {entry.image}"]
        if entry.percent is not None:
            parts.append(f"{entry.percent}%")
        if entry.detail:
            parts.append(entry.detail)
        return " \u00b7 ".join(parts)
    if entry.step == "failed" and entry.detail:
        return f"Failed: {entry.detail}"
    return label


def summarize_progress(progress: list[NodeProgressInfo]) -> tuple[str, int]:
    """('Downloading alpine:3.21 · 42% · 3 of 7 layers (router)', 37) for the node that is
    currently being worked on; ('Starting containers…', 0) before anything was reported."""
    if not progress:
        return "Starting containers\u2026", 0
    overall = round(sum(node_percent(p) for p in progress) / len(progress))
    failed = next((p for p in progress if p.step == "failed"), None)
    if failed is not None:
        return f"{step_text(failed)} ({failed.node_id})", overall
    active = next((p for p in progress if p.step not in ("ready", "waiting")), None)
    if active is None:
        if all(p.step == "ready" for p in progress):
            return "All containers are running.", 100
        return "Starting containers\u2026", overall
    return f"{step_text(active)} ({active.node_id})", overall


class StartProgressPanel(QFrame):
    """Per-node progress list shown while a lab starts (running view + gate)."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setProperty("panel", "true")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(8)
        self.title_label = role_label("Starting containers\u2026", "h3")
        layout.addWidget(self.title_label)
        self.summary_label = role_label("", "muted", wrap=True)
        layout.addWidget(self.summary_label)
        self.overall_bar = QProgressBar()
        self.overall_bar.setRange(0, 100)
        self.overall_bar.setTextVisible(False)
        layout.addWidget(self.overall_bar)
        self.rows = QGridLayout()
        self.rows.setHorizontalSpacing(12)
        self.rows.setVerticalSpacing(6)
        self.rows.setColumnStretch(1, 1)
        layout.addLayout(self.rows)
        self._row_widgets: list[QWidget] = []

    def set_progress(self, progress: list[NodeProgressInfo]) -> None:
        summary, overall = summarize_progress(progress)
        self.summary_label.setText(summary)
        self.overall_bar.setValue(overall)
        for widget in self._row_widgets:
            self.rows.removeWidget(widget)
            discard(widget)
        self._row_widgets = []
        for row, entry in enumerate(progress):
            name = QLabel(entry.node_id)
            name.setProperty("role", "label")
            state = QLabel(step_text(entry))
            state.setProperty("role", "error" if entry.step == "failed" else "muted")
            state.setWordWrap(True)
            self.rows.addWidget(name, row, 0, Qt.AlignmentFlag.AlignTop)
            self.rows.addWidget(state, row, 1)
            self._row_widgets.extend([name, state])
            if entry.step == "pulling_image":
                bar = QProgressBar()
                bar.setRange(0, 100)
                bar.setValue(entry.percent or 0)
                bar.setTextVisible(False)
                bar.setFixedWidth(120)
                self.rows.addWidget(bar, row, 2)
                self._row_widgets.append(bar)
            elif entry.step in ("ready", "failed"):
                mark = self._outcome_mark(entry.step)
                self.rows.addWidget(mark, row, 2, Qt.AlignmentFlag.AlignTop)
                self._row_widgets.append(mark)

    @staticmethod
    def _outcome_mark(step: str) -> QLabel:
        """The design check / cross for a finished node (text glyph when assets are missing)."""
        name, glyph, colour, label = (
            ("success", "\u2713", theme.GREEN, "Ready")
            if step == "ready"
            else ("error", "\u2717", theme.DANGER, "Failed")
        )
        if icons.icon_available(name):
            return icons.icon_label(name, 16, label)
        mark = QLabel(glyph)
        mark.setToolTip(label)
        mark.setAccessibleName(label)
        mark.setStyleSheet(f"color: {colour}; font-weight: 700;")
        return mark

    def set_title(self, text: str) -> None:
        self.title_label.setText(text)
