from __future__ import annotations

from datetime import UTC, datetime, timedelta

from practicum_desktop.api_client import LabSummary
from practicum_desktop.dashboard import DashboardScreen, LabCard, WelcomeScreen

NOW = datetime(2026, 10, 24, 12, 0, tzinfo=UTC)


def _lab(status: str = "running", **overrides) -> LabSummary:
    values = {
        "id": "lab-1",
        "name": "Build a Python API",
        "status": status,
        "origin": "imported",
        "source_file": "python-api-lab.json",
        "created_at": NOW - timedelta(hours=2),
        "last_started_at": NOW - timedelta(minutes=12),
    }
    values.update(overrides)
    return LabSummary(**values)


# ----- welcome ------------------------------------------------------------------------------


def test_welcome_hides_dashboard_link_without_labs_and_counts_them_otherwise() -> None:
    screen = WelcomeScreen()
    screen.set_lab_count(0)
    assert screen.dashboard_link.isHidden()

    screen.set_lab_count(4)

    assert screen.dashboard_link.isHidden() is False
    assert screen.dashboard_link.text() == "You have 4 labs \u00b7 View your labs dashboard \u2192"


def test_welcome_emits_its_three_actions() -> None:
    screen = WelcomeScreen()
    fired: list[str] = []
    screen.create_requested.connect(lambda: fired.append("create"))
    screen.import_requested.connect(lambda: fired.append("import"))
    screen.dashboard_requested.connect(lambda: fired.append("dashboard"))
    screen.set_lab_count(1)

    screen.create_button.click()
    screen.import_button.click()
    screen.dashboard_link.click()

    assert fired == ["create", "import", "dashboard"]


def test_blocked_welcome_explains_and_disables_api_actions() -> None:
    screen = WelcomeScreen()

    screen.set_blocked("API unreachable")

    assert screen.blocked_banner.text() == "API unreachable"
    assert not screen.create_button.isEnabled()
    assert not screen.import_button.isEnabled()

    screen.set_blocked(None)

    assert screen.blocked_banner.isHidden()
    assert screen.create_button.isEnabled()


# ----- cards ----------------------------------------------------------------------------------


def test_running_card_offers_export_and_open() -> None:
    card = LabCard(_lab("running"), NOW)

    assert list(card.buttons) == ["Export", "Open"]
    assert card.badge.text() == "\u25cf Running"
    assert card.meta_label.text() == "Imported from python-api-lab.json"
    assert card.time_label.text() == "Started 12 minutes ago"


def test_stopped_card_offers_export_edit_delete_and_start() -> None:
    card = LabCard(
        _lab("stopped", origin="designer", source_file=None, node_count=3, network_count=2), NOW
    )

    assert list(card.buttons) == ["Export", "Edit", "Delete", "Start"]
    assert card.buttons["Start"].property("kind") == "primary"
    assert card.meta_label.text() == "Custom lab \u00b7 3 machines \u00b7 2 networks"
    assert card.time_label.text() == "Last run 12 minutes ago"


def test_ready_card_for_never_started_quick_start() -> None:
    card = LabCard(
        _lab("defined", origin="quick_start", source_file=None, last_started_at=None, node_count=1),
        NOW,
    )

    assert card.badge.text() == "\u25cf Ready"
    assert card.meta_label.text() == "Quick start \u00b7 single host"
    assert card.time_label.text() == "Created 2 hours ago"
    assert list(card.buttons) == ["Export", "Edit", "Delete", "Start"]


def test_error_card_offers_reset_and_shows_the_reason() -> None:
    card = LabCard(_lab("error", last_error="node 'router': could not pull image"), NOW)

    assert list(card.buttons) == ["Export", "Edit", "Delete", "Reset", "Start"]
    assert card.buttons["Reset"].property("kind") == "danger"
    assert card.badge.text() == "\u25cf Error"


def test_transitional_card_only_offers_open() -> None:
    assert list(LabCard(_lab("starting"), NOW).buttons) == ["Open"]
    assert LabCard(_lab("starting"), NOW).badge.text() == "\u25cf Starting\u2026"
    assert list(LabCard(_lab("stopping"), NOW).buttons) == ["Open"]


def test_card_buttons_emit_the_lab_id() -> None:
    card = LabCard(_lab("error"), NOW)
    fired: list[tuple[str, str]] = []
    card.open_requested.connect(lambda lab_id: fired.append(("open", lab_id)))
    card.start_requested.connect(lambda lab_id: fired.append(("start", lab_id)))
    card.delete_requested.connect(lambda lab_id: fired.append(("delete", lab_id)))
    card.reset_requested.connect(lambda lab_id: fired.append(("reset", lab_id)))
    card.edit_requested.connect(lambda lab_id: fired.append(("edit", lab_id)))
    card.export_requested.connect(lambda lab_id: fired.append(("export", lab_id)))

    card.buttons["Export"].click()
    card.buttons["Edit"].click()
    card.buttons["Delete"].click()
    card.buttons["Reset"].click()
    card.buttons["Start"].click()

    assert fired == [
        ("export", "lab-1"),
        ("edit", "lab-1"),
        ("delete", "lab-1"),
        ("reset", "lab-1"),
        ("start", "lab-1"),
    ]


# ----- dashboard ------------------------------------------------------------------------------


def test_dashboard_lays_cards_out_in_two_columns_and_relays_signals() -> None:
    screen = DashboardScreen()
    labs = [_lab("running", id=f"lab-{i}", name=f"Lab {i}") for i in range(3)]
    fired: list[str] = []
    screen.open_requested.connect(fired.append)

    screen.set_labs(labs, NOW)

    assert [card.lab.id for card in screen.cards] == ["lab-0", "lab-1", "lab-2"]
    positions = [screen.grid.getItemPosition(i)[:2] for i in range(3)]
    assert positions == [(0, 0), (0, 1), (1, 0)]
    screen.card_for("lab-2").buttons["Open"].click()
    assert fired == ["lab-2"]

    screen.set_labs(labs[:1], NOW)
    assert len(screen.cards) == 1
    assert screen.card_for("lab-2") is None


def test_dashboard_header_actions_and_messages() -> None:
    screen = DashboardScreen()
    fired: list[str] = []
    screen.create_requested.connect(lambda: fired.append("create"))
    screen.import_requested.connect(lambda: fired.append("import"))

    screen.create_button.click()
    screen.import_button.click()
    screen.show_message("Deleting\u2026", "info")

    assert fired == ["create", "import"]
    assert screen.message_label.text() == "Deleting\u2026"
    assert screen.message_label.isHidden() is False
    screen.show_message("")
    assert screen.message_label.isHidden()

    screen.set_actions_enabled(False)
    assert not screen.create_button.isEnabled()
