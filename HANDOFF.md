# Practicum — Technical Handoff Document

> Audience: any engineer or AI coding agent picking up this project for the first time.
> This document is model-agnostic — it describes the codebase, not any particular AI tool's workflow.
>
> Refreshed 2026-10-25 after Phase 8 (Windows Quick Start + design icons) was completed. The day-to-day
> engineering memory — status, backlog, known issues, decisions, session log — lives in
> [Tigre/](Tigre/00-README.md) and is kept more current than this overview.

## 1. What This Project Is

**Practicum** is a local-first system for creating, distributing, and running reproducible academic
**networking labs** on student-owned Windows hardware, using Docker as the execution backend.

Two audiences:

- **Instructors** author a lab spec (topology of nodes/networks/interfaces, resource requirements,
  and an embedded instructional "manual") and export it as JSON.
- **Students** import that JSON spec into a Windows desktop app, validate it, start/stop it via
  Docker, and follow the embedded manual.

Two runtime pieces make this up:

1. **`practicum` core** ([src/practicum](src/practicum)) — a local FastAPI service that validates lab
   specs, stores them in memory, and orchestrates Docker containers/networks.
2. **`practicum-desktop`** ([desktop](desktop)) — a PySide6 (Qt) Windows GUI that talks to the local
   API over HTTP, adding instructor "Designer" and student "Import" workflows plus Docker/API
   health checks.

## 2. Project Structure

```
Practicum/
├── pyproject.toml              # practicum core package (FastAPI service)
├── README.md                   # API + dev setup docs
├── src/practicum/               # Core: FastAPI app, models, service, runtime, ports
├── tests/                      # Core test suite (pytest)
├── examples/                   # Sample lab JSON specs
├── src/user-stories.md         # Product vision + phased backlog
├── src/user-story-status.json  # Machine-readable status of every story/phase
├── src/user-stories/           # Per-epic story markdown files
├── src/future-roadmap/         # Longer-term/paid-tier feature ideas (not built)
├── src/postman/                # Postman collection for manual API testing
├── design/practicum-mockups.html  # Clickable mockup the desktop UI is built from
├── Tigre/                      # Living engineering memory (status, issues, decisions, log)
├── start-practicum.bat / stop-practicum.bat  # One-shot Windows launcher (API + desktop)
└── desktop/
    ├── pyproject.toml          # practicum-desktop package (PySide6 app)
    ├── src/practicum_desktop/  # GUI app: screens, running view, designer, API client, theme
    └── tests/                  # Desktop test suite (widget tests included)
```

There is no `.github/workflows`, no dedicated `mypy.ini`/`.ruff.toml` — lint config (ruff) lives
inline in each `pyproject.toml`. **There is currently no CI/CD pipeline configured.**

## 3. Core Package (`src/practicum/`) — Architecture

This is a **ports-and-adapters (hexagonal) style** design, modest in scope:

### `models.py` — domain/contract layer
Pydantic v2 data model. All models use `ConfigDict(extra="forbid")` for strict validation.

- `LabDefinition` — the lab spec: `nodes: list[Node]`, `networks: list[Network]`,
  `interfaces: list[Interface]`, optional `manual: LabManual`. A `model_validator(mode="after")`
  (`validate_topology`) cross-checks: unique node/network IDs, interfaces reference real
  nodes/networks, addresses fall inside their subnet, no duplicate node-network attachments, no
  duplicate IPs.
- `Lab(LabDefinition)` — adds `id` and `status` plus local bookkeeping that is never exported
  (`LAB_RUNTIME_FIELDS`): `origin` (`designer | imported | quick_start`), `source_file`,
  `created_at`, `last_started_at`, `last_error`.
- `Node` — id, Docker `image`, `command`, `environment` (validated names via `EnvironmentName`
  regex), optional `resources: ResourceRequirements`, and (Phase 8) the declared `os`
  (`linux` default | `windows`) and `shell` (`bash` | `sh` | `powershell` | `cmd`; None = the OS
  default, `effective_shell`). Validators: the shell fits the OS, Windows nodes have no
  `shm_size_mb`/`sysctls`, and all nodes of a lab share one OS (`LabDefinition.container_os`) —
  Docker Desktop serves either Linux or Windows containers, never both.
