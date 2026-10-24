"""Pure-Python text helpers for the dashboard and running view (no Qt): how a lab's
origin, activity time and status are worded. Kept separate so they can be unit-tested
without a QApplication and reused by every screen that shows a lab."""

from __future__ import annotations

from datetime import UTC, datetime

from practicum_desktop.api_client import LabSummary

# Plain geometric glyphs (no emoji): they render the same everywhere and don't read as
# "status" the way coloured emoji do.
ORIGIN_ICONS = {
    "imported": "\u2193",  # ↓ brought in from a file
    "quick_start": "\u25b6",  # ▶ ready-made template
    "designer": "\u25c6",  # ◆ built by hand
}


def lab_icon(origin: str) -> str:
    return ORIGIN_ICONS.get(origin, ORIGIN_ICONS["designer"])


def plural(count: int, noun: str) -> str:
    return f"{count} {noun}{'' if count == 1 else 's'}"


def origin_meta(lab: LabSummary) -> str:
    """The card's meta line: 'Imported from static-routing.json' /
    'Quick start · Ubuntu · single host' / 'Custom lab · 3 machines · 2 networks'."""
    if lab.origin == "imported":
        return f"Imported from {lab.source_file}" if lab.source_file else "Imported lab"
    if lab.origin == "quick_start":
        parts = ["Quick start"]
        if lab.node_count == 1:
            parts.append("single host")
        elif lab.node_count:
            parts.append(plural(lab.node_count, "machine"))
        return " \u00b7 ".join(parts)
    parts = ["Custom lab"]
    if lab.node_count:
        parts.append(plural(lab.node_count, "machine"))
    if lab.network_count:
        parts.append(plural(lab.network_count, "network"))
    return " \u00b7 ".join(parts)


def relative_time(moment: datetime | None, now: datetime | None = None) -> str:
    """'just now', '12 minutes ago', 'yesterday', '3 days ago', or the date for older."""
    if moment is None:
        return ""
    now = now or datetime.now(UTC)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=UTC)
    if now.tzinfo is None:
        now = now.replace(tzinfo=UTC)
    seconds = max(0, int((now - moment).total_seconds()))
    if seconds < 60:
        return "just now"
    minutes = seconds // 60
    if minutes < 60:
        return f"{plural(minutes, 'minute')} ago"
    hours = minutes // 60
    if hours < 24:
        return f"{plural(hours, 'hour')} ago"
    days = hours // 24
    if days == 1:
        return "yesterday"
    if days < 14:
        return f"{days} days ago"
    return moment.astimezone().strftime("%d %b %Y")


def activity_line(lab: LabSummary, now: datetime | None = None) -> str:
    """The card's footer time: what the lab did most recently."""
    if lab.status == "running" and lab.last_started_at:
        return f"Started {relative_time(lab.last_started_at, now)}"
    if lab.last_started_at:
        return f"Last run {relative_time(lab.last_started_at, now)}"
    if lab.created_at:
        verb = "Imported" if lab.origin == "imported" else "Created"
        return f"{verb} {relative_time(lab.created_at, now)}"
    return "Never started"
