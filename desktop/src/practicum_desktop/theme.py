"""Visual theme of the desktop app (windows-desktop-visual-theme).

The design tokens below are the CSS custom properties of `design/practicum-mockups.html`
translated to Qt: colours, radii and type sizes, plus one application-wide style sheet that
styles widgets by *role* rather than by class. Roles are plain Qt dynamic properties, e.g.

    button.setProperty("kind", "primary")      # primary | secondary | danger | ghost | link
    label.setProperty("role", "h1")            # h1 | h2 | h3 | subtitle | muted | mono | hint
    frame.setProperty("panel", True)           # bordered white card (the mockup's .panel)
    label.setProperty("badge", "running")      # running | stopped | ready | error | busy

`apply_theme(app)` installs the sheet once; `restyle(widget)` re-polishes a widget after one
of its role properties changed at runtime (Qt only re-reads properties on polish).
"""

from __future__ import annotations

from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication, QWidget

# ----- tokens (from the mockup's :root) -----------------------------------------------------

INK = "#0f172a"
INK_SOFT = "#1e293b"
MUTED = "#6b7280"
MUTED_2 = "#94a3b8"
LINE = "#e5e7eb"
LINE_SOFT = "#eef0f3"
BG = "#f4f5f7"
CARD = "#ffffff"
ACCENT_SOFT = "#eef2ff"
GREEN = "#16a34a"
DANGER = "#dc2626"
DANGER_HOVER = "#b91c1c"
AMBER = "#d97706"

RADIUS_LG = 16
RADIUS_MD = 12
RADIUS_SM = 8

# Badge palettes (.lab-status.*)
BADGE_COLOURS = {
    "running": ("#dcfce7", "#15803d"),
    "stopped": ("#f1f5f9", "#475569"),
    "ready": ("#e0f2fe", "#075985"),
    "error": ("#fee2e2", "#b91c1c"),
    "busy": ("#fef3c7", "#92400e"),
}

# Lab status (API) -> badge role + label. Resolves the mockup's Running/Stopped/Draft to the
# statuses the API actually has (Tigre/11 C3, decision D-26).
STATUS_BADGES: dict[str, tuple[str, str]] = {
    "running": ("running", "Running"),
    "stopped": ("stopped", "Stopped"),
    "defined": ("ready", "Ready"),
    "error": ("error", "Error"),
    "starting": ("busy", "Starting…"),
    "stopping": ("busy", "Stopping…"),
}

FONT_FAMILY = '"Segoe UI", Inter, Roboto, Arial, sans-serif'
MONO_FAMILY = 'Consolas, "Cascadia Mono", "Courier New", monospace'


BADGE_RULES = "\n".join(
    f'QLabel[badge="{role}"] {{ background: {background}; color: {colour}; }}'
    for role, (background, colour) in BADGE_COLOURS.items()
)


def badge_for_status(status: str) -> tuple[str, str]:
    """(badge role, label) for an API lab status; unknown statuses show as-is, muted."""
    return STATUS_BADGES.get(status, ("stopped", status.capitalize() or "Unknown"))


