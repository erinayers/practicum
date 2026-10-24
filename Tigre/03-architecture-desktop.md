# 03 — Desktop App Architecture (`desktop/src/practicum_desktop/`)

PySide6 (Qt 6) Windows GUI. **Pure client of the core API** — no lab logic. 15 modules
(+ bundled `samples/`), ~2,500 lines.

```
main.py (18)          QApplication + MainWindow; console script `practicum-desktop`
main_window.py (~400) MainWindow(QMainWindow) — the single screen today
api_client.py (~520)  ApiClient (httpx) + result dataclasses; never raises, returns success flags
import_lab.py (~430)  ImportLabDialog — "Open Lab File" modal + staged import/start progress;
                      RecentLabFiles (QSettings); LabFileRowDelegate; ImportOutcome
lab_file.py (~170)    read_lab_file() (specific file errors), format_issue(), sample_lab_files()
node_shell.py (~75)   shell_command() / open_node_shell() — docker exec in a new console window
samples/*.json        static-routing / ubuntu-quickstart / ubuntu-webtop — copies of examples/
app_status.py (40)    evaluate_app_status(api, docker) -> AppStatus(readiness ready|degraded|blocked)
docker_status.py (36) check_docker() -> DockerStatus via `docker info` (5 s timeout)
startup.py (28)       StartupWorker(QThread): health + docker + list_labs off the UI thread
workers.py (21)       CallableWorker(QThread): run any callable, emit finished_call(result)
dialogs.py (78)       ConfirmDialog + confirm() — THE sanctioned in-app confirmation
prestart_gate.py (244) PreStartGateDialog — mandatory review screen before Start
designer.py (408)     DesignerDialog — instructor form: nodes / networks / connections
manual.py (141)       ManualFlyout(QDockWidget) — manual sections + checkable tasks
quickstart.py (97)    UBUNTU_QUICK_START_LAB dict + (unused/broken) subnet-picking helpers
eduLabs.code-workspace  stray VS Code workspace file (personal paths) — see Tigre/06
```

## Threading pattern (use this everywhere)

Every blocking call (HTTP, subprocess) runs in a `QThread` subclass and reports back via a
`Signal(object)`:

```python
self._x_worker = CallableWorker(self._api_client.some_call, arg1, arg2)
self._x_worker.finished_call.connect(self._on_some_call_done)
self._x_worker.start()
```

