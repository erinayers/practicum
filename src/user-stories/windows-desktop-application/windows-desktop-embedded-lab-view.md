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

## Implementation Status

Done 2026-10-24 (Session 5) in `desktop/src/practicum_desktop/embedded_view.py` (`EmbeddedLabView`), hosted by the running view's left pane.

- `QWebEngineView` (PySide6 QtWebEngine, D-16) renders the published port inside the app; a browser chrome gives ↻ reload, the URL, a port picker when the lab maps more than one TCP port (the most web-like port is preselected; well-known non-web ports such as 22 are listed but not chosen by default), and ↗ "open in system browser".
- Before loading, `probe_service` GETs `http://localhost:<port>/` (any HTTP status counts as answering) and falls back to `https://` when the port accepts connections but garbles plain HTTP (webtop's 3001); self-signed certificates are accepted for localhost only (`LocalLabPage`, D-28). While the container's service is not answering yet the pane shows a waiting card and retries every 2.5 s.
- Labs without browser-accessible ports get an explanation pointing at Open shell; a stopped lab says so; when QtWebEngine is not importable the pane offers the system browser instead, so the rest of the app keeps working.
- The instructions flyout is toggled independently (`Instructions` button / × in the flyout) without reloading the page or losing checked tasks.
- Known limitations (documented, not fixed): clipboard/WebGL/downloads inside QtWebEngine behave like Chromium's defaults; `main.py` sets `AA_ShareOpenGLContexts` as QtWebEngine requires.
- Tests: `desktop/tests/test_embedded_view.py` (13), plus the embedded-view cases in `test_running_view.py`. QtWebEngine itself was exercised offscreen in the sandbox (a page loads); the Windows run with webtop on 3000/3001 is pending.

## Update 2026-10-24 (user report: "400 Bad Request — The plain HTTP request was sent to HTTPS port")

The embedded view had loaded `http://localhost:3001` on a webtop lab: nginx's 400 counted as "the port answers over HTTP", and the picker could prefer 3001 over 3000 once the gate had re-mapped 3000 (the fixed mapping is appended after 3001). Fixed: `probe_service` treats a 400 whose body says "plain HTTP request was sent to HTTPS port" as a TLS port and retries `https://`; `pick_default_mapping` scores ports (plain-web first, TLS-only ports such as 443/8443/3001 next, non-web ports last) regardless of mapping order. Tests: `test_probe_treats_nginx_plain_http_on_tls_port_as_https`, `test_default_mapping_prefers_web_like_tcp_ports`.

### Addendum 2026-10-25 — several desktops in one lab (user request)

A lab with two Ubuntu Desktop machines showed only one of them: the picker above the lab view
listed raw host ports ("localhost:3002 → 3000/tcp") with no hint which machine they belonged to.
Now the preview carries each machine's published ports (`TopologyNodeInfo.port_mappings`,
`PortMappingInfo.node_id`) and the picker lists them **by machine** - "desktop-1 ·
localhost:3000", "desktop-1 · localhost:3001 (https)", "desktop-2 · localhost:3002", … - with
the first machine's plain web port selected by default and the waiting/not-running messages
naming the machine. The lab-wide flat list remains the fallback for labs whose preview has no
per-node ports. In the designer, a second machine from a preset that publishes ports (Ubuntu
Desktop, Web server) is given the next free host ports (`node_catalog.free_host_ports`) so the
lab no longer needs a port fix in the gate first. Tests: `test_embedded_view.py`
(`test_picker_lists_machines_by_name_and_switches_between_desktops`, waiting message, labels),
`test_running_view.py::test_two_desktops_are_offered_by_machine_name_in_the_lab_view`,
`test_api_client.py::test_get_preview_carries_each_machines_published_ports`,
`test_designer.py::test_second_desktop_gets_free_host_ports_instead_of_clashing`.
