# Embedded Lab View

## User Story

As a student running a browser-accessible lab,
I want to see and use the lab's web interface inside the Practicum window itself,
so that I don't have to juggle a separate browser tab alongside my instructions.

## Why This Matters

`runtime-browser-accessible-nodes.md` and `runtime-browser-desktop-example.md` already make the API/runtime capable of exposing a lab node's web interface on a host port (for example, `examples/ubuntu-webtop.json` exposing a noVNC desktop on port 3001). Today the desktop app's only behavior is to open that URL in the user's default external browser. This story replaces that with an in-app embedded view, so the whole experience — the lab's interface and the instructions — stays inside one window.

## User Flow

1. The user starts a lab whose node(s) expose a browser-accessible port.
2. Instead of opening an external browser, the running-lab view shows that port's content in an embedded view inside the app, with a minimal URL bar for context (and a way to open it in the system browser instead, for anyone who prefers that).
3. The Lab Instructions flyout remains available, docked beside or over the embedded view, and can be shown or hidden without leaving the screen.
4. If the lab exposes more than one browser-accessible port (for example, a multi-host custom lab), the user can choose which one to view.

## Functional Requirements

- The embedded view loads whatever the container exposes on its mapped port — a desktop environment, a code editor, or a plain web app under test — without Practicum needing to know what kind of content it is.
- The Lab Instructions flyout can be toggled open/closed independently of the embedded view and preserves the student's checked-task progress while doing so.
- An explicit "open in system browser" affordance remains available as a fallback for content the embedded view can't render well (e.g., downloads, OS-level prompts).
- If a lab's containers aren't finished starting yet, the embedded view shows a waiting/boot state rather than a blank or error page.

## Acceptance Criteria

- A lab with one browser-accessible node shows that node's interface embedded in the app, not in an external browser.
- A lab with multiple browser-accessible nodes lets the user pick which one to view.
- The instructions flyout can be opened and closed without losing the embedded view's state.
- An "open in system browser" option is available from the embedded view.

## Edge Cases

- The container's web service takes time to become ready after Start — show a waiting state and retry rather than a permanent error.
- The lab has no browser-accessible ports at all (e.g., a headless-only custom lab) — the embedded view area should explain that rather than showing a blank panel.
- The embedded content requires capabilities the embedding technology doesn't support well (e.g., clipboard access, WebGL) — document this as a known limitation rather than silently failing.

## Implementation Notes

- No backend changes expected; this consumes the host port mappings already returned by the existing runtime/port endpoints.
- On the desktop stack, PySide6's `QtWebEngineWidgets` (already bundled with the installed PySide6 Addons package) provides `QWebEngineView`, which is the natural fit for the embedded view — no new dependency should be required.
- Reference design: `screen-running`'s `browser-pane` in the clickable mockup (`practicum-mockups.html`), which mocks the embedded view plus the flyout toggle.
- This directly replaces the current `webbrowser.open(...)`-based behavior in the desktop app's running-lab flow.
