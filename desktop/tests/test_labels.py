from __future__ import annotations

from datetime import UTC, datetime, timedelta

from practicum_desktop.api_client import LabSummary
from practicum_desktop.labels import activity_line, lab_icon, origin_meta, plural, relative_time

NOW = datetime(2026, 10, 24, 12, 0, tzinfo=UTC)


def test_plural() -> None:
    assert plural(1, "lab") == "1 lab"
    assert plural(0, "lab") == "0 labs"
    assert plural(3, "machine") == "3 machines"


def test_relative_time_wording() -> None:
    assert relative_time(None, NOW) == ""
    assert relative_time(NOW - timedelta(seconds=20), NOW) == "just now"
    assert relative_time(NOW - timedelta(minutes=1), NOW) == "1 minute ago"
    assert relative_time(NOW - timedelta(minutes=12), NOW) == "12 minutes ago"
    assert relative_time(NOW - timedelta(hours=3), NOW) == "3 hours ago"
    assert relative_time(NOW - timedelta(days=1, hours=2), NOW) == "yesterday"
    assert relative_time(NOW - timedelta(days=3), NOW) == "3 days ago"
    assert relative_time(NOW - timedelta(days=40), NOW) == "14 Sep 2026"
    assert relative_time(NOW + timedelta(minutes=5), NOW) == "just now"  # clock skew


def test_relative_time_accepts_naive_timestamps() -> None:
    assert relative_time(datetime(2026, 10, 24, 11, 30), NOW) == "30 minutes ago"


def test_origin_meta_lines() -> None:
    assert (
        origin_meta(LabSummary("a", "A", "defined", "imported", "x.json")) == "Imported from x.json"
    )
    assert origin_meta(LabSummary("a", "A", "defined", "imported")) == "Imported lab"
    assert origin_meta(LabSummary("a", "A", "defined", "quick_start", node_count=1)) == (
        "Quick start \u00b7 single host"
    )
    assert origin_meta(LabSummary("a", "A", "defined", "quick_start", node_count=2)) == (
        "Quick start \u00b7 2 machines"
    )
    assert origin_meta(
        LabSummary("a", "A", "defined", "designer", node_count=3, network_count=2)
    ) == ("Custom lab \u00b7 3 machines \u00b7 2 networks")
    assert origin_meta(LabSummary("a", "A", "defined", "designer")) == "Custom lab"


def test_activity_line_prefers_the_most_recent_event() -> None:
    running = LabSummary("a", "A", "running", last_started_at=NOW - timedelta(minutes=12))
    assert activity_line(running, NOW) == "Started 12 minutes ago"
    stopped = LabSummary("a", "A", "stopped", last_started_at=NOW - timedelta(days=1))
    assert activity_line(stopped, NOW) == "Last run yesterday"
    fresh = LabSummary("a", "A", "defined", "imported", created_at=NOW - timedelta(minutes=20))
    assert activity_line(fresh, NOW) == "Imported 20 minutes ago"
    built = LabSummary("a", "A", "defined", "designer", created_at=NOW - timedelta(minutes=20))
    assert activity_line(built, NOW) == "Created 20 minutes ago"
    assert activity_line(LabSummary("a", "A", "defined"), NOW) == "Never started"


def test_lab_icons_by_origin() -> None:
    assert lab_icon("imported") != lab_icon("quick_start") != lab_icon("designer")
    assert lab_icon("unknown") == lab_icon("designer")
