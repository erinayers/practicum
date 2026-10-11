# Practicum — Technical Handoff Document

> Audience: any engineer or AI coding agent picking up this project for the first time.
> This document is model-agnostic — it describes the codebase, not any particular AI tool's workflow.

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
└── desktop/
    ├── pyproject.toml          # practicum-desktop package (PySide6 app)
    ├── src/practicum_desktop/  # GUI app: main window, designer, manual flyout, API client
    └── tests/                 # Desktop test suite
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
- `Lab(LabDefinition)` — adds `id` and `status` (a stored/instantiated lab).
- `Node` — id, Docker `image`, `command`, `environment` (validated names via `EnvironmentName`
  regex), optional `resources: ResourceRequirements`.
- `ResourceRequirements` — cpu, memory_mb, shm_size_mb, `exposed_ports`, `port_mappings`
  (`PortMapping`: host/container/protocol), with a validator preventing duplicate/overlapping ports.
- `Network` (id + `IPv4Network` subnet), `Interface` (node/network/`IPv4Interface` address).
- `LabManual` / `ManualSection` / `ManualTask` — instructional content with unique section/task IDs
  enforced by validators.
- Response models: `ValidationResult`, `ImportResult`, `LabPreview` (+ `ResourceEstimate`,
  `TopologyPreview`), `RuntimeActionResult`, `RuntimeStatusResult` (+ `RuntimeResourceStatus`),
  `PortCheckResult` (+ `PortConflict`), `ApplyPortRecommendationRequest`.

### `runtime.py` — the runtime "port" (interface) + Docker "adapter"

- `LabRuntime(Protocol)` — abstract runtime interface: `start`, `stop`, `reset`, `status` (all take
  a `Lab`).
- `DockerRuntime` — concrete adapter implemented via `subprocess` calls to the `docker` CLI (not the
  Docker SDK). Creates bridge networks with explicit subnet/gateway per lab network, runs one
  container per node with CPU/memory/shm/port/env flags, connects additional interfaces via
  `docker network connect`, and computes deterministic resource names like
  `practicum-{lab.id[:8]}-{node_id}`. Handles cleanup on failed starts
  (`_cleanup_after_failed_start`), stale leftover networks with the same subnet, and idempotent
  "not found" errors on stop/reset.
- `RuntimeFailure` — custom exception carrying a message + the failed command, surfaced to API
  callers as `RuntimeIssue`.

### `ports.py` — host port-conflict detection
(This is the domain "port" in the networking sense, distinct from hexagonal "ports".)

- `check_lab_ports(lab)` — finds conflicts from 3 sources: `duplicate_in_spec`,
  `reserved_by_practicum_api` (via `PRACTICUM_API_PORT` env var, default 8000), `in_use_on_host` (via
  `is_local_port_free`, a real socket bind test).
- `find_available_port` — suggests the next free port ≥1024 avoiding all other ports in play,
  attached to each `PortConflict` as `recommended_port`.

### `service.py` — `LabService`, the application/orchestration layer
In-memory store, no DB.

- Holds `_labs: dict[str, Lab]`, a `LabRuntime` (defaults to `DockerRuntime()`, injectable for
  tests).
- `create`, `list`, `get`/`export`/`preview` (raise `LabNotFoundError` if missing),
  `start`/`stop`/`reset` (drive lab `.status` through
  `defined → starting/stopping → running/stopped/error`, catching `RuntimeFailure`), `status`
  (delegates to runtime, returns per-resource status), `check_ports`/`apply_port_recommendation`
  (mutates a lab's node resources to swap in a recommended port, raises
  `PortRecommendationUnavailableError` if none available).

### `main.py` — FastAPI app + HTTP adapter layer
Thin: each route calls into `LabService`/`ports`, converts `LabNotFoundError` → 404,
`PortRecommendationUnavailableError` → 409, and Pydantic `ValidationError` → structured
`ValidationIssue` lists (no exceptions raised to the client for validate/import). A single
module-level `service = LabService()` instance backs the whole app (**in-memory, not persisted
across restarts, not thread-safe beyond FastAPI's defaults**).

### `__init__.py`
Empty except for the package docstring.

### API surface
`GET /health`, `POST /labs/validate`, `POST /labs`, `POST /labs/import`, `GET /labs`,
`GET /labs/{id}`, `GET /labs/{id}/export`, `GET /labs/{id}/preview`, `POST /labs/{id}/start`,
`POST /labs/{id}/stop`, `POST /labs/{id}/reset`, `GET /labs/{id}/status`, `GET /labs/{id}/ports`,
`POST /labs/{id}/ports/apply-recommendation`. Interactive docs at `/docs`.

## 4. Desktop App (`desktop/src/practicum_desktop/`)

A PySide6 Windows GUI that is a **pure client** of the core API — it contains no lab/Docker
business logic itself (validation, orchestration, and port-conflict logic all live server-side;
the desktop app only renders/relays).

- **`main.py`** — entry point (`main()`), creates `QApplication` + `MainWindow`. Console-script
  entry point: `practicum-desktop = "practicum_desktop.main:main"`.
- **`api_client.py`** — `ApiClient`, a thin `httpx`-based wrapper around every core endpoint,
  converting JSON responses into dataclasses (`HealthStatus`, `LabsResult`,
  `PortCheckResult`/`PortConflict`, `StartResult`, `ValidateLabResult`/`FieldIssue`,
  `CreateLabResult`, `PreviewResult`/`ManualSectionInfo`/`ManualTaskInfo`/`PortMappingInfo`).
  Handles connection/timeout/HTTP errors gracefully rather than raising.
- **`app_status.py`** — `evaluate_app_status(api, docker) -> AppStatus` — pure function combining
  API health + Docker availability into a `Readiness` (`ready` / `degraded` / `blocked`) plus a
  human-readable `next_action` string. Pure logic, easily unit-tested (see `test_app_status.py`).
- **`docker_status.py`** — `check_docker()` runs `docker info` via subprocess with a timeout,
  returns `DockerStatus(available, detail)`.
- **`startup.py`** — `StartupWorker(QThread)` runs the API/Docker checks off the UI thread, emits
  `finished_check(status, labs_result)`.
- **`workers.py`** — `CallableWorker(QThread)` — generic "run any blocking callable off the UI
  thread" worker used throughout the app (port checks, apply-recommendation, save/validate, manual
  load, quick start) to keep the Qt UI thread non-blocking.
