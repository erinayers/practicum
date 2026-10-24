# 01 — Project Overview

## What Practicum is

A **local-first system for creating, distributing, and running reproducible academic
networking labs** on student-owned Windows machines, using Docker as the execution backend.

- **Instructors** (Designer Mode) author a lab: topology (nodes, networks, interfaces),
  Docker resource requirements, and an embedded step-by-step **manual**. Exported as one JSON
  file.
- **Students** (Import Mode) import that JSON into the Windows desktop app, see a preview /
  readiness gate, start/stop/reset the lab with a click, and follow the manual in a flyout
  while the lab runs. No Docker commands required on their end.
- **Local Runtime** = the API + Docker orchestration. Validates specs, creates containers and
  networks, tracks status, reports structured errors.

Product vision and personas are in `src/user-stories.md`. Long-term monetization ideas are in
`src/future-roadmap/` — the **local loop (create, validate, export, import, run, manual, stop,
reset) must always stay free/open-source**; paid tiers are hosted/marketplace/enterprise only.

## Two independently-installed Python packages

| Package | Path | Stack | Entry |
|---------|------|-------|-------|
| `practicum` (core API) | repo root `pyproject.toml`, code in `src/practicum/` | FastAPI, Pydantic v2, uvicorn, `docker` CLI via subprocess | `uvicorn practicum.main:app --reload` (port 8000) |
| `practicum-desktop` | `desktop/pyproject.toml`, code in `desktop/src/practicum_desktop/` | PySide6 (Qt), httpx | `practicum-desktop` console script → `practicum_desktop.main:main` |

Both: Python ≥ 3.12, hatchling build, ruff `line-length = 100`, `target-version = py312`,
pytest `testpaths = ["tests"]`. Both are version `0.1.0`. **No shared code between them** —
the desktop mirrors the core's ID regex and rules by convention (keep in sync manually).

The desktop app contains **no lab/Docker business logic**; all validation, orchestration and
port-conflict logic is server-side. The desktop only renders and relays.

## Repository layout (as of the 2026-10-24 snapshot)

```
eduLabs - Copy/
├── README.md                   # API list + dev setup (accurate for API surface)
├── HANDOFF.md                  # Human handoff doc — refreshed 2026-10-24, points here for detail
├── .gitignore                  # __pycache__, .pytest_cache, .venv, dist, build, egg-info
├── pyproject.toml              # core package
├── src/
│   ├── practicum/              # core: __init__ main models service runtime ports networks
│   ├── user-stories.md         # vision, personas, phases 1-7 recommended order
│   ├── user-story-status.json  # CANONICAL machine-readable status of every story
│   ├── user-stories/<epic>/    # one .md per story (6 epics, 47 stories)
│   ├── future-roadmap/<epic>/  # paid-tier ideas, NOT built, 6 epics
│   └── postman/practicum-api.postman_collection.json
├── tests/                      # core pytest suite (159 tests)
├── examples/                   # 3 sample labs + import-probes/ (7 manual-test files + README)
├── design/practicum-mockups.html   # clickable HTML mockups driving Phase 7
├── desktop/
│   ├── pyproject.toml
│   ├── src/practicum_desktop/  # 24 modules + samples/ (see Tigre/03)
│   └── tests/                  # 270 tests (+ qt_helpers.py)
└── Tigre/                      # THIS FOLDER — living memory
```

Git: single commit `59c4a9e baseline` (2026-10-23). No branches, no CI/CD, no
`.github/workflows`.

## The six story epics (src/user-stories/)

| Epic folder | Goal | Stories |
|-------------|------|---------|
| `windows-desktop-application` | Native-feeling Windows shell | launch, local-api, port-conflict-ui, labs-dashboard, prestart-lab-gate, import-lab-file, lab-lifecycle-controls, embedded-lab-view, in-app-dialogs, open-node-shell |
| `lab-spec-format` | Portable lab JSON | metadata, docker-resources |
| `designer-mode` | Instructor authoring | create-new-lab, add-nodes, add-networks, connect-nodes-networks, validate-lab, author-manual, export-spec, visual-topology-builder |
| `student-import-mode` | Student import/run | import-spec, preview-imported-lab, start-lab, stop-lab, reset-lab |
| `lab-manual-flyout` | Manual while working | view-flyout, track-progress |
| `docker-runtime-api` | Backend runtime | api-start, api-stop, api-status, browser-accessible-nodes, node-command-options, node-environment, port-mappings, shared-memory, browser-desktop-example, host-port-availability, host-port-recommendations, subnet-conflicts, image-pull-progress |

## The design mockup (design/practicum-mockups.html)

A single self-contained HTML file (≈62 KB) with 7 screens and 3 overlays, used to review UX
and to source Phase 7 stories. Screen ids and which story they anchor:

| Mockup id | Screen | Story it drives |
|-----------|--------|-----------------|
| `screen-welcome` | Zero-state welcome: Create New Lab / Import Existing Lab | (existing) |
| `screen-dashboard` | "Your Labs" cards: Running→Open, Stopped→Start/Delete, Draft→Edit/Delete | `windows-desktop-labs-dashboard` |
| `screen-create` | Choose Quick start (single host) vs Custom Lab | — |
| `screen-quickstart` | Configure quick start: OS template, packages, step editor | (future; relates to quickstart.py) |
| `screen-custom` | 3-panel Machines / Network Topology / Networks designer | `designer-visual-topology-builder` |
| `screen-preview` | Pre-start gate: images (local vs pull), CPU/mem, topology, conflicts | `windows-desktop-prestart-lab-gate` (done) |
| `screen-running` | Toolbar (Restart/Stop/Instructions), embedded browser pane, instructions flyout | `lab-lifecycle-controls`, `embedded-lab-view` |
| `confirmModal` | `showConfirm(title, message, confirmLabel, destructive, onConfirm)` | `windows-desktop-in-app-dialogs` (built as `dialogs.py`) |
| `importModal` | "Open Lab File" recent-files list + Browse | `windows-desktop-import-lab-file` (done — `import_lab.py`) |
| `importingOverlay` | Multi-stage progress bar (`runLoadingSequence`) — **fake timer** | `runtime-image-pull-progress` would make it real |

## Timeline clues

- `.pyc` cache stamps run 2026-06-11 → 2026-06-16; status JSON `last_updated` 2026-10-11;
  HANDOFF.md references 2026-08-15; git baseline 2026-10-23. Python used by the author is
  **3.14** (`cpython-314` pyc files) on **Windows** (PowerShell in README, Qt app verified
  on Windows).
- Phase 7 stories were authored 2026-10-11 after the mockup review. Session 4 (2026-10-23) added
  two stories born from the first Windows smoke run (`runtime-subnet-conflicts`,
  `windows-desktop-open-node-shell`).
