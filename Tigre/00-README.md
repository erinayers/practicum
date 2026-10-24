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
| 11 | [11-user-story-review.md](11-user-story-review.md) | Gap analysis of the original 38 stories (47 now): AC drift, contradictions (mostly resolved), 22 proposed stories (S-4/5/6/11/12/15/16 done), re-sequencing | Planning / before writing new stories |

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

## Resume here (state at close of 2026-10-24, Session 5 — Phase 7 completed)

**Everything from Session 5 is uncommitted** on top of the `baseline` commit (`git status` ≈ 60
entries, 11 new desktop modules, 12 new test modules, 7 new story files). Suggest the user commits
before anything else. Nothing outside the repo matters (`/tmp/fakedocker`, `/tmp/e2e_*.py`,
screenshots in `/tmp` were sandbox-only — recipes in Tigre/07).

**Delivered this session** (all `done` in `src/user-story-status.json`, 49 stories now incl. the
feedback-round `designer-node-catalog` and `designer-edit-existing-lab`, Phase 7
`done`): `windows-desktop-lab-lifecycle-controls`, `windows-desktop-labs-dashboard`,
`windows-desktop-embedded-lab-view`, `windows-desktop-in-app-dialogs`,
`designer-visual-topology-builder`, `runtime-image-pull-progress`, `runtime-host-port-availability`
(closed, D-30) + seven new stories (`runtime-lab-restart`, `runtime-delete-lab`,
`lab-origin-and-timestamps`, `windows-desktop-visual-theme`, `windows-desktop-create-lab-screen`,
`designer-quick-start-lab`, `windows-desktop-status-polling`). The desktop is now the mockup:
welcome → dashboard cards → create (quick start / custom) → gate → running view (Restart / Stop /
Reset, embedded QWebEngineView, instructions flyout, Lab nodes + Open shell, status bar).

**NOT verified on Windows — first thing next session**: run `start-practicum.bat` with Docker
Desktop and walk the checklist in Tigre/05 ("What is NOT verified on Windows"). Highest-risk
items: QtWebEngine present in the venv (`PySide6-Addons`), webtop in the embedded view
(http 3000 / https 3001) — also the default **Ubuntu Desktop** quick start template (D-35), `docker pull` progress lines on Windows Docker Desktop (non-TTY →
layer-based percent expected), Open shell (`cmd /k`, Tigre/06 #14), apt-get inside the quick
start container (needs internet).

**Known rough edges left open** (Tigre/06): #6 single worker attributes in gate/designer
(mitigated), #14 Open shell unverified, #17 no cancel for a hung background start, #18 quick
start package install needs internet. S-1 persistence is the biggest product gap (dashboard is
empty after every API restart).

**Decisions awaiting the user** (Tigre/09): Q-3 persistence location, Q-5 naming, Q-7 what the
"Instructor setup" toggle should hide for students, Q-8 Edit lab (S-7) before/after persistence.

**Engineering rules added this session** (Tigre/07): no lambdas capturing `self` on child-widget
signals (`widgets.bind()`), no bare `QFrame {}` selectors (`style_frame`), `discard()` when
rebuilding rows, patch `CallableWorker` in every module the widget imports, fixtures must stop
pollers on teardown, always check the pytest **exit code** (teardown crashes hide behind
"passed").

**Sandbox facts that save time**: `pip install --break-system-packages pytest PySide6 ruff`
(PySide6 6.12 incl. WebEngine); full Qt suite with `QT_QPA_PLATFORM=offscreen` (desktop 270,
core 159 at close); QtWebEngine works offscreen; screenshots via `widget.grab().save()` after
`processEvents()` + `sendPostedEvents(None, DeferredDelete)`; the stateful fake `docker` recipe
(now with `image inspect`/`pull`/`start`) and the real-app e2e driver pattern are in Tigre/07;
**files have mixed CRLF/LF** — preserve per file; git root is `/workspace` (repo folder
`Practicum/`).

**User's environment**: Windows, Python 3.14 in `.venv`, launches with `start-practicum.bat`,
Docker Desktop working as of the end of Session 4.

## One-paragraph summary (if you only read one thing)

Practicum is a local-first Windows tool for reproducible Docker-based networking labs. A
FastAPI service (`src/practicum`, in-memory, shells out to the `docker` CLI) validates lab
JSON specs (nodes / networks / interfaces / manual), stores them, and starts (with real image
pull progress) / stops / restarts / resets / deletes containers and bridge networks. A PySide6
desktop app (`desktop/src/practicum_desktop`) is a pure HTTP client of that API, built
screen-for-screen from `design/practicum-mockups.html`: welcome, labs dashboard, create (quick
start template or custom designer with a schematic topology), pre-start gate, import-and-launch,
and a running view with lifecycle controls, an embedded web view, the instructions flyout and
Open shell. **Phases 1–7 are done (159 core + 270 desktop tests); Session 5's UI has not yet
been run on Windows — that smoke run is the next step, then persistence (S-1).**
Everything is tracked in `src/user-story-status.json`.
