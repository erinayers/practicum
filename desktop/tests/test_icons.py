from __future__ import annotations

from pathlib import Path

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QPushButton

from practicum_desktop import icons, theme
from practicum_desktop.icons import (
    BANNER_ICONS,
    COLOUR_ICONS,
    ICONS,
    icon,
    icon_available,
    icon_html,
    icon_label,
    icon_path,
    pixmap,
    set_button_icon,
    set_label_icon,
)

SHEET_NAMES = (
    "success",
    "error",
    "warning",
    "back",
    "forward",
    "play",
    "terminal",
    "desktop",
    "tools",
)
DERIVED_NAMES = ("refresh", "stop")  # drawn to match the sheet, not on it
ALL_NAMES = SHEET_NAMES + DERIVED_NAMES


def test_every_design_icon_is_mapped_to_a_meaning_and_shipped() -> None:
    assert tuple(ICONS) == ALL_NAMES  # the nine cells of design/icons.png, row-major + derived
    assert {n for n, s in ICONS.items() if s.derived} == set(DERIVED_NAMES)
    for name in ALL_NAMES:
        spec = ICONS[name]
        assert spec.meaning and spec.label
        path = icon_path(name)
        assert path is not None and path.is_file(), name
        assert path.parent == Path(icons.__file__).resolve().parent / "assets" / "icons"
        assert icon_available(name)
    assert {n for n, s in ICONS.items() if s.coloured} == {"success", "error", "warning"}
    assert icon_path("nope") is None and not icon_available("nope")


def test_meaning_aliases_cover_banner_kinds_and_status_colours() -> None:
    assert BANNER_ICONS == {"ok": "success", "warn": "warning", "error": "error", "info": None}
    assert COLOUR_ICONS == {theme.GREEN: "success", theme.AMBER: "warning", theme.DANGER: "error"}


def test_pixmaps_scale_and_monochrome_icons_can_be_tinted() -> None:
    small = pixmap("terminal", 16)
    assert (small.width(), small.height()) == (16, 16)
    big = pixmap("terminal", 48)
    assert big.width() == 48
    white = pixmap("terminal", 24, "white").toImage()
    # A tinted pixel keeps the icon's alpha but takes the colour: the opaque centre of the
    # terminal frame border is white now, and fully transparent pixels stay transparent.
    opaque = [
        white.pixelColor(x, y)
        for x in range(white.width())
        for y in range(white.height())
        if white.pixelColor(x, y).alpha() > 250
    ]
    assert opaque and all(c.red() > 240 and c.green() > 240 and c.blue() > 240 for c in opaque)
    assert white.pixelColor(0, 0).alpha() == 0
    # Coloured artwork is never re-tinted: the circle's green rim stays green.
    green = pixmap("success", 24, "white").toImage()
    rim = green.pixelColor(2, 12)
    assert rim.alpha() > 200 and rim.green() > 150 and rim.red() < 100


def test_qicon_has_normal_and_disabled_states() -> None:
    result = icon("play", colour="white")
    assert isinstance(result, QIcon) and not result.isNull()
    assert not result.pixmap(16, QIcon.Mode.Disabled).isNull()
    assert icon("missing-meaning").isNull()


def test_set_button_icon_gives_icon_only_buttons_an_accessible_name() -> None:
    button = QPushButton("")
    set_button_icon(button, "back")
    assert not button.icon().isNull()
    assert button.accessibleName() == "Back"
    assert button.toolTip() == "Back"

    labelled = QPushButton("Start lab")
    set_button_icon(labelled, "play", trailing=True)
    assert labelled.accessibleName() == ""  # the text already says it
    assert labelled.layoutDirection().name == "RightToLeft"  # icon after the text


def test_icon_label_and_set_label_icon_carry_the_meaning() -> None:
    label = icon_label("warning", 16, "Needs attention")
    assert label.toolTip() == "Needs attention"
    assert label.accessibleName() == "Warning"
    assert label.property("icon") == "warning"
    assert label.pixmap() is not None and not label.pixmap().isNull()

    set_label_icon(label, "success", 16)
    assert label.property("icon") == "success" and label.accessibleName() == "OK"
    set_label_icon(label, None, 16)
    assert label.property("icon") == "" and label.pixmap().isNull()


def test_icon_html_is_an_img_tag_with_alt_text() -> None:
    html = icon_html("error", 13)
    assert html.startswith('<img src="file://')
    assert 'alt="Error"' in html and 'width="13"' in html
    assert icon_html("nope") == ""


def test_missing_assets_degrade_to_empty_icons_not_errors(monkeypatch) -> None:
    monkeypatch.setattr(icons, "ICON_DIRS", [Path("/nonexistent/icons")])
    icons._source_pixmap.cache_clear()
    icons.pixmap.cache_clear()
    try:
        assert icon_available("success") is False
        assert icon("success").isNull()
        assert pixmap("success", 16).isNull()
        assert icon_html("success") == ""
        button = QPushButton("")
        set_button_icon(button, "terminal")  # no exception, still labelled
        assert button.accessibleName() == "Terminal"
        label = icon_label("success", 16)
        assert label.property("icon") == ""
    finally:
        icons._source_pixmap.cache_clear()
        icons.pixmap.cache_clear()
