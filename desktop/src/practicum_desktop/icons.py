"""The design icon set (windows-desktop-design-icons).

`design/icons.png` supplies nine icons; `tools/slice_design_icons.py` cuts them into the
transparent PNGs under `assets/icons/`, and this module is the only place that knows their
files and meanings. Every screen asks for an icon *by meaning* (`icon("success")`) so later
icons can be added here without screen-specific loading code:

    success   green circle + check    check / OK / done / ready states
    error     red circle + cross      errors, failed actions, blocked states
    warning   orange circle + bang    warnings, attention, "resolve before continuing"
    back      black circle + arrow    back navigation
    forward   black circle + arrow    forward navigation / calls to action that move on
    play      black circle + triangle start / run a lab; ready-made (quick start) labs
    terminal  prompt in a frame       terminal and shell actions, terminal-only templates
    desktop   monitor                 desktop templates and lab environments
    tools     pencil + wrench         designer / custom labs, editing

Two more are *derived* - drawn by `tools/slice_design_icons.py` in the same language as the
black discs because the sheet has no artwork for them (swap in real artwork when supplied):

    refresh   black circle + ↻        restart / reload
    stop      black circle + square   stop a running lab

The monochrome icons are black; `icon(name, colour=...)` re-tints them (white on the dark
primary buttons, muted grey for hints). Everything degrades gracefully: when an asset is
missing (`icon_available()` is False) the helpers return a null `QIcon` / empty `QPixmap`
and every screen still builds and works - the meaning is always also carried by text, a
tooltip or an accessible name, never by the icon or its colour alone.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from functools import cache
from pathlib import Path

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPixmap
from PySide6.QtWidgets import QAbstractButton, QLabel, QWidget

from practicum_desktop import theme


@dataclass(frozen=True)
class IconSpec:
    name: str
    file: str
    meaning: str
    label: str  # default accessible name / tooltip for icon-only uses
    coloured: bool = False  # True: the artwork carries its own colour (never tinted)
    derived: bool = False  # True: not on the design sheet; drawn to match it (see module doc)


ICONS: dict[str, IconSpec] = {
    spec.name: spec
    for spec in (
        IconSpec("success", "success.png", "check / OK / done / ready", "OK", coloured=True),
        IconSpec("error", "error.png", "error / failed / blocked", "Error", coloured=True),
        IconSpec("warning", "warning.png", "warning / needs attention", "Warning", coloured=True),
        IconSpec("back", "back.png", "back navigation", "Back"),
        IconSpec("forward", "forward.png", "forward navigation / continue", "Continue"),
        IconSpec("play", "play.png", "start / run; ready-made quick start labs", "Start"),
        IconSpec("terminal", "terminal.png", "terminal / shell actions", "Terminal"),
        IconSpec("desktop", "desktop.png", "desktop templates / lab environments", "Desktop"),
        IconSpec("tools", "tools.png", "designer / custom labs / editing", "Designer"),
        IconSpec("refresh", "refresh.png", "restart / reload", "Refresh", derived=True),
        IconSpec("stop", "stop.png", "stop a running lab", "Stop", derived=True),
    )
}

# Meaning aliases used by status code: a NoteBanner kind or StatusPill colour maps here.
BANNER_ICONS = {"ok": "success", "warn": "warning", "error": "error", "info": None}
COLOUR_ICONS = {theme.GREEN: "success", theme.AMBER: "warning", theme.DANGER: "error"}

DEFAULT_SIZE = 16


def _asset_dirs() -> list[Path]:
    """Where `assets/icons` may live: next to this module (source checkout and wheel) and,
    in the PyInstaller build, under the unpacked bundle (`--add-data`)."""
    dirs = [Path(__file__).resolve().parent / "assets" / "icons"]
    bundle = getattr(sys, "_MEIPASS", None)
    if bundle:
        dirs.append(Path(bundle) / "practicum_desktop" / "assets" / "icons")
        dirs.append(Path(bundle) / "assets" / "icons")
    return dirs


ICON_DIRS: list[Path] = _asset_dirs()


def icon_path(name: str) -> Path | None:
    """The PNG for `name`, or None when the meaning is unknown or the asset is missing."""
    spec = ICONS.get(name)
    if spec is None:
        return None
    for directory in ICON_DIRS:
        candidate = directory / spec.file
        if candidate.is_file():
            return candidate
    return None


def icon_available(name: str) -> bool:
    return icon_path(name) is not None


@cache
def _source_pixmap(name: str) -> QPixmap:
    path = icon_path(name)
    if path is None:
        return QPixmap()
    return QPixmap(str(path))


@cache
def pixmap(
    name: str, size: int = DEFAULT_SIZE, colour: str | None = None, pad_left: int = 0
) -> QPixmap:
    """A smoothly scaled pixmap for `name`; monochrome icons (stored as black ink masks)
    can be re-tinted with `colour`. `pad_left` adds transparent margin before the icon.
    Empty (but valid) when the asset is missing, so callers never need to special-case it."""
    source = _source_pixmap(name)
    if source.isNull():
        return QPixmap()
    spec = ICONS[name]
    scaled = source.scaled(
        QSize(size, size),
        Qt.AspectRatioMode.KeepAspectRatio,
        Qt.TransformationMode.SmoothTransformation,
    )
    if (colour is None or spec.coloured) and not pad_left:
        return scaled
    result = QPixmap(scaled.width() + pad_left, scaled.height())
    result.fill(Qt.GlobalColor.transparent)
    painter = QPainter(result)
    painter.drawPixmap(pad_left, 0, scaled)
    if colour is not None and not spec.coloured:
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceIn)
        painter.fillRect(pad_left, 0, scaled.width(), scaled.height(), QColor(colour))
    painter.end()
    return result


# Rendering sizes to pre-populate a QIcon with, so Qt picks a crisp one for any device pixel
# ratio instead of scaling the 16 px version up on a high-DPI screen.
_ICON_SIZES = (16, 20, 24, 32, 48, 64)


def icon(name: str, colour: str | None = None, pad_left: int = 0) -> QIcon:
    """A QIcon for `name` (null when missing). With `colour`, the normal state is tinted and
    the disabled state is always muted, so icons on dark and disabled buttons stay visible."""
    result = QIcon()
    if not icon_available(name):
        return result
    for size in _ICON_SIZES:
        pad = round(pad_left * size / DEFAULT_SIZE)
        result.addPixmap(pixmap(name, size, colour, pad), QIcon.Mode.Normal)
        result.addPixmap(pixmap(name, size, colour, pad), QIcon.Mode.Active)
        muted = theme.MUTED_2 if not ICONS[name].coloured else None
        result.addPixmap(pixmap(name, size, muted, pad), QIcon.Mode.Disabled)
    return result


def set_button_icon(
    button: QAbstractButton,
    name: str,
    size: int = 14,
    colour: str | None = None,
    trailing: bool = False,
) -> None:
    """Puts the icon on a button (before the text, or after it with `trailing`). An icon-only
    button gets the icon's meaning as its accessible name (and tooltip, if it has none)."""
    if trailing:
        # Qt only draws button icons on the leading side; mirroring the layout direction
        # puts it after the text while the text itself is still drawn left-to-right. The
        # padding keeps a gap between the text and the icon.
        pad = 6
        button.setIcon(icon(name, colour, pad_left=pad))
        button.setIconSize(QSize(size + round(pad * size / DEFAULT_SIZE), size))
        button.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
    else:
        button.setIcon(icon(name, colour))
        button.setIconSize(QSize(size, size))
    spec = ICONS.get(name)
    if spec is not None and not button.text().strip():
        button.setAccessibleName(spec.label)
        if not button.toolTip():
            button.setToolTip(spec.label)


