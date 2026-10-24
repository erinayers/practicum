# 03 — Desktop App Architecture (`desktop/src/practicum_desktop/`)

PySide6 (Qt 6) Windows GUI. **Pure client of the core API** — no lab logic. 24 modules
(+ bundled `samples/`), ~7,400 lines after Session 5 (2026-10-24), built screen-for-screen from
`design/practicum-mockups.html`.

```
main.py (25)            AA_ShareOpenGLContexts → QApplication → apply_theme → MainWindow
main_window.py (~520)   MainWindow: title bar + status chip + connection panel + QStackedWidget
                        of screens; owns all API calls the screens request; navigation
theme.py (~280)         design tokens → one QSS; role properties; badge_for_status (D-26)
widgets.py (~600)       Panel, Badge, Chip, RemovableChip, StatTile, StatusPill, BackLink,
                        FlowLayout, AutoSizeStack, TopologyView/TopologyCanvas, bind()/payload_of(),
                        style_frame()/edge_frame(), discard(), copyable_label(), make_button()
labels.py (~90)         pure text: origin_meta, activity_line, relative_time, lab_icon, plural
dashboard.py (~300)     WelcomeScreen, DashboardScreen, LabCard
create_lab.py (~520)    CreateLabScreen (choice cards, template radios), QuickStartScreen, StepRow
quickstart.py (~240)    TEMPLATES, QuickStartDraft, build_quick_start_lab, create_quick_start_lab
designer.py (~800)      DesignerView: Machines (preset picker) / Network topology / Networks panels,
                        lab details, address suggestion + reference, Validate, Save Lab,
                        Save & Start, load_lab() edit mode (PUT)
node_catalog.py (~190)  NodePreset/PRESETS (host, alpine, router+sysctl, web, desktop, custom),
                        next_node_id, suggest_address, preset_for_node
prestart_gate.py (~700) PreStartGateDialog: review + conflicts + real start progress (wait=false)
import_lab.py (~560)    ImportLabDialog (file picker + staged import with real start progress)
lab_file.py (~170)      read_lab_file, format_issue, sample_lab_files
running_view.py (~480)  RunningLabView: header/toolbar (lifecycle), embedded view + nodes table,
                        ManualFlyout, status bar, GET /status polling
embedded_view.py (~330) EmbeddedLabView: QWebEngineView + chrome, probe_service, waiting state
manual.py (~300)        ManualFlyout (steps, markers, Mark step complete, local progress)
progress_panel.py (~130) StartProgressPanel, summarize_progress, node_percent, step_text
node_shell.py (69)      shell_command / open_node_shell (docker exec in a new console)
api_client.py (~900)    ApiClient + result dataclasses; never raises
app_status.py (~45)     evaluate_app_status → ready | degraded | blocked (+ timeout wording)
docker_status.py (40)   check_docker() via `docker info`
startup.py (~45)        StartupWorker; check_health_with_retries (3 s, 6 s, 10 s)
workers.py (21)         CallableWorker(QThread)
dialogs.py (78)         ConfirmDialog + confirm() — THE sanctioned in-app confirmation
samples/*.json          copies of examples/ (guarded by a test)
eduLabs.code-workspace  stray VS Code workspace file — see Tigre/06 H2
```

## Screen map (MainWindow's `QStackedWidget`)

| key | widget | mockup | reached from | leaves to |
|---|---|---|---|---|
| `welcome` | `WelcomeScreen` | screen-welcome | startup with 0 labs or API blocked; deleting the last lab | create / import / dashboard link |
| `dashboard` | `DashboardScreen` | screen-dashboard | startup with ≥1 lab; back from anywhere | Open → running; Start → gate → running; Edit → designer (`load_lab`); Export → save picker; Delete/Reset (confirm) |
| `create` | `CreateLabScreen` | screen-create | Create New Lab | Quick start → quickstart; Custom Lab → designer |
| `quickstart` | `QuickStartScreen` | screen-quickstart | create | Create Lab → `create_quick_start_lab` → gate → running |
| `designer` | `DesignerView` | screen-custom | create | Save Lab → dashboard; Save & Start → gate → running |
| `running` | `RunningLabView` | screen-running | Open / any successful Start / import | ← back → home |

