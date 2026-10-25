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

Not started.