STYLESHEET = f"""
QWidget {{
    font-family: {FONT_FAMILY};
    font-size: 13px;
    color: {INK};
}}
QMainWindow, QDialog, QWidget#screen, QScrollArea, QScrollArea > QWidget > QWidget {{
    background: {CARD};
}}
QWidget#titlebar {{
    background: {CARD};
    border-bottom: 1px solid {LINE};
}}
QLabel#brandBadge {{
    background: {INK};
    color: white;
    font-weight: 700;
    font-size: 11px;
    border-radius: 7px;
    min-width: 26px; max-width: 26px; min-height: 26px; max-height: 26px;
}}
QLabel#brandName {{
    font-weight: 600;
    font-size: 14px;
}}

/* ----- type roles ----- */
QLabel[role="h1"] {{ font-size: 28px; font-weight: 700; letter-spacing: -1px; }}
QLabel[role="hero"] {{ font-size: 42px; font-weight: 700; letter-spacing: -1px; }}
QLabel[role="h2"] {{ font-size: 18px; font-weight: 700; }}
QLabel[role="h3"] {{ font-size: 14px; font-weight: 700; }}
QLabel[role="title"] {{ font-size: 15px; font-weight: 700; }}
QLabel[role="subtitle"] {{ font-size: 14px; color: {MUTED}; }}
QLabel[role="muted"] {{ color: {MUTED}; font-size: 12px; }}
QLabel[role="hint"] {{ color: {MUTED_2}; font-size: 11px; }}
QLabel[role="mono"] {{ font-family: {MONO_FAMILY}; color: {MUTED}; font-size: 11px; }}
QLabel[role="label"] {{ font-size: 12px; font-weight: 600; color: {INK_SOFT}; }}
QLabel[role="error"] {{ color: {DANGER_HOVER}; }}
QLabel[role="ok"] {{ color: #15803d; font-weight: 600; }}

/* ----- buttons ----- */
QPushButton {{
    border-radius: 10px;
    font-weight: 600;
    font-size: 13px;
    padding: 9px 18px;
    border: 1px solid {LINE};
    background: {CARD};
    color: {INK};
}}
QPushButton:hover {{ background: #f9fafb; }}
QPushButton:disabled {{ color: {MUTED_2}; background: #fafafa; border-color: {LINE_SOFT}; }}
QPushButton[kind="primary"] {{ background: {INK}; color: white; border-color: {INK}; }}
QPushButton[kind="primary"]:hover {{ background: {INK_SOFT}; }}
QPushButton[kind="primary"]:disabled {{ background: #cbd5e1; border-color: #cbd5e1; color: white; }}
QPushButton[kind="danger"] {{ background: {DANGER}; color: white; border-color: {DANGER}; }}
QPushButton[kind="danger"]:hover {{ background: {DANGER_HOVER}; }}
QPushButton[kind="danger"]:disabled {{ background: #fca5a5; border-color: #fca5a5; color: white; }}
QPushButton[kind="ghost"] {{ background: transparent; border: none; color: {MUTED}; }}
QPushButton[kind="ghost"]:hover {{ color: {INK}; background: {LINE_SOFT}; }}
QPushButton[kind="link"] {{
    background: transparent; border: none; color: {MUTED}; padding: 2px 4px;
    text-align: left; font-weight: 400; text-decoration: underline;
}}
QPushButton[kind="link"]:hover {{ color: {INK}; }}
QPushButton[kind="dashed"] {{
    background: transparent; border: 1.5px dashed {LINE}; color: {MUTED}; font-weight: 400;
    border-radius: {RADIUS_SM}px;
}}
QPushButton[kind="dashed"]:hover {{ border-color: {INK}; color: {INK}; }}
QPushButton[small="true"] {{ padding: 6px 13px; font-size: 12px; }}

/* ----- panels / cards ----- */
QFrame[panel="true"] {{
    background: {CARD};
    border: 1px solid {LINE};
    border-radius: {RADIUS_MD}px;
}}
QFrame[panel="true"][selected="true"] {{ border: 1.5px solid {INK}; }}
QFrame[panel="soft"] {{
    background: #fafafa;
    border: 1px solid {LINE};
    border-radius: {RADIUS_SM}px;
}}
QFrame[panel="dark"] {{
    background: #0b1220;
    border: none;
    border-radius: 0px;
}}
QFrame#panelHead {{
    border: none;
    border-bottom: 1px solid {LINE_SOFT};
    background: transparent;
}}
QFrame[separator="true"] {{ background: {LINE}; max-height: 1px; min-height: 1px; border: none; }}
QFrame#bottomBar {{ border-top: 1px solid {LINE}; background: {CARD}; }}

/* ----- badges / chips / pills ----- */
QLabel[badge] {{
    font-size: 10.5px; font-weight: 700; padding: 3px 9px; border-radius: 9px;
}}
{BADGE_RULES}
QLabel[chip="true"] {{
    background: {ACCENT_SOFT}; color: #3730a3; font-size: 11.5px; padding: 4px 10px;
    border-radius: 11px;
}}
QLabel[chip="muted"] {{
    background: #f3f4f6; color: {MUTED}; font-size: 11.5px; padding: 4px 10px; border-radius: 11px;
}}
QLabel[chip="count"] {{
    background: {LINE_SOFT}; color: {MUTED}; font-size: 11px; padding: 1px 8px; border-radius: 9px;
}}
QLabel[banner="warn"] {{
    background: #fffbeb; color: #92400e; border: 1px solid #fde68a; border-radius: {RADIUS_SM}px;
    padding: 8px 12px; font-weight: 600; font-size: 12.5px;
}}
QLabel[banner="ok"] {{
    background: #f0fdf4; color: #15803d; border: 1px solid #bbf7d0; border-radius: {RADIUS_SM}px;
    padding: 8px 12px; font-weight: 600; font-size: 12.5px;
}}
QLabel[banner="error"] {{
    background: #fef2f2; color: #991b1b; border: 1px solid #fecaca; border-radius: {RADIUS_SM}px;
    padding: 8px 12px; font-weight: 600; font-size: 12.5px;
}}
QLabel[banner="info"] {{
    background: #f8fafc; color: {INK_SOFT}; border: 1px solid {LINE}; border-radius: {RADIUS_SM}px;
    padding: 8px 12px; font-size: 12.5px;
}}
QLabel#urlBar {{
    background: #f3f4f6; border-radius: 13px; padding: 5px 12px; font-size: 12px; color: {MUTED};
}}

/* ----- inputs ----- */
QLineEdit, QPlainTextEdit, QTextEdit, QComboBox {{
    border: 1px solid {LINE};
    border-radius: {RADIUS_SM}px;
    padding: 7px 10px;
    background: {CARD};
}}
QLineEdit, QPlainTextEdit, QTextEdit {{
    selection-background-color: {INK};
    selection-color: white;
}}
QLineEdit:focus, QPlainTextEdit:focus, QComboBox:focus {{ border-color: {INK}; }}
QLineEdit:disabled, QComboBox:disabled {{ color: {MUTED_2}; background: #fafafa; }}
QComboBox {{ color: {INK}; }}
QComboBox::drop-down {{ border: none; width: 22px; }}
/* The popup is a separate top-level list; style it explicitly so a dark system theme
   (Windows dark mode) cannot turn it into black-on-black. */
QComboBox QAbstractItemView, QComboBox QListView {{
    border: 1px solid {LINE}; background: {CARD}; color: {INK}; outline: none;
    selection-background-color: {ACCENT_SOFT}; selection-color: {INK};
}}
QComboBox QAbstractItemView::item {{ min-height: 24px; padding: 3px 8px; color: {INK}; }}
QComboBox QAbstractItemView::item:hover,
QComboBox QAbstractItemView::item:selected {{ background: {ACCENT_SOFT}; color: {INK}; }}
QCheckBox {{ spacing: 8px; }}
QCheckBox::indicator {{
    width: 16px; height: 16px; border: 1.5px solid {MUTED_2}; border-radius: 5px;
    background: {CARD};
}}
QCheckBox::indicator:checked {{ background: {GREEN}; border-color: {GREEN}; }}
QCheckBox[toggle="true"] {{
    background: #f8fafc; border: 1px solid {LINE}; border-radius: 14px; padding: 5px 12px;
    font-size: 12px; color: {INK_SOFT};
}}
QCheckBox[toggle="true"]::indicator {{
    width: 28px; height: 14px; border-radius: 7px; border: none; background: {LINE};
}}
QCheckBox[toggle="true"]::indicator:checked {{ background: {INK}; }}
QRadioButton::indicator {{
    width: 14px; height: 14px; border: 2px solid {LINE}; border-radius: 8px; background: {CARD};
}}
QRadioButton::indicator:checked {{
    border-color: {INK};
    background: qradialgradient(cx:0.5, cy:0.5, radius:0.5, fx:0.5, fy:0.5,
        stop:0 {INK}, stop:0.55 {INK}, stop:0.65 {CARD}, stop:1 {CARD});
}}

/* ----- tables / lists ----- */
QTableWidget, QListWidget, QTableView {{
    border: 1px solid {LINE_SOFT};
    border-radius: {RADIUS_SM}px;
    background: {CARD};
    gridline-color: {LINE_SOFT};
    font-size: 12px;
    selection-background-color: {ACCENT_SOFT};
    selection-color: {INK};
}}
QHeaderView::section {{
    background: #f8fafc; color: {MUTED}; font-weight: 600; font-size: 11px;
    padding: 6px 10px; border: none; border-bottom: 1px solid {LINE_SOFT};
}}
QTableWidget::item {{ padding: 4px 8px; }}
QProgressBar {{
    border: none; background: {LINE_SOFT}; border-radius: 3px;
    max-height: 6px; min-height: 6px; text-align: center;
}}
QProgressBar::chunk {{ background: {INK}; border-radius: 3px; }}
QScrollBar:vertical {{ background: transparent; width: 10px; margin: 0; }}
QScrollBar::handle:vertical {{ background: #cbd5e1; border-radius: 5px; min-height: 24px; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar:horizontal {{ background: transparent; height: 10px; margin: 0; }}
QScrollBar::handle:horizontal {{ background: #cbd5e1; border-radius: 5px; min-width: 24px; }}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}
QToolTip {{ background: {INK}; color: white; border: none; padding: 5px 8px; border-radius: 6px; }}
QGroupBox {{
    border: 1px solid {LINE}; border-radius: {RADIUS_SM}px; margin-top: 10px; font-weight: 600;
}}
QGroupBox::title {{ subcontrol-origin: margin; left: 10px; padding: 0 4px; color: {INK}; }}
QDialogButtonBox QPushButton {{ min-width: 80px; }}
"""