- **`main_window.py`** — `MainWindow(QMainWindow)`, the central window: shows readiness banner, lab
  list/table, port conflict table with per-row "Use `<port>`" buttons, wires up the Designer dialog,
  Manual flyout, and Quick Start action. Persists API base URL via
  `QSettings("Practicum", "Practicum Desktop")`.
- **`designer.py`** — `DesignerDialog(QDialog)` — instructor-facing form UI to build a new lab
  (nodes/networks/interfaces), validates via `POST /labs/validate` and saves via `POST /labs`, with
  ID pattern validation matching the core model's regex.
- **`manual.py`** — `ManualFlyout(QDockWidget)` — dockable panel rendering a lab's manual
  (`QTextBrowser.setMarkdown`) with checkable tasks; **task-completion progress is stored only
  locally in `QSettings`**, keyed by lab/section/task id, and is never sent to the API. Has a
  separate "Reset Progress" action distinct from lab runtime reset.
- **`quickstart.py`** — embeds `UBUNTU_QUICK_START_LAB`, a hardcoded single-container Ubuntu lab
  spec (mirrors [examples/ubuntu-quickstart.json](examples/ubuntu-quickstart.json)) so users can
  try the app without authoring a spec; uses a dedicated `/16` subnet pool (`10.90.0.0/16`) to
  avoid collisions with hand-authored labs.

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

**Desktop (`desktop/tests/`)**: `test_api_client.py`, `test_app_status.py`,
`test_docker_status.py` — unit tests for the client/status logic, decoupled from the Qt UI (no
widget tests observed).

## 6. Feature Status

See [src/user-stories.md](src/user-stories.md) and
[src/user-story-status.json](src/user-story-status.json).

- Full product vision: Designer Mode (instructor) + Import Mode (student), backed by local API +
  Docker runtime.
- **All 6 planned MVP phases are marked `"done"`** as of `last_updated: 2026-08-15`:
  1. Strengthen the Lab Spec (metadata, Docker resources, manual authoring)
  2. Validate/Import/Export lab files
  3. Runtime API + Docker control (start/stop/status, port mappings, host-port conflict detection
     & recommendations)
  4. Windows Application Shell (launch, API connection, port-conflict UI)
  5. Basic Designer Workflows (create lab, add nodes/networks, connect nodes)
  6. Student Learning Experience (manual flyout, progress tracking)
- `current_phase`: **"Post-MVP: close remaining gaps / future-roadmap"**.
- **One known open gap**: `GET /labs/{lab_id}/export` is not yet guarded by the host-port-conflict
  check (tracked as `runtime-host-port-availability`, phase-3) — flagged as
  `next_recommended_story`.
- Beyond that, further work is expected to come from `src/future-roadmap/`.

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
`PySide6>=6.7,<7.0`, `httpx>=0.28,<1.0`. Dev dep: `pytest`. Console script `practicum-desktop`. Same
ruff config.

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

Run desktop tests with `pytest` from `desktop/`.

**Prerequisite for actual lab execution**: Docker must be installed and running (checked live by
`docker_status.check_docker()` / `DockerRuntime`); the API/tests themselves don't require Docker
since Docker calls are mocked or optional at the service layer.

## 11. Gaps & Things a New Engineer/Agent Should Know

- **No CI/CD** (`.github/workflows`) — tests must be run manually before/after changes.
- **No persistence layer** — all lab state is lost on API restart; anything requiring durability is
  unbuilt.
- `DockerRuntime` shells out to the `docker` CLI rather than using an SDK — command construction is
  string-based and covered mainly through subprocess-mocking tests, so changes there need careful
  test updates.
- The `runtime-host-port-availability` gap on `/export` is the most concretely flagged next task
  (see [src/user-story-status.json](src/user-story-status.json)).
- Two separate `pyproject.toml`/packages (`practicum` and `practicum-desktop`) are independently
  versioned and installed — remember to activate/install the correct one when working in
  `desktop/` vs the repo root.
- Both core and desktop currently share the same versioned data-model regexes/constraints (e.g.
  ID patterns) by convention, not by shared code — keep them in sync manually if either changes.
