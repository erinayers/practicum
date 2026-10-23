# 03 — Desktop App Architecture (`desktop/src/practicum_desktop/`)

PySide6 (Qt 6) Windows GUI. **Pure client of the core API** — no lab logic. 13 modules,
~1,900 lines.

```
main.py (18)          QApplication + MainWindow; console script `practicum-desktop`
main_window.py (349)  MainWindow(QMainWindow) — the single screen today
api_client.py (423)   ApiClient (httpx) + result dataclasses; never raises, returns success flags
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

**Not yet wrapped** (needed by Phase 7): `stop_lab`, `reset_lab`, `get_status`, `import_lab`,
`export_lab`, delete (no endpoint exists server-side either).

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
5. **Quick Start: Ubuntu** → `CallableWorker(api.create_lab, UBUNTU_QUICK_START_LAB)` →
   status label → `check_status()`.
6. **View Manual** (enabled when a lab is selected) → toggles `ManualFlyout` visibility.
7. `Port Conflicts:` table (Node / Host Port / Issue / Recommended with "Use <port>" buttons).
8. `Browser Access:` table (Host Port / Maps To / "Open in Browser" → `webbrowser.open
   (http://localhost:{port})`) — filled from `PreviewResult.port_mappings`.
9. **Start Selected Lab…** → opens `PreStartGateDialog`; on Accepted shows "✅ Lab started.";
   then re-runs port check.
10. `ManualFlyout` docked right (hidden by default).

Selecting a lab row (`_on_lab_row_changed`) fires two workers: `check_ports` and `get_preview`
(the latter feeds both the manual flyout and the browser-access table).

QSettings: `QSettings("Practicum", "Practicum Desktop")`. Keys: `api_base_url`,
`manual_progress/{lab_id}/{section_id}/{task_id}` = bool.

Window: title "Practicum", default size 480×420 (small; the mockups imply a much larger
multi-screen app — Phase 7 will restructure this).

## PreStartGateDialog (prestart_gate.py) — done, the "single authority" for Start

- Constructor kicks off `get_preview` and `check_ports` in parallel workers.
- Shows: name (bold 16px), description, `author · version`, required images (comma list),
  CPU `"{n} vCPU"`/`Unknown`, Memory `"{n} MB"`/`Unknown`, read-only topology table
  (Node/Network/Address — one row per interface), manual step count sentence or "This lab has
  no manual.", Port Conflicts group (banner + table with "Use <port>" buttons), status label,
  Cancel / **Start Lab** buttons.
- Start Lab enabled only when `self._conflicts` is empty. Applying a recommendation re-renders
  from the server's fresh response.
- Start → `start_lab` worker → on success `accept()`; on failure shows `❌ detail` and
  re-enables Start if still conflict-free.
- Docstring states: every entry point that can start a lab (dashboard, import-and-launch)
  **must reuse this dialog**, not reimplement the gate.
- Not yet shown: image local-vs-pull status (no API support), manual preview content (only a
  count).

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
destructive=False) -> bool`. `ConfirmDialog(QDialog)` modal, word-wrapped message,
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

## Tests (desktop/tests/, 49 total)

- `conftest.py` — session-scoped autouse `qapp` fixture creating `QApplication([])`.
- `test_api_client.py` (27) — monkeypatch `httpx.get/post` with fake responses; also
  `httpx.ConnectError`/`TimeoutException`.
- `test_app_status.py` (4), `test_docker_status.py` (4) — pure logic / subprocess monkeypatch.
- `test_dialogs.py` (7) — needs QApplication; checks labels, destructive style, accept/reject,
  `confirm()` via monkeypatched `exec`.
- `test_prestart_gate.py` (7) — `FakeApiClient` + `ImmediateWorker` (synchronous) injected by
  monkeypatching `prestart_gate.CallableWorker`; checks rendering, start gating, accept/reject.
- No tests for `main_window.py`, `designer.py`, `manual.py`, `quickstart.py`, `startup.py`.

Run from `desktop/`: `pytest` (needs PySide6 installed; `pip install -e ".[dev]"`). The 35
non-Qt tests can run without PySide6 via a stub on PYTHONPATH and `--noconftest` (done in the
2026-10-23 review session; see Tigre/07).