- `ResourceRequirements` — cpu, memory_mb, shm_size_mb, `exposed_ports`, `port_mappings`
  (`PortMapping`: host/container/protocol), `sysctls` (namespaced kernel parameters →
  `docker run --sysctl`), with a validator preventing duplicate/overlapping ports.
- `Network` (id + `IPv4Network` subnet), `Interface` (node/network/`IPv4Interface` address).
- `LabManual` / `ManualSection` / `ManualTask` — instructional content with unique section/task IDs
  enforced by validators.
- Response models: `ValidationResult`, `ImportResult`, `LabPreview` (+ `ResourceEstimate`,
  `TopologyPreview`), `RuntimeActionResult` (+ `pending` for background starts),
  `RuntimeStatusResult` (+ `RuntimeResourceStatus`, `progress: [NodeStartProgress]`),
  `PortCheckResult` (+ `PortConflict`), `NetworkCheckResult` (+ `SubnetConflict`,
  `DockerNetworkInfo`), the `Apply*RecommendationRequest` / `RemoveLeftoverNetworkRequest` bodies.

### `runtime.py` — the runtime "port" (interface) + Docker "adapter"

- `LabRuntime(Protocol)` — abstract runtime interface: `engine_info()`, `start(lab, on_progress)`,
  `stop`, `reset`, `status`, `list_networks`, `remove_network`, `list_practicum_containers`,
  `remove_container`.
- `DockerRuntime` — concrete adapter implemented via `subprocess` calls to the `docker` CLI (not the
  Docker SDK). `engine_info()` is a read-only `docker info --format '{{json .}}'` →
  `DockerEngineInfo` (which kind of container the daemon serves, version, Windows host build,
  isolation); `start` re-checks it first and refuses a lab built for the other kind with the
  Docker Desktop switch instructions (Practicum never switches the mode itself — D-42).
  Creates bridge networks (`nat` for Windows labs) with explicit subnet/gateway per lab network; per node it
  checks the image (`docker image inspect`), pulls a missing one with a streamed `docker pull`
  whose per-layer lines become 0–100 % progress, then `docker start`s a container left by Stop or
  `docker run`s a new one (CPU/memory/shm/port/env flags) and connects extra interfaces via
  `docker network connect`. Deterministic names `practicum-{lab.id[:8]}-{id}`. Reports every step
  through the `on_progress` callback, attributes failures to the node, cleans up on failed starts,
  removes stale empty leftover networks with the same subnet, and tolerates every "already gone"
  wording on stop/reset (`_is_missing_error`).
- `RuntimeFailure` — custom exception carrying a message + the failed command, surfaced to API
  callers as `RuntimeIssue`.

### `ports.py` — host port-conflict detection
(This is the domain "port" in the networking sense, distinct from hexagonal "ports".)

- `check_lab_ports(lab)` — finds conflicts from 3 sources: `duplicate_in_spec`,
  `reserved_by_practicum_api` (via `PRACTICUM_API_PORT` env var, default 8000), `in_use_on_host` (via
  `is_local_port_free`, a real socket bind test — TCP or UDP per mapping). `describe_conflict`
  words a conflict for the start-time re-check. `networks.py` does the same for subnets against
  every Docker network on the host (`find_subnet_conflicts`, `recommend_subnet` from `10.90.0.0/16`).
- `find_available_port` — suggests the next free port ≥1024 avoiding all other ports in play,
  attached to each `PortConflict` as `recommended_port`.

### `service.py` — `LabService`, the application/orchestration layer
In-memory store, no DB.

- Holds `_labs: dict[str, Lab]`, a `LabRuntime` (defaults to `DockerRuntime()`, injectable for
  tests).
