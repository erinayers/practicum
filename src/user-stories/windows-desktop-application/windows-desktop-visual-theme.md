# Desktop Visual Theme (Mockup Look and Feel)

## User Story

As a user of the Practicum desktop app,
I want every screen to look like the clickable mockup — one window, a title bar, cards, pills and consistent buttons —
so that the app feels like a finished product rather than a stack of default Qt forms.

## Why This Matters

Phase 7 is "mockup-driven", but the app was a single tall form with default widgets. Each screen story (dashboard, lifecycle controls, embedded view, designer) needed the same visual language, so it is defined once here instead of per story.

## User Flow

1. The window opens at the mockup's size (1200×760) with the brand title bar ("PR practicum") and a connection status chip on the right; clicking the chip shows the API/Docker details, the API URL and Retry.
2. Screens swap inside the window: welcome, dashboard, create, quick start, designer, running lab. Back links and bottom bars follow the mockup.
3. Status is shown with the mockup's badges (Running green, Stopped grey, Ready blue, Error red, Starting…/Stopping… amber), chips, stat tiles and bordered panels.

## Functional Requirements

- One application-wide style sheet translates the mockup's design tokens (colours, radii, type sizes) to Qt; widgets are styled by role properties (`kind`, `role`, `panel`, `badge`, `chip`, `banner`) rather than per-widget style sheets.
- Shared building blocks exist for panels, badges, chips, stat tiles, status pills, back links, bottom bars, flow layouts and the schematic topology view, and are reused by every screen.
- The API lab statuses map to badge labels as: `running` → Running, `stopped` → Stopped, `defined` → Ready, `error` → Error, `starting`/`stopping` → Starting…/Stopping… (decision D-26; the mockup's "Draft" has no real counterpart because every stored lab is validated).
- The connection/readiness information from `windows-desktop-launch.md` stays available (status chip + collapsible panel) without occupying the screen.
- Container style sheets never use bare type selectors that would also restyle child labels (`QLabel` is a `QFrame`).

## Acceptance Criteria

- All six screens render inside the one window with the title bar and status chip.
- Status badges, primary/secondary/danger buttons and panels look the same on every screen that uses them.
- The connection panel is hidden by default, opened by the chip, and opened automatically when the API is unreachable.

## Edge Cases

- Emoji glyphs (icons) depend on the platform font; Windows renders them with Segoe UI Emoji.
- High-DPI scaling is Qt 6's default; no per-widget pixel tuning is needed.

## Implementation Notes

- `desktop/src/practicum_desktop/theme.py` (tokens, `STYLESHEET`, `apply_theme`, `badge_for_status`), `widgets.py` (`Panel`, `Badge`, `Chip`, `StatTile`, `StatusPill`, `BackLink`, `FlowLayout`, `TopologyView`, `bind`, `style_frame`), `main.py` (`apply_theme`), `main_window.py` (title bar, screen stack).
- Reference design: `design/practicum-mockups.html` (`:root` tokens, `.titlebar`, `.btn-*`, `.panel`, `.lab-status`, `.chip`, `.stat-tile`, `.bottom-bar`).

## Implementation Status

Done 2026-10-24 (Session 5). Tests: `desktop/tests/test_theme.py`, `desktop/tests/test_widgets.py`. Screens reviewed as offscreen screenshots against the mockup; a Windows run is still pending.

## Update 2026-10-24 (user feedback)

- No emoji anywhere: status is words + colour (`OK` / `Problem` lines in the connection panel, coloured banners, the status chip's dot); icons are plain geometric glyphs (■ ◆ ▣ ▶ ↓ ◆) that render identically on every platform.
- The app now forces the **Fusion** style and a fixed **light palette** (`theme.light_palette`), so Windows dark mode no longer leaks into unstyled parts — the connect form's dropdown had rendered black text on a black popup. The combo-box popup is also styled explicitly (`QComboBox QAbstractItemView`), and text-field selection colours no longer propagate to combo popups.
