# Tigre — Living Memory for the Practicum / eduLabs Project

This folder is the persistent working memory for AI-assisted sessions on this project.
It exists so nothing is forgotten between sessions. **Read this file first**, then follow the
read order below.

> Repo folder is named `eduLabs - Copy`, but the product and every package/module is named
> **Practicum**. Treat "eduLabs" as the workspace name and "Practicum" as the product name.

## Read order for a new session

| # | File | What it gives you | Read when |
|---|------|-------------------|-----------|
| 1 | [01-project-overview.md](01-project-overview.md) | What Practicum is, personas, repo layout, two packages | Always |
| 2 | [05-status-and-backlog.md](05-status-and-backlog.md) | Exactly where the work stands, next story, open gaps | Always |
| 3 | [08-session-log.md](08-session-log.md) | What happened in previous sessions | Always |
| 4 | [02-architecture-core-api.md](02-architecture-core-api.md) | FastAPI core: models, service, Docker runtime, ports | Touching `src/practicum` |
| 5 | [03-architecture-desktop.md](03-architecture-desktop.md) | PySide6 app: modules, threading pattern, UI conventions | Touching `desktop/` |
| 6 | [04-lab-spec-format.md](04-lab-spec-format.md) | The lab JSON contract, field by field | Changing the spec / models |
| 7 | [06-known-issues-and-tech-debt.md](06-known-issues-and-tech-debt.md) | Bugs found in review, stale docs, hygiene | Before picking work / fixing |
| 8 | [07-dev-workflow.md](07-dev-workflow.md) | How to run, test, and the conventions to keep | Before writing code |
| 9 | [09-decisions.md](09-decisions.md) | Product + technical decisions already made (don't re-litigate) | Before designing anything |
| 10 | [10-glossary.md](10-glossary.md) | Terms, names, naming conventions | As needed |
| 11 | [11-user-story-review.md](11-user-story-review.md) | Gap analysis of the original 38 stories (40 now): AC drift, contradictions, 22 proposed new stories, re-sequencing | Planning / before writing new stories |

## Rules for maintaining this folder

- **Update `08-session-log.md` at the end of every session** with what was done, what was
  verified, and what's next.
- When a story's status changes, update BOTH `src/user-story-status.json` (the project's
  canonical tracker) AND `05-status-and-backlog.md` (our summary).
- When you find a bug or debt, log it in `06-known-issues-and-tech-debt.md` with a status.
- When a decision is made (product or technical), log it in `09-decisions.md`.
- Keep facts here verifiable against the source — cite file paths and line-level details.
- `HANDOFF.md` at the repo root is the human-facing handoff; it is **stale** (see 06). This
  folder is more current. If you update HANDOFF.md, note it in the session log.

## Resume here (state at close of 2026-10-23, Session 4 — long session, 3 stories)

**Everything from Session 4 is uncommitted** on top of the single `baseline` commit
(`git status` ≈ 49 entries). Suggest the user commits before anything else. Nothing outside
the repo matters (screenshots in `/workspace/*.png` and `/tmp/fakedocker` were sandbox-only).

**Delivered this session** (all `done` in `src/user-story-status.json`, 40 stories now):
1. `windows-desktop-import-lab-file` — `import_lab.py` + `lab_file.py` + bundled `samples/`,
   **Import Lab File…** button. **Verified on Windows by the user** (flow reached Start).
2. `runtime-subnet-conflicts` (was Tigre/11 S-16) — `GET/POST /labs/{id}/networks…`, gate
   "Network Conflicts" with Remove leftover / Reset '<lab>' / Use <subnet>. **Verified on Windows
   by the user: "That worked great!"** (leftover Quick Start network removed from the gate, lab
   started — so Docker Desktop is working on the user's machine now).
3. `windows-desktop-open-node-shell` (was Tigre/11 S-11, P0) — Lab Nodes table + **Open shell**
   (docker exec in a new console). **NOT yet verified on Windows** — built at the very end.

**Windows verification checklist for the next session (ask the user):**
- [ ] Probe 1 (`examples/import-probes/1-valid-auto-start.json`): after start, does the Lab Nodes
      table show host-a/host-b as `running`? Does **Open shell** open a console with a `/ #`
      prompt? Does `ping -c 3 10.93.1.20` reply? (Risk: `cmd.exe /k` + `CREATE_NEW_CONSOLE` with
      Docker Desktop's `docker.exe` — if the window flashes/closes or shows no prompt, capture it.)
- [ ] Probe 2 (port 8000 conflict) stops at the gate with a "Use <port>" button.
- [ ] Recent-files list persists across app restarts; greyed row after moving a file.
- [ ] Importing the same sample twice → second one stops at the gate with "Used by lab '…'
      (running)" and offers Reset / Use 10.90.0.0/24.

**Known rough edges left open** (Tigre/06): #11 health-check false "Blocked" on a loaded machine
(user hit it in Session 3); #2 stop→start name conflict (blocks lifecycle story); #1 quick-start
subnet fixed at 10.50.0.0/24 (mitigated by the gate now, not fixed); S-1 persistence (leftovers
exist *because* labs vanish on API restart). Root causes of the subnet collision are still these.

**Decisions still awaiting the user** (unchanged): Tigre/11 §3 C2, C3; Q-1 duplicate import
(interim D-19 = duplicate lab); Q-2…Q-6 in Tigre/09; which of S-1…S-22 to adopt next. C1 and C8
were settled by implementation (D-2+D-21, D-18).

**Next story**: `windows-desktop-labs-dashboard`, after the backend enablers (`DELETE /labs/{id}`,
Tigre/06 #2). It should reuse `ImportLabDialog`, `PreStartGateDialog`, and absorb the Lab Nodes
table into the running view. Suggested order in Tigre/05.

**Sandbox facts that save time**: `pip install --break-system-packages pytest PySide6 ruff`
works; full Qt suite runs with `QT_QPA_PLATFORM=offscreen` (desktop 134, core 132 at close);
screenshots via `widget.grab().save()` after `app.processEvents()`; the stateful fake `docker`
recipe is in Tigre/07; **Qt swallows slot exceptions** (run `pytest -s | grep Traceback`);
**files have mixed CRLF/LF** — preserve per file (Tigre/07).

**User's environment**: Windows, Python 3.14 in `.venv`, launches with `start-practicum.bat`,
Docker Desktop working as of the end of Session 4.

## One-paragraph summary (if you only read one thing)

Practicum is a local-first Windows tool for reproducible Docker-based networking labs. A
FastAPI service (`src/practicum`, in-memory, shells out to the `docker` CLI) validates lab
JSON specs (nodes / networks / interfaces / manual), stores them, and starts/stops/resets
containers and bridge networks. A PySide6 desktop app (`desktop/src/practicum_desktop`) is a
pure HTTP client of that API: instructor "Designer" dialog, student lab list + import-and-launch
dialog + pre-start gate + manual flyout with local progress. Phases 1–6 of the backlog are done
(132 core tests + 134 desktop tests pass). **Phase 7 — closing the mockup-driven desktop UI gap —
is in progress (gate ✅, import ✅, subnet conflicts ✅, open shell ✅); next recommended story is `windows-desktop-labs-dashboard`.**
Everything is tracked in `src/user-story-status.json`.