- Keep a reference on `self` (else the QThread is GC'd mid-run).
- `StartupWorker` is the special-case one: emits `finished_check(AppStatus, LabsResult|None)`.
- Tests replace `CallableWorker` with a synchronous `ImmediateWorker` via
  `monkeypatch.setattr(prestart_gate, "CallableWorker", ImmediateWorker)` — new dialogs should
  import `CallableWorker` at module level so the same trick works.
- Caveat: workers are reassigned without waiting for the previous one (see Tigre/06 #6).

## ApiClient (api_client.py)

`ApiClient(base_url="http://127.0.0.1:8000", timeout=3.0)`. Every method catches
`httpx.HTTPError` / bad status / bad JSON and returns a dataclass with `success: bool` and
`detail: str`. Methods and results:

| Method | Endpoint | Result dataclass |
|---|---|---|
| `check_health()` | GET /health | `HealthStatus{reachable, healthy, detail}` |
| `list_labs()` | GET /labs | `LabsResult{success, labs: [LabSummary{id,name,status}], detail}` |
| `check_ports(lab_id)` | GET /labs/{id}/ports | `PortCheckResult{success, has_conflicts, conflicts:[PortConflict], detail}` |
| `apply_port_recommendation(lab_id, node_id, host_port, protocol)` | POST …/ports/apply-recommendation | `PortCheckResult` (409 detail surfaced) |
| `validate_lab(dict)` | POST /labs/validate | `ValidateLabResult{success, valid, errors:[FieldIssue], detail}` |
| `create_lab(dict)` | POST /labs | `CreateLabResult{success, lab_id, errors:[FieldIssue], detail}` (parses 201 and 422) |
| `start_lab(lab_id)` | POST /labs/{id}/start | `StartResult{success, detail}` (first runtime error message as detail) |
| `get_preview(lab_id)` | GET /labs/{id}/preview | `PreviewResult{success, name, description, author, version, required_images, estimated_resources: EstimatedResourcesInfo{total_cpu,total_memory_mb}, topology: TopologyInfo{nodes,networks,interfaces}, manual_sections:[ManualSectionInfo{id,title,content_markdown,tasks:[ManualTaskInfo]}], port_mappings:[PortMappingInfo{host,container,protocol}], detail}` |

| `check_networks(lab_id)` | GET /labs/{id}/networks | `NetworkCheckResult{success, has_conflicts, conflicts:[SubnetConflict], detail}` — `success=False` also when the API's own `error` is set (Docker unreachable) |
| `apply_subnet_recommendation(lab_id, network_id)` | POST …/networks/apply-recommendation | `NetworkCheckResult` (409 detail surfaced) |
| `remove_leftover_network(lab_id, network_name)` | POST …/networks/remove-leftover | `NetworkCheckResult` (lifecycle timeout; 409 detail surfaced) |
| `get_status(lab_id)` | GET /labs/{id}/status | `StatusResult{success, lab_status, resources:[ResourceStatusInfo{kind,id,name,exists,status,error}], detail}`; `.containers` property |
| `reset_lab(lab_id)` | POST /labs/{id}/reset | `StartResult{success, detail}` (lifecycle timeout) |
| `import_lab(dict)` | POST /labs/import | `ImportLabResult{success, lab_id, lab_name, errors:[FieldIssue], detail}` — `success` only when stored; validation rejection → `errors`; transport/422/odd body → `detail` only |

`ApiClient(base_url, timeout=3.0, lifecycle_timeout=900.0)` — `start_lab` uses
`lifecycle_timeout` (Tigre/06 #3 fix); future `stop/reset/restart` wrappers must too.

**Not yet wrapped** (needed by Phase 7): `stop_lab`, `export_lab`, delete (no endpoint exists
server-side either). `SUBNET_CONFLICT_REASONS` joins `PORT_CONFLICT_REASONS` here.

`PORT_CONFLICT_REASONS` dict (reason code → human text) lives here and is shared by
`main_window.py` and `prestart_gate.py`.

## MainWindow (main_window.py) — current single-screen layout, top to bottom

1. Readiness banner `Status: Ready|Degraded|Blocked`, API line (✅/❌ + detail), Docker line,
   `next_action` copyable label.
2. `API base URL:` `QLineEdit` + **Retry** button → saves `api_base_url` to QSettings, rebuilds
   `ApiClient`, reruns `check_status()`.
3. `Labs:` `QListWidget` — items `"{name} ({status})"`; parallel `self._lab_ids` list. A
   placeholder row "No labs defined yet." is added when empty (row index with no id).
4. **New Lab…** → `DesignerDialog.exec()`; on Accepted → `check_status()` (reloads list).
   **Import Lab File…** (same row) → `ImportLabDialog.exec()`; then if `outcome.gate_required`
   → `PreStartGateDialog`; then `_pending_selection = (lab_id, message, show_manual)` +
   `check_status()`; `_on_status_checked` → `_apply_pending_selection` selects the lab row, sets
   `start_result_label` ("✅ '<name>' imported and started." / "'<name>' imported. Select it below
   and use Start when ready.") and shows the manual flyout when started. `_last_status` (AppStatus)
   is kept so the import dialog can show its "API not available" banner.
5. **Quick Start: Ubuntu** → `CallableWorker(api.create_lab, UBUNTU_QUICK_START_LAB)` →
   status label → `check_status()`.
6. **View Manual** (enabled when a lab is selected) → toggles `ManualFlyout` visibility.
7. `Port Conflicts:` table (Node / Host Port / Issue / Recommended with "Use <port>" buttons).
8. `Browser Access:` table (Host Port / Maps To / "Open in Browser" → `webbrowser.open
   (http://localhost:{port})`) — filled from `PreviewResult.port_mappings`.
8b. `Lab Nodes:` table (Node / Container / State / **Open shell**) — filled by `_refresh_nodes()`
   → `get_status` on row change and after Start; button enabled only when the container is
   `running`; click → `open_node_shell(name, node_id)` in a worker → `nodes_status_label`
   (failure text + copyable command).
9. **Start Selected Lab…** → opens `PreStartGateDialog`; on Accepted shows "✅ Lab started.";
   then re-runs port check and `_refresh_nodes()`.
10. `ManualFlyout` docked right (hidden by default).

Selecting a lab row (`_on_lab_row_changed`) fires two workers: `check_ports` and `get_preview`
(the latter feeds both the manual flyout and the browser-access table).

QSettings: `QSettings("Practicum", "Practicum Desktop")`. Keys: `api_base_url`,
`manual_progress/{lab_id}/{section_id}/{task_id}` = bool, `recent_lab_files` = list[str]
(newest first, max 8; a one-element list may come back as a plain `str` — `RecentLabFiles`
normalises).

Window: title "Practicum", default size 560×760 (small; the mockups imply a much larger
multi-screen app — Phase 7 will restructure this).

## PreStartGateDialog (prestart_gate.py) — done, the "single authority" for Start

- Constructor kicks off `get_preview` and `check_ports` in parallel workers.
- Shows: name (bold 16px), description, `author · version`, required images (comma list),
  CPU `"{n} vCPU"`/`Unknown`, Memory `"{n} MB"`/`Unknown`, read-only topology table
  (Node/Network/Address — one row per interface), manual step count sentence or "This lab has
  no manual.", Port Conflicts group (banner + table with "Use <port>" buttons), status label,
  Cancel / **Start Lab** buttons.
- **Network Conflicts** group (2026-10-23): banner + table Network / Subnet / Issue (stretch) /
  Fix. Issue text per reason (`_subnet_issue_text`); Fix cell = buttons **Remove leftover**
  (`overlaps_leftover`, `confirm(destructive)` → `remove_leftover_network`), **Reset '<name>'**
  (`overlaps_other_lab`, confirm → `reset_lab(owner)` then `check_networks` in one worker), and
  **Use <subnet>** (any reason with a recommendation → `apply_subnet_recommendation`, then the
  banner adds "addresses were remapped… manual may still mention the original addresses" and the
  preview is reloaded so the topology table shows the new addresses). `_run_network_fix` drives
  all three through `_on_network_fix_done`.
- Start Lab enabled only when **both** checks have answered (`_ports_known`, `_networks_known`)
  and both `self._conflicts` and `self._subnet_conflicts` are empty (`_update_start_enabled`).
  A failed network check shows "Could not check Docker networks: … Start stays disabled".
  Applying a recommendation re-renders from the server's fresh response.
- Start → `start_lab` worker → on success `accept()`; on failure shows `❌ detail` and
  re-enables Start if still conflict-free.
- Docstring states: every entry point that can start a lab (dashboard, import-and-launch)
  **must reuse this dialog**, not reimplement the gate.
- Not yet shown: image local-vs-pull status (no API support), manual preview content (only a
  count).

## ImportLabDialog (import_lab.py) — done, the import-and-launch flow

Two pages in a `QStackedWidget`:
- **Choose**: title "Open Lab File", optional amber banner when `api_available=False`
  (Open/Browse disabled), `files_list` (`QListWidget` + `LabFileRowDelegate`: file icon, bold
  name, muted hint "Recent · 2 KB" / "Sample lab · 1 KB" / "Recent · file not found" (row disabled));
  item text = file name, `FILE_HINT_ROLE` (UserRole) = hint, tooltip = full path. Recent files
  first, then bundled samples not already in recent. **Browse computer…** →
  `QFileDialog.getOpenFileName(self, "Open Lab File", <dir of newest recent | home>,
  "Practicum lab files (*.json);;All files (*)")` — picking continues immediately. **Open**
  (default button, also double-click) for list rows.
- **Progress**: `stage_label` (Reading lab file… 10 % → Importing lab definition… 35 % →
  Checking host ports and networks… 60 % → Starting containers… 85 % (+ `START_HINT` about image pulls) →
  Lab started 100 %), `file_label` (path, then lab name), `progress_bar`, `detail_label`
  (❌ message + hint), `errors_box` (`QPlainTextEdit`, "• nodes[0].image: Field required" lines),
  **Choose another file** (only while `outcome is None`), **Close** (disabled while busy;
  `reject()`/`closeEvent` are ignored while a stage is in flight).

Flow (each stage a `CallableWorker`, module-level import so tests swap in `ImmediateWorker`):
`read_lab_file` → `api.import_lab` → (`outcome` set, recent list updated) → `api.check_ports` →
`api.check_networks` → conflicts **or check failure** in either ⇒ `_hand_over_to_gate()`
(`outcome.gate_required = True`, `accept()`); else `api.start_lab`
→ success ⇒ `outcome.started = True`, `accept()`; failure ⇒ error + "select it and use Start"
hint, dialog stays open (result ≠ Accepted, `outcome` still set so the caller refreshes).

Not done here: duplicate detection (D-19), `.zip` (D-18), per-image pull progress.

## DesignerDialog (designer.py)

Form-based, table-driven. State: `_nodes: [{id,image}]`, `_networks: [{id,subnet}]`,
`_interfaces: [{node,network,address}]` (plain dicts). Three groups:

- **Nodes**: id field + editable combo (`SUGGESTED_IMAGES = ["alpine:3.21", "ubuntu:22.04",
  "nginx:latest"]`) + Add Node; table ID/Image/Remove.
- **Networks**: id + subnet (`IPv4Network(strict=True)`) + Add Network; table ID/Subnet/
  Attached Nodes (derived live from interfaces)/Remove.
- **Connections**: node combo + network combo + address (`IPv4Interface`) + Connect; table
  Node/Network/Address/Remove.

Client-side rules mirror the server: `ID_PATTERN = ^[a-z][a-z0-9-]*$`, unique ids, address in
subnet, one interface per node per network, unique IPs. Removing a node/network cascades to
its interfaces. `_build_definition()` emits only `name/nodes/networks/interfaces` — **no
description/author/version/manual/resources authoring yet**. Validate → `validate_lab`; Save →
`create_lab` → `accept()` on success. Errors shown as `"loc.path: message; …"` in a status label.
No unsaved-changes guard on close.

## ManualFlyout (manual.py)

`QDockWidget("Lab Manual")`, right/left dock areas, hidden initially. `show_lab(lab_id, name,
sections)` renders each section as a `QGroupBox(title)` with a `QTextBrowser.setMarkdown
(content_markdown)` (external links open) and one `QCheckBox` per task. Checkbox state is
persisted to QSettings on toggle and read back on render. **Reset Progress** → `confirm(...)`
(destructive) → `settings.remove("manual_progress/{lab_id}")` → re-render. `show_empty(msg)`
clears. Progress is never sent to the API and is independent of the runtime reset.

## dialogs.py — in-app dialog rule

`confirm(parent, title, message, confirm_label="Confirm", cancel_label="Cancel",
destructive=False) -> bool`. The only native dialog in the app is `QFileDialog.getOpenFileName`
in `import_lab.py` (grep for `QMessageBox` should stay empty). `ConfirmDialog(QDialog)` modal, word-wrapped message,
`QDialogButtonBox` with Reject/Accept roles; destructive style
`background-color:#dc2626; color:white; font-weight:600`. **Never use `QMessageBox` or OS
message boxes** anywhere in the app (story `windows-desktop-in-app-dialogs`). The only
permitted native dialog is the file-open picker for import.

## quickstart.py

`UBUNTU_QUICK_START_LAB` — "Ubuntu Quick Start", `ubuntu:22.04`, cpu 1 / 512 MB, network
`lab-net 10.50.0.0/24`, interface `10.50.0.10/24`, one manual section with 2 tasks (mirrors
`examples/ubuntu-quickstart.json`). `QUICK_START_SUBNET_POOL = 10.90.0.0/16`,
`_pick_free_subnet`, `build_ubuntu_quick_start_lab`, `create_ubuntu_quick_start_lab` — the
latter is **dead and broken** (`preview.network_subnets` attribute doesn't exist); MainWindow
posts the constant dict directly. See Tigre/06 #1.

## Tests (desktop/tests/, 134 total)

- `conftest.py` — session-scoped autouse `qapp` fixture creating `QApplication([])`.
- `qt_helpers.py` — shared `ImmediateWorker` (synchronous `CallableWorker` stand-in) and
  `StalledWorker` (never finishes until `.finish()`; exposes the busy state). Import as
  `from qt_helpers import …` (pytest puts `tests/` on `sys.path`).
- `test_api_client.py` (45) — monkeypatch `httpx.get/post` with fake responses; also
  `httpx.ConnectError`/`TimeoutException`; `import_lab` and lifecycle-timeout cases.
- `test_lab_file.py` (19) — pure Python: every `read_lab_file` failure mode, `format_issue`,
  sample discovery, and `test_bundled_samples_match_repo_examples` (samples == `examples/`).
- `test_import_lab.py` (23) — `FakeApiClient` + `ImmediateWorker`, ini-file `QSettings` in
  `tmp_path`, `QFileDialog.getOpenFileName` monkeypatched; covers recent list, chooser states,
  every flow outcome, and close-while-busy (`StalledWorker`).
- `test_main_window.py` (11) — **first MainWindow tests**: monkeypatch `ApiClient`, `QSettings`,
  `StartupWorker`, `CallableWorker`, `ImportLabDialog`, `PreStartGateDialog` on `main_window`;
  asserts the import → gate → refresh → select → message/manual wiring.
- `test_node_shell.py` (5) — `sys.platform` / `shutil.which` / `subprocess.Popen` monkeypatched.
- `test_app_status.py` (4), `test_docker_status.py` (5) — pure logic / subprocess monkeypatch.
- **Qt swallows exceptions in slots**: a broken slot prints a traceback and the test still passes.
  Run `pytest -s | grep Traceback` after touching signal handlers.
- `test_dialogs.py` (7) — needs QApplication; checks labels, destructive style, accept/reject,
  `confirm()` via monkeypatched `exec`.
- `test_prestart_gate.py` (15) — `FakeApiClient` + `ImmediateWorker` (synchronous) injected by
  monkeypatching `prestart_gate.CallableWorker`; checks rendering, start gating, accept/reject,
  and the subnet-conflict fixes (monkeypatch `prestart_gate.confirm`).
- No tests for `designer.py`, `manual.py`, `quickstart.py`, `startup.py`.

Run from `desktop/`: `pytest` (needs PySide6 installed; `pip install -e ".[dev]"`). In the Linux
sandbox PySide6 installs from pip; run with `QT_QPA_PLATFORM=offscreen` (see Tigre/07).
