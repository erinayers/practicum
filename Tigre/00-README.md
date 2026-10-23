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
| 11 | [11-user-story-review.md](11-user-story-review.md) | Gap analysis of all 38 stories: AC drift, contradictions, 22 proposed new stories, re-sequencing | Planning / before writing new stories |

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

## Resume here (state at close of 2026-10-23)

- **Uncommitted in git** (baseline commit only): `Tigre/` (all), `start-practicum.bat`,
  `stop-practicum.bat`, `README.md` (new "Quick start (Windows)" section). Suggest committing.
- **No product code changed yet.** Everything so far is review, memory, and the launcher.
- **Launcher works** on the user's Windows machine (`start-practicum.bat`); user double-clicks it.
- **Awaiting user decisions** before writing new stories: Tigre/11 §3 C1 (import auto-start vs
  gate), C2 (Save vs Save-and-Start), C3 (status→badge mapping), C8 (`.zip`), and which of
  S-1…S-22 to adopt; plus Q-1…Q-6 in Tigre/09.
- **Highest-value first code changes** (all small, testable): Tigre/06 #11 (health-check
  retry/backoff — the user actually hit this), #3 (long timeout for start/stop/reset), #2
  (start-after-stop), S-4 `DELETE /labs/{id}`; then the Labs Dashboard.
- **User's environment**: Windows, Python 3.14 in `.venv`, Docker Desktop was not running/failed
  to start during the last session — expect "Degraded" until it is.

## One-paragraph summary (if you only read one thing)

Practicum is a local-first Windows tool for reproducible Docker-based networking labs. A
FastAPI service (`src/practicum`, in-memory, shells out to the `docker` CLI) validates lab
JSON specs (nodes / networks / interfaces / manual), stores them, and starts/stops/resets
containers and bridge networks. A PySide6 desktop app (`desktop/src/practicum_desktop`) is a
pure HTTP client of that API: instructor "Designer" dialog, student lab list + pre-start gate
+ manual flyout with local progress. Phases 1–6 of the backlog are done (100 core tests +
49 desktop tests pass). **Phase 7 — closing the mockup-driven desktop UI gap — is in progress;
next recommended story is `windows-desktop-labs-dashboard`.** Everything is tracked in
`src/user-story-status.json`.