def light_palette() -> QPalette:
    """A fixed light palette so the app looks the same under Windows dark mode (otherwise
    unstyled bits such as combo-box popups inherit a dark background with dark text)."""
    palette = QPalette()
    groups = (QPalette.ColorGroup.Active, QPalette.ColorGroup.Inactive, QPalette.ColorGroup.Disabled)
    colours = {
        QPalette.ColorRole.Window: CARD,
        QPalette.ColorRole.WindowText: INK,
        QPalette.ColorRole.Base: CARD,
        QPalette.ColorRole.AlternateBase: BG,
        QPalette.ColorRole.ToolTipBase: INK,
        QPalette.ColorRole.ToolTipText: CARD,
        QPalette.ColorRole.Text: INK,
        QPalette.ColorRole.PlaceholderText: MUTED_2,
        QPalette.ColorRole.Button: CARD,
        QPalette.ColorRole.ButtonText: INK,
        QPalette.ColorRole.BrightText: CARD,
        QPalette.ColorRole.Highlight: ACCENT_SOFT,
        QPalette.ColorRole.HighlightedText: INK,
        QPalette.ColorRole.Link: "#3730a3",
        QPalette.ColorRole.Mid: LINE,
        QPalette.ColorRole.Dark: MUTED,
        QPalette.ColorRole.Light: BG,
    }
    for group in groups:
        for role, colour in colours.items():
            palette.setColor(group, role, QColor(colour))
    palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text, QColor(MUTED_2))
    palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.ButtonText, QColor(MUTED_2))
    return palette


def apply_theme(app: QApplication) -> None:
    """Installs the mockup-derived look application-wide: the Fusion style (identical on
    every platform, unlike the native Windows style), a light palette, and the style sheet."""
    app.setStyle("Fusion")
    app.setPalette(light_palette())
    app.setStyleSheet(STYLESHEET)


def restyle(widget: QWidget) -> None:
    """Re-applies the style sheet to `widget` after one of its role properties changed."""
    style = widget.style()
    style.unpolish(widget)
    style.polish(widget)
    widget.update()
