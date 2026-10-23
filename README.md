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
  to the local API, adding a guided lab designer for instructors, an import
  flow for students, and Docker/API health checks. See [HANDOFF.md](HANDOFF.md)
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
- `POST /labs`
- `POST /labs/import`
- `GET /labs`
- `GET /labs/{lab_id}`
- `GET /labs/{lab_id}/export`
- `GET /labs/{lab_id}/preview`
- `POST /labs/{lab_id}/start`
- `POST /labs/{lab_id}/stop`
- `POST /labs/{lab_id}/reset`
- `GET /labs/{lab_id}/status`
- `GET /labs/{lab_id}/ports`
- `POST /labs/{lab_id}/ports/apply-recommendation`

Interactive API documentation is available at `/docs`.

## Quick start (Windows)

Double-click `start-practicum.bat` (or run it from a terminal in the repo root). It creates
`.venv` and installs both packages on first run, starts the API in its own window, waits for
`/health`, then launches the desktop app. Closing the desktop app stops the API again.
`start-practicum.bat --dev` runs the API with `--reload`; `stop-practicum.bat` cleans up an
API window if one is left behind.

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

The Docker runtime, import/export, and port-conflict detection described
above are implemented and tested, alongside a PySide6 desktop shell. Active
work is tracked story-by-story in [src/user-stories.md](src/user-stories.md)
and [src/user-story-status.json](src/user-story-status.json); longer-term
ideas live in [src/future-roadmap](src/future-roadmap).
