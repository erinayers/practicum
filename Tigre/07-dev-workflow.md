# 07 — Dev Workflow and Conventions

## One-shot launcher (added 2026-10-23)

`start-practicum.bat` at the repo root (CRLF, cmd.exe):
1. `cd /d %~dp0`; creates `.venv` via `py -3` (fallback `python`) and `pip install -e ".[dev]"`
   + `-e ".\desktop[dev]"` when `.venv\Scripts\python.exe` is missing, imports fail, or `--setup`.
2. If `GET /health` already returns 200 → reuses the running API (`API_STARTED_HERE` unset).
   Else `start "Practicum API (port N)" /D root python -m uvicorn practicum.main:app --host
   127.0.0.1 --port N [--reload]` and polls `/health` up to 30 × 1 s (curl, PowerShell fallback).
3. Runs `python -m practicum_desktop.main` in the foreground.
4. On desktop exit: `taskkill /FI "WINDOWTITLE eq Practicum API*" /T /F` — only if it started it.
Flags: `--dev` (= `--reload`), `--setup`, `--help`. Env: `PRACTICUM_API_PORT` (default 8000;
the desktop's `api_base_url` QSettings value must be changed in the UI if the port changes).
`stop-practicum.bat` = the taskkill line alone. Verified working on Windows 2026-10-23 (API runs
under `cmd /k` so crashes stay visible; launcher prints per-attempt health codes). This is an interim for story S-2 (Tigre/11).

## Environment (author's: Windows, PowerShell, Python 3.14; spec says ≥3.12)

```powershell
# core API (repo root)
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
uvicorn practicum.main:app --reload          # http://127.0.0.1:8000 , docs at /docs
pytest                                        # 100 tests, ~1.5 s, no Docker needed

# desktop (separate install, same venv is fine)
cd desktop
python -m pip install -e ".[dev]"
practicum-desktop                             # or: python -m practicum_desktop.main
pytest                                        # 49 tests; needs PySide6 (QApplication fixture)
```

Docker Desktop must be running only to actually start labs; tests never touch Docker.
`PRACTICUM_API_PORT` env var tells `ports.py` which host port the API itself occupies (default 8000).

### Linux sandbox notes (AI sessions)

- Install: `pip install --break-system-packages pytest PySide6 ruff` — **PySide6 6.12 installed
  fine on 2026-10-23 (Session 4)**; if pip has no network, fall back to the stub approach below.
- Core: `PYTHONPATH=src python3 -m pytest -q -p no:cacheprovider` from repo root → 104 passed.
- Desktop (all tests incl. Qt): from `desktop/`,
  `QT_QPA_PLATFORM=offscreen PYTHONPATH=src python3 -m pytest -q -p no:cacheprovider` → 105 passed.
- Visual check without a display: build the widget, `widget.show()`, call
  `app.processEvents()` a couple of times (layouts are lazy), then `widget.grab().save("x.png")`
  and view the PNG. Used in Session 4 for `ImportLabDialog` and `MainWindow`.
- Live API for e2e: `PYTHONPATH=src python3 -m uvicorn practicum.main:app --port 8000 &`; the
  sandbox's `docker` binary is not executable (PermissionError) — good for testing failure paths.
  Host port 22 cannot be bound as non-root, so `static-routing.json` always reports a conflict here.
- **Stateful fake Docker for e2e** (Session 4): a Python script named `docker` on `PATH` ahead of
  the real one, keeping `{"networks": {name: {subnet, gateway, labels}}, "containers": {name:
  {networks, status}}}` in a JSON file; implements `info`, `network ls/inspect/create/rm/connect`,
  `run`, `stop`, `rm -f`, `inspect --format {{.State.Status}}`; rejects overlapping pools with
  Docker's exact message and refuses `network rm` with active endpoints. Start uvicorn with
  `PATH=/tmp/fakedocker:$PATH`. Seed the state file to reproduce leftovers. (Not committed — it
  lived in `/tmp`; recreate from this description if needed, ~80 lines.)
- **Slot exceptions are swallowed by Qt** — after changing any signal handler run the desktop
  suite with `-s` and grep for `Traceback`; a green run alone proves nothing for slots.
- Lint: `python3 -m ruff check <paths>` / `ruff format --check`. Pre-existing findings exist in
  `quickstart.py`, `workers.py`, `runtime.py`, `test_runtime.py` (long lines, UP035) — leave them
  unless touching those files. Delete `.ruff_cache/` afterwards (not gitignored).
- **Line endings**: files are individually CRLF or LF (see Tigre/06). `Path.write_text` normalises
  to LF — re-apply CRLF (`sed -i 's/$/\r/'`) or edit bytes. Check with `file <path>`.
- Offline fallback (no PySide6): stub package `PySide6/{__init__,QtCore,QtWidgets}.py` with dummy
  `QThread, Signal, QObject, Qt, QSettings, QApplication, QDialog, QDialogButtonBox, QLabel,
  QVBoxLayout, QWidget`, then `--noconftest` on `test_api_client.py test_app_status.py
  test_docker_status.py test_lab_file.py` only.

## Manual API poke

`src/postman/practicum-api.postman_collection.json` — 33 requests incl. negative cases;
variables `baseUrl`, `labId`, `webtopLabId`. Or:

```powershell
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/labs/validate `
  -ContentType application/json -InFile examples/static-routing.json
```

## Conventions to keep (observed in the codebase)

**Core**
- Pydantic input models: `model_config = ConfigDict(extra="forbid")`; ids use
  `^[a-z][a-z0-9-]*$`; cross-field rules in `@model_validator(mode="after")` raising `ValueError`
  with lowercase, user-readable messages (`"node ids must be unique"`).
- Routes stay thin: try/except mapping `LabNotFoundError → 404`,
  `PortRecommendationUnavailableError → 409`. Runtime problems are **never** HTTP errors —
  return `success=false` + `errors[]`.
- Runtime: build argv lists, call `self._run(cmd)`; tolerate "no such …" on teardown; tests
  assert the exact argv, so update `tests/test_runtime.py` alongside any flag change.
- New endpoint checklist: model(s) in `models.py` → service method → route in `main.py` →
  tests in `test_api.py` (+`test_service.py`) → README API list → Postman collection →
  `ApiClient` method + `desktop/tests/test_api_client.py` → story notes.

**Desktop**
- Never block the UI thread: wrap calls in `CallableWorker`, keep the worker on `self`.
- Never use `QMessageBox`/native dialogs; use `dialogs.confirm()` (destructive=True for
  irreversible actions). Only exception: OS file-open picker for import (`import_lab.py`).
- Long-running API calls (start, and later stop/reset/restart) use `ApiClient.lifecycle_timeout`,
  not the 3 s `timeout`.
- Subprocess calls to `docker` must catch `OSError` (not just `FileNotFoundError`) — Tigre/06 #12.
- Labels that show errors/details use `_copyable_label()` (selectable text) — there are three
  copies of this helper (`main_window`, `designer`, `prestart_gate`); `dialogs.py` exports
  `COPYABLE_TEXT_FLAGS` — consolidate when touching.
- All Start paths go through `PreStartGateDialog`.
- Mirror server validation client-side for instant feedback, but the server stays authoritative.
- Use `QSettings("Practicum", "Practicum Desktop")` via the instance passed in, not new ones.
- Tests: inject a `FakeApiClient` and monkeypatch the module's `CallableWorker` with the shared
  `ImmediateWorker` from `desktop/tests/qt_helpers.py` (`StalledWorker` for busy states). Import
  `CallableWorker` at module level in new UI modules so this works. For QSettings use an ini file
  in `tmp_path` (`QSettings(str(tmp_path / "s.ini"), QSettings.Format.IniFormat)`), never the
  real `("Practicum", "Practicum Desktop")` store. `test_main_window.py` shows how to construct
  `MainWindow` with every collaborator monkeypatched.

**Style** — ruff, 100 cols, py312 target, `from __future__ import annotations` in desktop
modules, type hints everywhere, dataclasses for client results.

## Definition of done for a story (matches how past stories were closed)

1. Code + tests (core and/or desktop) passing locally.
2. `src/user-story-status.json`: story `status`, each AC `complete`, detailed `notes`;
   top-level `last_updated`, `latest_checkpoint`, `next_recommended_story`, phase status.
3. README/HANDOFF touched if the API surface or run instructions changed.
4. If the desktop was changed: "Manually verified running on Windows" noted (or explicitly
   "needs manual verification").
5. Update `Tigre/05` and `Tigre/08` (session log).
