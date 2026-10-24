# Practicum

Practicum is a local-first system for creating, distributing, and running
reproducible academic **networking labs** on student-owned Windows hardware,
using Docker as the execution backend. Instructors author a lab's topology
(nodes, networks, interfaces), resource requirements, and an embedded
step-by-step manual, then export it as a single JSON file. Students import
that file into a Windows desktop app, validate it, start and stop it with one
click, and follow the embedded manual alongside the running lab — no Docker
commands, topology diagrams, or command-line tooling required on their end.

The project has two parts:

- **[`practicum`](src/practicum)** — a local FastAPI service that validates
  lab specs, stores them, and orchestrates the Docker containers and networks
  behind them. This repository's root package; see below for API usage.
- **[`practicum-desktop`](desktop)** — a PySide6 (Qt) Windows GUI that talks
  to the local API: a labs dashboard, a guided lab designer and quick-start
  templates for instructors, an import-and-launch flow for students, a
  pre-start review gate, and a running-lab view with lifecycle controls, an
  embedded web view and the instructions flyout. See [HANDOFF.md](HANDOFF.md)
  for how it's structured.

See [HANDOFF.md](HANDOFF.md) for a full technical walkthrough of the
codebase, and [src/user-stories.md](src/user-stories.md) for the product
vision and phased backlog driving ongoing work.

The first milestone defined the API contract: accept a network topology as
JSON, validate its references and addresses, and store the definition in
memory. That contract has since grown to cover import/export, Docker
runtime orchestration, port-conflict detection, and a desktop application —
this README's API section below reflects the current surface.

## API

- `GET /health`
- `POST /labs/validate`
- `POST /labs` (`?origin=designer|imported|quick_start`, dashboard bookkeeping)
- `POST /labs/import` (`?source_file=<name>`)
- `GET /labs`
- `GET /labs/{lab_id}`
- `PUT /labs/{lab_id}` (edit: replaces the definition, keeps id/origin; 409 while running)
- `DELETE /labs/{lab_id}` (removes the lab's Docker resources first; 409 if that fails)
- `GET /labs/{lab_id}/export`
- `GET /labs/{lab_id}/preview`
- `POST /labs/{lab_id}/start` (`?wait=false` returns 202 at once; poll `/status` for progress)
- `POST /labs/{lab_id}/stop`
- `POST /labs/{lab_id}/restart`
- `POST /labs/{lab_id}/reset`
- `GET /labs/{lab_id}/status` (includes per-node start progress while starting)
- `GET /labs/{lab_id}/ports`
- `POST /labs/{lab_id}/ports/apply-recommendation`
- `POST /docker/sweep-leftovers` (removes containers/networks of labs this API no longer knows; also runs at startup)
- `GET /labs/{lab_id}/networks`
- `POST /labs/{lab_id}/networks/apply-recommendation`
- `POST /labs/{lab_id}/networks/remove-leftover`

Interactive API documentation is available at `/docs`.

## Quick start (Windows)

Double-click `start-practicum.bat` (or run it from a terminal in the repo root). It creates
`.venv` and installs both packages on first run, starts the API in its own window, waits for
`/health`, then launches the desktop app. Closing the desktop app stops the API again.
`start-practicum.bat --dev` runs the API with `--reload`; `stop-practicum.bat` cleans up an
API window if one is left behind.

To run a lab an instructor sent you, click **Import Existing Lab** in the desktop app, pick the
`.json` export (the three labs from [`examples/`](examples) are offered as samples), and
Practicum imports it, checks host ports and Docker subnets, and starts it — showing the real
image-download progress while it does. Labs whose host ports or subnets clash with something on
your machine stop at a review screen with one-click fixes (use a recommended port/subnet, remove a
leftover from an earlier session, or reset the lab that owns the address space). Once running, the
lab opens in the running view: its web interface (if it publishes one) embedded in the app, the
instructions flyout with checkable steps, **Open shell** on each node, and **Restart / Stop / Reset**.

Returning users land on the **Your Labs** dashboard (one card per lab with Open / Start / Delete);
**Create New Lab** offers a Quick start template — an **Ubuntu Desktop** that opens inside the app
(point and click, made for simple or non-IT labs) or a terminal-only Ubuntu, each with packages to
pre-install and a step editor — or the Custom Lab designer: pick machines from a catalogue (host,
router, web server, desktop…), connect them into networks with suggested addresses, and see the
schematic topology. Any lab can be **edited** later (including quick starts) and **exported** to a
`.json` file from its dashboard card.

## Development

Python 3.12 or newer is required.

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
uvicorn practicum.main:app --reload
```

Run the tests:

```powershell
pytest
```

Validate the example topology after starting the API:

```powershell
Invoke-RestMethod `
  -Method Post `
  -Uri http://127.0.0.1:8000/labs/validate `
  -ContentType application/json `
  -InFile examples/static-routing.json
```

## Current Status and Roadmap

The Docker runtime (start/stop/restart/reset/delete with real pull progress),
import/export, port- and subnet-conflict detection, and the complete
mockup-driven desktop UI (phases 1–7 of the backlog) are implemented and
tested. Work is tracked story-by-story in [src/user-stories.md](src/user-stories.md)
and [src/user-story-status.json](src/user-story-status.json); the living
engineering notes are in [Tigre/](Tigre/00-README.md); longer-term ideas live
in [src/future-roadmap](src/future-roadmap). Labs are held in memory by the
API and are lost when it restarts (persistence is the next backend gap).