- `create(definition, origin, source_file)`, `list`, `delete` (resets Docker resources first;
  `LabDeleteError` → 409), `get`/`export`/`preview` (raise `LabNotFoundError` if missing),
  `start(wait=True|False)` / `stop` / `restart` / `reset` (drive lab `.status` through
  `defined → starting/stopping → running/stopped/error`, catching `RuntimeFailure`; a lab that is
  already `starting`/`stopping` raises `LabBusyError` → 409; start re-checks host ports first and
  keeps a per-node progress store that `status` returns; `wait=False` runs the start on a
  background thread), `status` (runtime resources + progress), `check_ports` /
  `apply_port_recommendation`, `check_networks` / `apply_subnet_recommendation` /
  `remove_leftover_network`.

### `main.py` — FastAPI app + HTTP adapter layer
Thin: each route calls into `LabService`/`ports`, converts `LabNotFoundError` → 404,
`PortRecommendationUnavailableError` → 409, and Pydantic `ValidationError` → structured
`ValidationIssue` lists (no exceptions raised to the client for validate/import). A single
module-level `service = LabService()` instance backs the whole app (**in-memory, not persisted
across restarts, not thread-safe beyond FastAPI's defaults**).

### `__init__.py`
Empty except for the package docstring.

### API surface
`GET /health`, `POST /labs/validate`, `POST /labs?origin=`, `POST /labs/import?source_file=`,
`GET /labs`, `GET /labs/{id}`, `PUT /labs/{id}`, `DELETE /labs/{id}`, `GET /labs/{id}/export`,
`GET /labs/{id}/preview`, `POST /labs/{id}/start?wait=`, `POST /labs/{id}/stop`,
`POST /labs/{id}/restart`, `POST /labs/{id}/reset`, `GET /labs/{id}/status`,
`GET /labs/{id}/ports`, `POST /labs/{id}/ports/apply-recommendation`, `GET /labs/{id}/networks`,
`POST /labs/{id}/networks/apply-recommendation`, `POST /labs/{id}/networks/remove-leftover`,
`POST /docker/sweep-leftovers` (also run at API startup), `GET /docker/engine` (read-only engine
mode). Interactive docs at `/docs`.

## 4. Desktop App (`desktop/src/practicum_desktop/`)

A PySide6 Windows GUI that is a **pure client** of the core API — it contains no lab/Docker
business logic itself (validation, orchestration, and port-conflict logic all live server-side;
the desktop app only renders/relays). Its screens are built from the clickable mockup in
[design/practicum-mockups.html](design/practicum-mockups.html).

- **`main.py`** — entry point: sets `AA_ShareOpenGLContexts` (QtWebEngine), creates the
  `QApplication`, applies the theme, shows `MainWindow`. Console script `practicum-desktop`.
- **`theme.py` / `widgets.py`** — the mockup's design tokens as one application-wide style sheet
  keyed on role properties (`kind`, `role`, `panel`, `badge`, `chip`, `banner`), plus the shared
  building blocks: `Panel`, `Badge`, `Chip`, `MessageBanner`/`NoteBanner` (design icon + copyable
  text), `StatTile`, `StatusPill`, `BackLink`, `FlowLayout`, `AutoSizeStack`, the schematic
  `TopologyView`/`TopologyCanvas`, and two helpers every screen relies on — `bind(button, slot,
  payload)` (connect child buttons without lambdas capturing `self`, which corrupted the heap on
  teardown) and `style_frame`/`edge_frame` (never style a container with a bare `QFrame`
  selector: `QLabel` is a `QFrame`).
- **`icons.py`** — the design icon set from `design/icons.png` (sliced into `assets/icons/` by
  `tools/slice_design_icons.py`): `ICONS` maps names to meanings (success, error, warning, back,
  forward, play, terminal, desktop, tools); `icon()`, `pixmap()`, `icon_label()`,
  `set_button_icon()`, `icon_html()` are the only loaders (cached, tinted for dark buttons,
  disabled state, null-safe when assets are missing). Screens ask for icons by meaning.
- **`main_window.py`** — `MainWindow(QMainWindow)`: brand title bar with a connection status chip
  (collapsible panel: API/Docker lines, next action, API base URL + Retry), and a `QStackedWidget`
  of screens — `welcome`, `dashboard`, `create`, `quickstart`, `designer`, `running`. Owns every
  API call the screens request (they only emit signals), routes every Start through
  `PreStartGateDialog`, confirms destructive actions with `dialogs.confirm()`, caches the lab
  list for the dashboard. Persists the API base URL via `QSettings("Practicum", "Practicum Desktop")`.
- **`dashboard.py`** — `WelcomeScreen` (zero-state hero, blocked banner, "You have N labs" link) and
  `DashboardScreen` with `LabCard`s (origin icon, name, meta line, status badge, activity line,
  per-status actions Open / Start / Delete / Reset).
- **`create_lab.py`** — `CreateLabScreen` (Quick start vs Custom Lab choice cards, OS template
  radios enabled per Docker engine mode, the Windows readiness panel with Docker/Microsoft links
  and Retry) and `QuickStartScreen` (lab name, Instructor setup toggle, template bar, package or
  tool chips, step editor, Create Lab). **`quickstart.py`** turns the draft into a lab definition:
  Ubuntu Desktop (webtop + LinuxServer package mod), Ubuntu (packages → apt-get start command) or
  Windows (Server Core tag pinned from `WINDOWS_IMAGES` by the host build, `os`/`shell` fields, a
  PowerShell init passed as `-EncodedCommand` that installs Chocolatey tools listed in
  `environment.PRACTICUM_PACKAGES` and keeps the container alive); steps → manual sections, free
  `/24` from `10.90.0.0/16`.
- **`designer.py`** — `DesignerView`: Machines / Network topology / Networks panels over the same
  in-memory draft as before, plus a collapsible **Lab instructions** panel (the shared
  **`manual_editor.py`** step editor with a student-view preview; steps are saved as the spec's
  manual); machines come from **`node_catalog.py`** presets (host, router with IP forwarding,
  web server, desktop, custom image), the connect form suggests free addresses; Validate
  (`POST /labs/validate`), Save Lab / Save & Start, and `load_lab()` for editing an existing
  lab (`PUT /labs/{id}`), manual included.
- **`prestart_gate.py`** — `PreStartGateDialog`, the mandatory review before any Start: images,
  topology, manual preview, estimated resources, the Container engine check (`GET /docker/engine`
  vs the lab's OS, with Retry), host-port and subnet conflicts with one-click fixes; Start uses
  `wait=false` and polls `/status` to show real per-node progress.
- **`import_lab.py` / `lab_file.py`** — "Open Lab File" dialog (recent + bundled samples, the one
  native file picker) and the staged import → ports → networks → engine mode → start flow with
  real start progress (anything off hands over to the gate).
- **`running_view.py`** — `RunningLabView`: header (back, title, meta, badge) + lifecycle toolbar
  (Start via gate / Restart / Stop / Reset-with-confirmation / Instructions), the
  **`embedded_view.py`** `EmbeddedLabView` (QWebEngineView behind a URL bar, port picker, waiting
  state, open-in-system-browser fallback), the Lab nodes table with **Open shell** / **Open
  PowerShell** (`node_shell.py`: `docker exec` in a new console with bash→sh, PowerShell or cmd
  from the node's declared `os`/`shell`, after a `docker inspect` pre-check), the **`manual.py`** `ManualFlyout` (numbered
  steps, checkable tasks, "Mark step complete", local progress with completion times in
  `QSettings`, per-step screenshot evidence via **`screenshots.py`** when the instructor asked
  for it — captured from the embedded view or uploaded —, **Export results** →
  **`lab_results.py`** JSON/Markdown/ZIP hand-in via `dialogs.ResultsExportDialog` + the save
  picker), a status bar, and
  `GET /status` polling (1 s while starting/stopping, 5 s idle, paused when hidden).
  **`progress_panel.py`** renders the per-node start progress used by the gate and the running view.
- **`api_client.py`** — `ApiClient`, a thin `httpx` wrapper around every endpoint returning
  dataclasses and never raising; lifecycle calls (`start_lab(wait=)`, `stop_lab`, `restart_lab`,
  `reset_lab`, `delete_lab`) share a long timeout and report 409 as `busy`.
- **`app_status.py`**, **`docker_status.py`**, **`startup.py`** — readiness evaluation, the
  read-only `docker info` probe (`DockerStatus` with the engine mode; `windows_container_readiness`
  → docker_unavailable / linux_engine / ready for the Windows template), and the startup worker
  (health retried with longer timeouts before reporting Blocked). `MainWindow.refresh_engine`
  re-runs only the Docker probe (Create screen Retry / each visit).
- **`workers.py`** — `CallableWorker(QThread)`; **`dialogs.py`** — `ConfirmDialog`/`confirm()`, the
  only sanctioned confirmation; **`labels.py`** — pure text helpers (origin meta, relative times).

## 5. Tests

**Core (`tests/`)**, pytest + FastAPI `TestClient`:

- [conftest.py](tests/conftest.py) — `clear_labs` autouse fixture resets the module-level `service`
  and its runtime between tests; `client` fixture; a shared `lab_definition` fixture (a "Static
  Routing Fundamentals" 2-router topology used across most tests).
- [test_api.py](tests/test_api.py) — end-to-end HTTP tests via `TestClient`, using
  `RecordingRuntime`/`FailingRuntime` fakes injected as `service.runtime` to test
  start/stop/reset/status success and failure paths without touching real Docker.
- [test_models.py](tests/test_models.py) — Pydantic validation rules (defaults, duplicate ID
  rejection, etc.).
- [test_ports.py](tests/test_ports.py) — port conflict detection, using `monkeypatch` on
  `ports.is_local_port_free` to simulate free/busy ports.
- [test_runtime.py](tests/test_runtime.py) — `DockerRuntime` behavior verified by monkeypatching
  `subprocess.run` and asserting the exact `docker` CLI commands built (network create/gateway
  args, run flags, network connect).
- [test_service.py](tests/test_service.py) — `LabService` CRUD/lifecycle logic with a real
  `DockerRuntime` injected.

This confirms the hexagonal pattern is testable by design: `LabRuntime` is a `Protocol`, so tests
substitute fakes at the service layer, and `DockerRuntime` itself is tested purely by asserting
subprocess call shape (no real Docker needed to run the suite).

**Desktop (`desktop/tests/`)**: one module per source module, widget tests included — they run
offscreen (`QT_QPA_PLATFORM=offscreen`) with a session `QApplication` (`conftest.py`), inject a
`FakeApiClient`, and replace `CallableWorker` with the synchronous `ImmediateWorker` /
`StalledWorker` from `qt_helpers.py`. 398 tests at the time of writing. Qt swallows exceptions
raised in slots, so run with `-s` and grep for `Traceback` after touching signal handlers.

## 6. Feature Status

See [src/user-stories.md](src/user-stories.md), [src/user-story-status.json](src/user-story-status.json)
and, for the readable summary, [Tigre/05-status-and-backlog.md](Tigre/05-status-and-backlog.md).

- Phases 1–8 of the backlog are **done** (54 stories) as of 2026-10-25: spec format, validation and
  import/export, Docker runtime with real pull progress and restart/delete, the Windows shell,
  designer workflows, the student learning experience, the mockup-driven desktop UI (dashboard,
  create/quick start, designer re-skin, pre-start gate, running view with lifecycle controls,
  embedded web view and instructions flyout), and Phase 8: Windows-container readiness, the
  Windows Server Core quick start with PowerShell and Chocolatey tools, and the design icon set.
- **Sessions 5 and 6 (everything desktop-visible above, and all Windows-container paths) have not
  been run on Windows yet** — the next step is a smoke run with `start-practicum.bat` against
  Docker Desktop, in both Linux- and Windows-container mode (checklists in Tigre/05, Tigre/06 #26).
- Next backend gaps (Tigre/11): persistence across API restarts (S-1), desktop-supervised API and
  packaging (S-2/S-3), designer metadata/manual editor (S-8/S-9), stable lab identity for
  progress (S-14).

## 7. Future Roadmap (`src/future-roadmap/`)

Long-term/monetization ideas explicitly **not** part of the open-source core:

- `open-source-core-sustainability/`
- `marketplace-platform/` (paid lab distribution, revenue share)
- `advanced-designer-features/` (e.g., visual topology designer)
- `hosted-collaboration-classrooms/`
- `enterprise-institution-features/` (SSO, admin controls)
- `analytics-assessment/`

Guiding principle documented in
[src/future-roadmap/README.md](src/future-roadmap/README.md): the local app/API/Docker
runtime/basic Designer & Import modes/validation/manual/import-export must **always stay free**;
paid tiers target scale, hosting, collaboration, and enterprise features only.

## 8. Postman Collection

`src/postman/practicum-api.postman_collection.json` — a Postman collection for manually exercising
the API endpoints (mirrors the routes in `main.py`); useful for manual/exploratory testing without
the desktop UI.

## 9. Dependencies & Tech Stack

**Core (`pyproject.toml`)**: Python ≥3.12, build via `hatchling`. Runtime deps:
`fastapi>=0.115,<1.0`, `pydantic>=2.10,<3.0`, `uvicorn[standard]>=0.34,<1.0`. Dev deps: `httpx`,
`pytest`, `ruff`. Ruff configured with `line-length=100`, `target-version=py312`. Tests configured
via `[tool.pytest.ini_options] testpaths = ["tests"]`.

**Desktop (`desktop/pyproject.toml`)**: Python ≥3.12, `hatchling`. Runtime deps:
`PySide6>=6.7,<7.0` (the full package — its Addons provide QtWebEngine for the embedded lab view;
without them the view falls back to "open in system browser"), `httpx>=0.28,<1.0`. Dev dep:
`pytest`. Console script `practicum-desktop`. Same ruff config.

No database — everything is in-memory (`LabService._labs` dict), reset on API restart. No async
DB/ORM. Docker orchestration is via `docker` CLI subprocess calls, not `docker-py`/SDK.

## 10. Build / Run / Test

From root README:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
uvicorn practicum.main:app --reload
```

Run core tests (from repo root, picks up `tests/` per `testpaths`):

```powershell
pytest
```

Validate the example topology once the server is running:

```powershell
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/labs/validate `
  -ContentType application/json -InFile examples/static-routing.json
```

Desktop app (inferred from its `pyproject.toml`; no dedicated README found): install `desktop/` as
an editable package and run the GUI, with the core API running in parallel (defaults to
`http://127.0.0.1:8000`, configurable via UI/QSettings):

```powershell
cd desktop
python -m pip install -e ".[dev]"
practicum-desktop        # or: python -m practicum_desktop.main
```

Run desktop tests with `pytest` from `desktop/` (`QT_QPA_PLATFORM=offscreen` on a headless machine).

**Prerequisite for actual lab execution**: Docker must be installed and running (checked live by
`docker_status.check_docker()` / `DockerRuntime`); the API/tests themselves don't require Docker
since Docker calls are mocked or optional at the service layer.

## 11. Gaps & Things a New Engineer/Agent Should Know

- **No CI/CD** (`.github/workflows`) — tests must be run manually before/after changes.
- **No persistence layer** — all lab state is lost on API restart; Docker resources survive and
  show up as "leftovers" the pre-start gate can remove. Persistence (Tigre/11 S-1) is unbuilt.
- `DockerRuntime` shells out to the `docker` CLI rather than using an SDK — command construction is
  string-based and covered mainly through subprocess-mocking tests, so changes there need careful
  test updates.
- Export is deliberately not blocked by host-port conflicts (they are machine-specific, the export is
  portable — decision D-30 in Tigre/09); Start re-checks ports server-side instead.
- QtWebEngine (the embedded lab view) needs `AA_ShareOpenGLContexts` before the `QApplication`
  exists (`main.py` does this) and accepts self-signed certificates for localhost only.
- Never connect a lambda that captures `self` to a child widget's signal; use `widgets.bind()` —
  the cycle it creates was torn down in the wrong order by PySide 6.12 and corrupted the heap.
- Two separate `pyproject.toml`/packages (`practicum` and `practicum-desktop`) are independently
  versioned and installed — remember to activate/install the correct one when working in
  `desktop/` vs the repo root.
- Both core and desktop currently share the same versioned data-model regexes/constraints (e.g.
  ID patterns) by convention, not by shared code — keep them in sync manually if either changes.
