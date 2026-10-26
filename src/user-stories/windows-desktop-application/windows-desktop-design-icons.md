# Use Design Icons Across the Desktop UI

## User Story

As a Practicum user,
I want the desktop UI to use the icons supplied in `design/icons.png` for common actions and states,
so that checks, errors, terminal actions, and related UI elements are easy to recognize and visually consistent.

## Why This Matters

The desktop UI currently uses text, color, and geometric glyphs for several status and action cues.
Using the supplied icon artwork gives these cues a consistent visual language while keeping the
mockup-driven interface recognizable.

## Functional Requirements

- Inspect `design/icons.png` and identify the intended icon for each supported UI meaning before
  wiring icons into the app.
- Add a shared icon-loading approach so the desktop UI references the design asset consistently
  rather than duplicating file paths or image handling across screens.
- Apply the appropriate icons to check/success states, errors/warnings, and terminal or shell
  actions wherever those meanings appear in the desktop UI.
- Preserve clear status text and accessible names or tooltips; meaning must not depend on color or
  an icon alone.
- Keep icon sizing, alignment, and contrast consistent with the existing light theme, including
  disabled and high-DPI rendering.
- Package or otherwise resolve the asset correctly in both development and the Windows release
  build.

## Acceptance Criteria

- The icons in `design/icons.png` are mapped to their intended meanings and documented in the
  shared icon definitions.
- Check/success, error/warning, and terminal/shell UI cues use the corresponding supplied icons
  consistently across applicable screens.
- Status and action meaning remains clear without relying on color alone, and icon-only controls
  expose an accessible name or tooltip.
- Icons render at the intended size and remain legible in the packaged Windows application.
- Missing or unsupported icon assets do not prevent the desktop app from launching or using its
  primary workflows.

## Dependencies

- `design/icons.png`
- Existing desktop theme and shared widgets in `desktop/src/practicum_desktop/`

## Implementation Notes

- Establish the icon-to-meaning mapping from the supplied artwork during implementation; do not
  substitute unrelated platform glyphs or emoji.
- Prefer shared theme/widget helpers so later icons can be added without screen-specific loading
  logic.

## Implementation Status

**Done 2026-10-25** (Session 6).

- **Mapping** (`desktop/src/practicum_desktop/icons.py`, `ICONS`): the 3×3 sheet, row-major -
  `success` (green check: OK/done/ready), `error` (red cross), `warning` (orange bang),
  `back`, `forward` (navigation / continue CTAs), `play` (start/run; quick start labs),
  `terminal` (shell actions, terminal templates), `desktop` (desktop template, lab
  environments), `tools` (designer / custom labs). `BANNER_ICONS` and `COLOUR_ICONS` map banner
  kinds and status-pill colours to them.
- **Assets.** `tools/slice_design_icons.py` cuts `design/icons.png` into
  `desktop/src/practicum_desktop/assets/icons/*.png` (256 px, transparent; the coloured status
  icons keep their white glyphs via a flood fill from the page edge, the black icons are stored as
  ink masks so they can be re-tinted white on dark buttons / grey when disabled and their
  cut-outs show the background). Re-run it when the sheet changes.
- **Loading.** `icons.icon()` / `pixmap()` / `icon_label()` / `set_button_icon()` /
  `icon_html()` are the only loaders (cached, multi-size QIcons for high DPI). Missing assets
  give null icons / empty pixmaps and every screen still builds (tested with the asset dir
  pointed at nothing); text glyph fallbacks remain where an icon replaced one.
- **Applied.** `widgets.MessageBanner` (icon + copyable text; now used by the gate's checks and
  start error, the running view's action feedback, the designer's validation line, the welcome
  blocked banner and `NoteBanner`), `StatusPill` (green/amber/red → check/bang/cross), the
  title-bar chip and connection-panel check lines, progress-panel ready/failed marks, the
  instructions flyout's done markers and "Mark step complete", Start / Save & Start / Start Lab
  (play), Open shell / Open PowerShell (terminal), Back links (icon-only one in the running view
  carries tooltip + accessible name), the Create screen's cards and template rows, CTA trailing
  arrows, dashboard origin tiles, the embedded view's empty state and its "open in your system
  browser" button (forward), the Windows readiness panel and the gate's Container engine panel.
  Follow-up from the user's review (same day): the painted topology cards and the designer's
  machine rows now use the icons by derived role - host → `desktop`, gateway/router →
  `forward` (a machine that forwards traffic between its networks), custom images by their link
  count like the card beside them (`widgets.NODE_ICON_NAMES`, `node_icon_name()`,
  `NodePreset.icon_name`).
- Second review round (user): Restart / Stop lab / reload and the designer's preset picker were
  still glyphs. The sheet has no refresh or stop artwork, so `tools/slice_design_icons.py` now
  **derives** two icons in the same language as the black discs (248 px disc, 24 px white
  strokes with round ends; `refresh` = ↻ ring with arrowhead, `stop` = rounded square on the
  play triangle's footprint), flagged `derived=True` in `ICONS`. Restart → refresh, Stop lab →
  stop, the embedded view's reload → refresh (icon-only, named), the preset picker shows each
  preset's icon (`NodePreset.icon_name`; Custom image → tools). Replace the derived PNGs with
  real artwork by adding cells to the sheet when design supplies them.
- Still text glyphs (no artwork, not status/action cues the story targets): remove/close (×),
  collapse (▾/▸), "+ Add …" labels.
- Accessibility: every icon-only control has a tooltip and `accessibleName`; every state also
  has words (banners, pills, labels), never colour or the icon alone.
- Packaging: `build-windows.ps1` / `Practicum.spec` add `practicum_desktop/assets` (and the
  bundled samples) with `--add-data`; `icons.ICON_DIRS` also looks under `sys._MEIPASS`.
- Tests: `test_icons.py`, `test_widgets.py` (banners, pills, buttons), plus assertions across
  the screen tests. Offscreen screenshots of every changed screen were reviewed.
- Not yet checked on a real high-DPI Windows display or in the packaged build.
