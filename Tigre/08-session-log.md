# 08 — Session Log

Newest entry first. Each entry: date, goal, what was done, what was verified, what's next.

---

## 2026-10-23 — Session 3: One-shot launcher script

**Goal:** Start the API and the desktop app together instead of separately.

**Done**
- Added `start-practicum.bat` (repo root): venv bootstrap + install on first run, starts uvicorn in
  its own titled window (or reuses a healthy API), waits for `/health`, runs the desktop in the
  foreground, kills the API window on exit. Flags `--dev`, `--setup`, `--help`; honours
  `PRACTICUM_API_PORT`.
- Added `stop-practicum.bat` (taskkill by window title) for leftovers after Ctrl+C.
- README: new "Quick start (Windows)" section. Tigre/07 documents the script; Tigre/11 S-2 notes it
  as an interim.

**Verified**
- Static checks only (Linux sandbox): all goto/call targets exist, parentheses balanced, CRLF
  endings. **Needs a first run on Windows** — watch for: `start` title/taskkill match, pip extras
  syntax `".\desktop[dev]"`, curl availability.

**First Windows run (user report):** both windows launched, but "the API doesn't appear to be
running". Hardened the script in response: API now runs under `cmd /k` so a crashing uvicorn
leaves its traceback visible; every health attempt prints `health=<code>`; prints the probe tool,
the `/health` body, whether the API was pre-existing, and warns (via `netstat`) if another PID
already listens on the port; import pre-check now includes uvicorn/fastapi/PySide6/httpx.
**Second Windows run (hardened script): started up fine** — API healthy, desktop connected.
Root cause of the first failure **found via the user's screenshot** (`/workspace/Screenshot
2026-10-23 173545.png`, outside the repo): desktop banner "Status: Blocked — Practicum API: ❌ The
Practicum API did not respond in time", base URL correctly `http://127.0.0.1:8000`, and "Docker: ❌
Docker Desktop is unable to start". So the API *was* up (launcher got 200); the desktop's single
3-second health check timed out under load and the app gave the misleading "run uvicorn" advice.
Logged as Tigre/06 #11 with a proposed fix (retry/backoff + better wording). The script changes
were still worthwhile for visibility but were not the fix; the second run simply wasn't loaded.
User environment note: Docker Desktop was not running / failed to start at the time. If it recurs, the launcher now
prints `health=` per attempt, the `/health` body, a "NOT started by this script" note, and a
netstat PID warning — ask the user for those lines.

**Status:** `start-practicum.bat` is verified working on Windows (2026-10-23).

**Next**: continue with the decisions listed in Session 2 (C1, C2, C3, C8; which of S-1…S-22 to
adopt), then write accepted stories into `src/user-stories/` + the JSON tracker.

---

## 2026-10-23 — Session 2: User-story gap review

**Goal:** Review all 38 existing user stories for gaps and improvements, based on the Session 1
code review.

**Done**
- Read every story file in full; cross-checked ACs in markdown vs `user-story-status.json`
  programmatically (6 stories drift); checked each "done" AC against the desktop/API code.
- Wrote `11-user-story-review.md`: executive top-10, process issues, "done-but-API-only" AC
  debt table, 12 contradictions (C1–C12), per-story edit notes for Phase 7, 22 proposed stories
  (S-1…S-22) with draft ACs and priorities, a re-sequenced Phase 7, and quick wins.

**Verified in code**
- Interface addresses equal to the network/broadcast address are accepted by the model.
- `LabService.start` runs the runtime again when status is already `starting` (no action lock).

**Headline gaps**: no desktop export / manual editor / metadata+resources authoring (instructor
loop not closable from the UI); no way for students to open a shell on a CLI node; students
must start the API by hand; no persistence although the dashboard assumes it; dashboard needs
a delete endpoint + origin/timestamps that don't exist; Restart undefined; import auto-start
contradicts the "never start blind" gate.

**Next**: get the user's decisions on C1 (import auto-start vs gate), C2 (Save vs Save&Start),
C3 (status→badge mapping), C8 (.zip), and which of S-1…S-22 to adopt; then write the accepted
stories into `src/user-stories/` and the JSON tracker.

---

## 2026-10-23 — Session 1: Full project review and memory bootstrap

**Goal:** Read the entire project, build a working memory of it in `Tigre/`, prime future
sessions. No product code was changed.

**Done**
- Read every source file in `src/practicum/` and `desktop/src/practicum_desktop/`, all tests,
  `README.md`, `HANDOFF.md`, `src/user-stories.md`, all 38 story files' key sections,
  `user-story-status.json` in full, the future-roadmap README/boundary docs, the three examples,
  the Postman collection, and the text/JS of `design/practicum-mockups.html`.
- Created Tigre files 00–10 (index, overview, core architecture, desktop architecture, spec
  format, status/backlog, known issues, dev workflow, this log, decisions, glossary).

**Verified**
- Core test suite: **100 passed** (`PYTHONPATH=src python -m pytest -q`, Python 3.12.3, fastapi
  0.121.2, pydantic 2.12.4, httpx 0.28.1 — pytest installed in-sandbox).
- Desktop non-Qt tests: **35 passed** using a PySide6 stub and `--noconftest` (PySide6 not
  installable offline). The 14 Qt tests (`test_dialogs.py`, `test_prestart_gate.py`) were not run
  here; status JSON says they pass on Windows.
- Git: one commit `59c4a9e baseline`, clean tree. No CI.

**Key findings** (details in Tigre/06)
- HANDOFF.md is stale (pre-Phase-7). `user-story-status.json` is current: Phase 7 in progress,
  next story `windows-desktop-labs-dashboard`.
- Likely bugs: stop→start fails once (container name conflict) [#2]; 3 s client timeout on
  `start` [#3]; dead/broken `create_ubuntu_quick_start_lab` [#1]; UDP probed with TCP [#4];
  QThread reassignment races [#6].
- Phase 7 dashboard story needs backend enablers that don't exist: `DELETE /labs/{id}`, and
  `ApiClient` methods for stop/reset/status/import/delete.
- Hygiene: sync-tool "Name clash" `.pyc` files, a personal `.code-workspace` inside the desktop
  package.

**Next session suggestions**
1. Confirm open questions Q-1…Q-6 in Tigre/09 with the user (esp. Q-3 persistence and Q-4
   stop/start semantics).
2. Optionally refresh `HANDOFF.md` (or make it point at `Tigre/`).
3. Start Phase 7 per the order in Tigre/05: backend enablers → Labs Dashboard.

---