Modal dialogs (exec): `PreStartGateDialog` (screen-preview — *every* Start goes through it, D-4),
`ImportLabDialog` (the "Open Lab File" modal; the only native dialog is its file picker),
`ConfirmDialog`.

`HOME_SCREENS = ("welcome", "dashboard")`: a status/lab-list refresh may only switch between
these two; it never yanks the user out of the designer, the quick start form or a running lab.
`_notify(text, banner)` writes a transient note to both home screens.
`_pending_selection = (lab_id, message, open_running)` is applied after the next lab-list refresh
(land on the running view when a lab started, else dashboard + note).

## Threading pattern (use this everywhere)

Every blocking call (HTTP, subprocess) runs in a `CallableWorker(QThread)` and reports back via
`finished_call(object)`. Screens keep their workers in a list (`self._workers`, pruned at 32) —
never reassign a single attribute from inside the previous worker's completion slot (Tigre/06 #6).
`main_window._run(func, *args, on_done, **kwargs)` and `running_view._run` are the helpers.
Worker bodies that need extra context return a tuple (e.g. `_delete_named → (DeleteResult, name)`)
instead of a lambda closure as the slot.

**Signal connections — the rule that cost a day (Tigre/06 #15):** never connect a lambda that
captures `self` to a child widget's signal. It closes a Python reference cycle
(owner → child → lambda → owner) that the GC breaks in an order PySide 6.12 does not survive
(`malloc_consolidate(): unaligned fastbin chunk detected` on teardown, reproduced with a
`ManualFlyout` of two sections). Use `widgets.bind(button, self._slot, payload)` +
`payload_of(self.sender())`, connect bound methods, or give the child its own signal.

Tests replace `CallableWorker` with `ImmediateWorker` / `StalledWorker` (`tests/qt_helpers.py`)
per module (`monkeypatch.setattr(running_view, "CallableWorker", ImmediateWorker)` — and also
`embedded_view`, because each module imports the class at module level). Fixtures must stop
timers / close widgets on teardown (`view.clear(); view.close()`), otherwise a late poll tick
creates a real QThread against the fake client after the monkeypatch is undone.

## Styling rules (theme.py / widgets.py)

- One application-wide style sheet (`theme.STYLESHEET`, applied in `main.py`). Widgets are
  styled by dynamic properties: `button.setProperty("kind", "primary|secondary|danger|ghost|link|dashed")`,
  `setProperty("small", True)`, `label.setProperty("role", "h1|hero|h2|h3|title|subtitle|muted|hint|mono|label|error|ok")`,
  `frame.setProperty("panel", "true|soft|dark")`, `label.setProperty("badge", role)`,
  `label.setProperty("chip", "true|muted|count")`, `label.setProperty("banner", "ok|warn|error|info")`.
  After changing a property at runtime call `theme.restyle(widget)` (or `widgets.set_role`).
- `apply_theme` forces the **Fusion** style and `light_palette()` (Windows dark mode otherwise
  leaks into combo popups etc.); no emoji anywhere — words + colour for status, geometric glyphs
  (■ ◆ ▣ ▶ ↓ ◆, `NODE_HOST_GLYPH`/`NODE_GATEWAY_GLYPH`) for icons.
- `theme.badge_for_status(api_status) → (role, label)`: running→Running, stopped→Stopped,
  defined→**Ready**, error→Error, starting/stopping→Starting…/Stopping… (D-26).
- **Never** write `frame.setStyleSheet("QFrame { border… }")` on a container: `QLabel` is a
  `QFrame`, so every label inside gets the border too. Use `style_frame(frame, css)` /
  `edge_frame("top"|"bottom", colour, style)`, which key the rule on a unique object name.
- Transient notes: `widgets.NoteBanner.show_note(text, kind)` (dismissible; `message_label` is
  the text). Chip rows: put a `FlowLayout` inside `widgets.FlowHost` (pins its minimum height
  to the flow's height-for-width; plain QWidget hosts clip the last row). Checkable chips:
  `ToggleChip`.
- Rebuilding lists (cards, rows, chips, steps): `widgets.discard(widget)` (hide + reparent +
  deleteLater) — `deleteLater()` alone leaves ghosts painted until the event loop runs.
- Tables with cell-widget buttons: Qt does not measure cell widgets — set the column width
  (`setColumnWidth`) and the row height (`verticalHeader().setDefaultSectionSize(34)`).
- Markdown in the flyout: `manual.markdown_to_html` (QTextDocument → HTML) with `<pre>` blocks
  turned into wrapping monospace paragraphs; QLabel never wraps `<pre>`. Do **not** set
  `TextSelectableByMouse` on those labels (part of the #15 teardown crash). Wrapping labels in
  narrow panels get `QSizePolicy.Ignored` horizontally (a long token must not widen the panel);
  `QCheckBox` cannot wrap → `manual.TaskRow` (bare box + wrapping label). The running view's body
  is a `QSplitter` (lab view | flyout, min 240 px).

## ApiClient (api_client.py)

`ApiClient(base_url, timeout=3.0, lifecycle_timeout=900.0)`. Every method catches
`httpx.HTTPError` / bad status / bad JSON and returns a dataclass with `success` + `detail`.

| Method | Endpoint | Result |
|---|---|---|
| `check_health(timeout=None)` | GET /health | `HealthStatus{reachable, healthy, detail, timed_out}` |
| `list_labs()` | GET /labs | `LabsResult{labs: [LabSummary{id, name, status, origin, source_file, created_at, last_started_at, last_error, node_count, network_count, description}]}` |
| `create_lab(dict, origin="designer")` | POST /labs?origin= | `CreateLabResult` |
| `import_lab(dict, source_file=None)` | POST /labs/import?source_file= | `ImportLabResult` |
| `delete_lab(id)` | DELETE /labs/{id} | `DeleteResult` (404 = already gone; 409 detail surfaced) |
| `get_lab(id)` / `export_lab(id)` | GET /labs/{id} / GET /labs/{id}/export | `LabDefinitionResult{definition, name, status}` |
| `update_lab(id, dict)` | PUT /labs/{id} | `CreateLabResult` (422 → errors; 409 detail, e.g. running) |
| `start_lab(id, wait=True)` | POST /labs/{id}/start[?wait=false] | `StartResult{success, detail, lab_status, pending, busy}` |
| `stop_lab` / `restart_lab` / `reset_lab` | POST …/stop, /restart, /reset | `StartResult` via `_lifecycle_call` (lifecycle timeout; 409 → `busy=True`) |
| `get_status(id)` | GET /labs/{id}/status | `StatusResult{lab_status, resources, progress: [NodeProgressInfo{node_id, image, step, percent, detail}], last_error, detail}`; `.containers`, `.running_container_count` |
| `get_preview(id)` | GET /labs/{id}/preview | `PreviewResult{status, name, description, author, version, required_images, estimated_resources, topology, manual_sections, port_mappings}` |
| `check_ports` / `apply_port_recommendation` | GET/POST …/ports… | `PortCheckResult` |
| `check_networks` / `apply_subnet_recommendation` / `remove_leftover_network` | GET/POST …/networks… | `NetworkCheckResult` |
| `validate_lab(dict)` | POST /labs/validate | `ValidateLabResult` |

`NODE_STEP_LABELS`, `ORIGIN_LABELS`, `PORT_CONFLICT_REASONS`, `SUBNET_CONFLICT_REASONS` live here.

## RunningLabView (running_view.py) — the lifecycle story

- `show_lab(LabSummary)` sets header/meta/badge, loads `get_preview` (manual + port mappings →
  flyout + embedded view) when the lab changed, then `refresh()` (= `get_status`) and starts
  polling (`FAST_POLL_MS` 1000 while busy/starting/stopping, `SLOW_POLL_MS` 5000 idle; stopped
  on `hideEvent`).
- Toolbar by status (`_apply_buttons`): running → Restart, Stop lab, Reset(danger), Instructions;
  otherwise → **▶ Start lab** (emits `start_requested(lab_id)`; MainWindow opens the gate), Reset,
  Instructions. Everything lifecycle is disabled while `_busy` or status ∈ {starting, stopping}.
- `_run_lifecycle(text, api_call)`: busy on, banner "info", worker, fast polling →
  `_on_lifecycle_done`: success → badge from `lab_status`, ✅ banner (Reset gets the "original
  state … instruction progress is kept" wording), `lab_changed`; `busy` (409) → ⏳ warn banner;
  failure → ❌ error banner + badge from `lab_status`. Then `refresh()`.
- Reset → `confirm(RESET_TITLE, RESET_MESSAGE, "Reset lab", destructive=True)` first; cancel = no call.
- `_on_status_loaded`: badge, nodes table (`container_state_text`: missing → "not created"),
  status bar "N containers running", embedded view `set_lab_running` only on change,
  `center_stack` index 1 (= `StartProgressPanel`) while `starting`, error → `last_error` banner.
- Nodes table: Node / Container / State / Open shell (`bind(button, self._on_open_shell_clicked,
  container)` → `open_node_shell` worker), sized to its rows (max 6 visible).

## EmbeddedLabView (embedded_view.py)

`set_port_mappings(list[PortMappingInfo])` + `set_lab_running(bool)` drive it. `pick_default_mapping`
prefers TCP ports not in `NON_WEB_PORTS` (22, 53, 3306…). `probe_service(port)` GETs
`http://localhost:<port>/` (any status = answering; refused/timeout = not yet) and falls back to
`https://` when plain HTTP is garbled (webtop 3001). Waiting card retries every `RETRY_INTERVAL_MS`
(2500). `LocalLabPage.certificateError` accepts self-signed certs for localhost only (D-28).
`web_view_factory` is injectable (tests pass a `QTextBrowser` stand-in; `None` → system-browser
fallback card). QtWebEngine ran fine offscreen in the sandbox (`QTWEBENGINE_CHROMIUM_FLAGS=--no-sandbox`
may be needed when running as root).

## PreStartGateDialog (prestart_gate.py)

Layout = screen-preview (see story addendum). Behaviour unchanged for conflicts; Start now calls
`start_lab(wait=False)` → if `pending`, `_poll_status` every `START_POLL_MS` (1000) rendering
`StartProgressPanel` in the footer (`AutoSizeStack` page 1) until `lab_status` leaves `starting`:
running → `accept()`; else ❌ `last_error`/failed node detail, Start re-enabled. `reject()` is a
no-op while `_starting`. Public attributes tests use: `name_label`, `image_chips`, `cpu_label`,
`memory_label`, `topology_canvas.view`, `manual_label`, `conflicts_banner/table`,
`networks_banner/table`, `status_pill`, `status_label`, `footer_stack`, `progress_panel`,
`start_button`, `cancel_button`.

## QSettings

`QSettings("Practicum", "Practicum Desktop")` (monkeypatched to an ini file in tests). Keys:
`api_base_url`, `manual_progress/{lab_id}/{section_id}/{task_id}` = bool, `recent_lab_files`.

## Window

1200×760 default (the mockup's `.window`), minimum 960×620. Title bar 46 px with the "PR practicum"
brand and the status chip (● Ready / Docker unavailable / API unreachable / Checking…).