def icon_label(
    name: str,
    size: int = DEFAULT_SIZE,
    tooltip: str | None = None,
    colour: str | None = None,
    parent: QWidget | None = None,
) -> QLabel:
    """A fixed-size label showing the icon, with an accessible name so screen readers and
    tests can tell what it means even though it has no text."""
    label = QLabel(parent)
    label.setFixedSize(size, size)
    label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    label.setScaledContents(False)
    set_label_icon(label, name, size, colour)
    spec = ICONS.get(name)
    label.setToolTip(tooltip if tooltip is not None else (spec.label if spec else ""))
    return label


def set_label_icon(label: QLabel, name: str | None, size: int, colour: str | None = None) -> None:
    """Swaps the icon shown by a label made with `icon_label` (None clears it)."""
    if name is None or not icon_available(name):
        label.clear()
        label.setAccessibleName("")
        label.setProperty("icon", "")
        return
    label.setPixmap(pixmap(name, size, colour))
    label.setAccessibleName(ICONS[name].label)
    label.setProperty("icon", name)


def icon_html(name: str, size: int = 14) -> str:
    """An inline `<img>` for rich-text labels (never use on selectable/copyable labels)."""
    path = icon_path(name)
    if path is None:
        return ""
    return (
        f'<img src="{path.as_uri()}" width="{size}" height="{size}" '
        f'alt="{ICONS[name].label}" style="vertical-align: middle;">'
    )
