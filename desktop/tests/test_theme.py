from __future__ import annotations

from PySide6.QtWidgets import QApplication, QLabel, QPushButton

from practicum_desktop import theme


def test_stylesheet_applies_without_parse_errors(qapp: QApplication) -> None:
    previous = qapp.styleSheet()
    try:
        theme.apply_theme(qapp)
        button = QPushButton("x")
        button.setProperty("kind", "primary")
        label = QLabel("y")
        label.setProperty("badge", "running")
        button.ensurePolished()
        label.ensurePolished()
        assert qapp.styleSheet() == theme.STYLESHEET
    finally:
        qapp.setStyleSheet(previous)


def test_restyle_repolishes_after_property_change(qapp: QApplication) -> None:
    label = QLabel("z")
    label.setProperty("banner", "ok")
    theme.restyle(label)
    label.setProperty("banner", "error")
    theme.restyle(label)
    assert label.property("banner") == "error"


def test_every_badge_role_has_colours() -> None:
    for status, (role, _label) in theme.STATUS_BADGES.items():
        assert role in theme.BADGE_COLOURS, status
