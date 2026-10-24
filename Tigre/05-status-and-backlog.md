# 05 — Status and Backlog

Canonical source: `src/user-story-status.json` (`last_updated: 2026-10-23`,
`current_phase: phase-7`, `next_recommended_story: windows-desktop-labs-dashboard`).
This file is our readable summary — keep both in sync.

## Phase summary

| Phase | Title | Status |
|---|---|---|
| 1 | Strengthen the Lab Spec (metadata, docker resources, manual) | done |
| 2 | Validate / Export / Import / Preview | done |
| 3 | Runtime API + Docker control (+ ports, env, cmd, shm, mappings, host-port checks) | done* |
| 4 | Windows application shell (launch, local API, port-conflict UI) | done |
| 5 | Basic Designer workflows (create, nodes, networks, connect) | done |
| 6 | Student learning experience (manual flyout, progress) | done |
| **7** | **Close the desktop UI gap (mockup-driven)** | **in_progress** |

\* Phase 3 is marked done but `runtime-host-port-availability` is still `in_progress` (one AC
open: export is not guarded by port check).

## Phase 7 — story by story

| Order | Story id | Status | Summary of what's needed |
|---|---|---|---|
| 22 | `windows-desktop-in-app-dialogs` | **in_progress** (component done) | `dialogs.py` `confirm()` exists and is used by Reset Progress. File-picker AC met 2026-10-23 (import's `QFileDialog` is the only native dialog; no `QMessageBox` anywhere). Remaining 2 ACs wait on Dashboard Delete and Lifecycle Reset to consume `confirm()`. |
| 23 | `windows-desktop-labs-dashboard` | **not_started — NEXT** (import flow now exists to plug in) | Home screen listing labs as cards (name, origin/meta line, status badge Running/Stopped/Draft). Running→Open (no new Start call); Stopped→Start via PreStartGateDialog; Draft→Edit/Delete; Delete with `confirm()`. Zero labs → welcome screen. Backed by `GET /labs` (+ `GET /labs/{id}/status`). **Blocker:** there is no `DELETE /labs/{id}` endpoint and no `ApiClient.delete_lab/get_status` — will need small backend + client additions. No "origin" metadata exists in the spec either. |
| 24 | `windows-desktop-prestart-lab-gate` | done | `PreStartGateDialog`. Reused by import (conflict path) since 2026-10-23; dashboard still to come. |
| 25 | `windows-desktop-import-lab-file` | **done** (2026-10-23; Windows smoke run pending) | `ImportLabDialog` (`import_lab.py`) + `lab_file.py` + bundled `samples/`; **Import Lab File…** button in MainWindow. Conflict-free → auto-start → lab selected + manual open; conflicts or failed port check → `PreStartGateDialog`. Duplicates = new lab (D-19). Dashboard must reuse `ImportLabDialog` for "Import Existing Lab". |
| 25b | `runtime-subnet-conflicts` (new, was Tigre/11 S-16) | **done** (2026-10-23; needs Windows verification) | `GET /labs/{id}/networks` + apply-recommendation / remove-leftover; gate "Network Conflicts" with Remove leftover / Reset '<lab>' / Use <subnet>; import hands over to the gate. Built because the Windows smoke run of import failed on a leftover Quick Start network. |
| 25c | `windows-desktop-open-node-shell` (new, was Tigre/11 S-11 P0) | **done** (2026-10-23; needs Windows verification) | Lab Nodes table + **Open shell** (docker exec in a new console) in MainWindow; `ApiClient.get_status`. The running view / embedded-lab-view should absorb this table. |
| 26 | `windows-desktop-lab-lifecycle-controls` | not_started | Running-lab toolbar: Restart, Stop (no confirm), Reset (destructive style + `confirm()`). Needs `ApiClient.stop_lab/reset_lab`; Restart = stop+start (note Tigre/06 #2). Reset must not touch manual progress. Prevent overlapping lifecycle calls. |
| 27 | `windows-desktop-embedded-lab-view` | not_started | Replace `webbrowser.open` with embedded `QWebEngineView` (PySide6 QtWebEngineWidgets) docked beside the manual flyout; URL bar; picker when multiple browser ports; "open in system browser" fallback; waiting state while service boots. |
| 28 | `designer-visual-topology-builder` | not_started | Re-skin DesignerDialog into Machines cards / schematic Network Topology / Networks panels. Same data, validation, and API calls. No drag-and-drop (that's a paid roadmap item). |
| 29 | `runtime-image-pull-progress` | not_started (backend) | Make `POST /start` non-blocking; explicit `docker pull` per node parsing streamed progress; per-node in-progress state in `GET /status`; per-node failure attribution. Then desktop replaces fake timers with polling. |

## Open gaps carried from earlier phases

1. `GET /labs/{id}/export` not guarded by port-conflict check (`runtime-host-port-availability`
   last AC). Decide: block export on conflicts, or warn only (export is portable — host-port
   conflicts are machine-specific, so blocking export is arguably wrong; see Tigre/09).
2. Port availability should be re-checked immediately before start (story edge case).
3. `windows-desktop-port-conflict-ui` notes "needs manual verification with a real port
   conflict on Windows".

## Suggested implementation order for Phase 7 (my recommendation, 2026-10-23)

1. **Small backend enablers first** (keep desktop stories pure-UI afterwards): add
   `DELETE /labs/{id}` + `LabService.delete` (+ tests); add `ApiClient.delete_lab`,
   `stop_lab`, `reset_lab`, `get_status` (`import_lab` ✅ done). Fix Tigre/06 #2 (start after
   stop) since the dashboard/lifecycle stories will hit it immediately (#3 ✅ fixed 2026-10-23).
2. `windows-desktop-labs-dashboard` (next recommended) — this restructures MainWindow into
   screens (welcome / dashboard / running). Consider a `QStackedWidget` with per-screen widgets.
   Reuse `ImportLabDialog` + `MainWindow._apply_pending_selection` pattern for "Import Existing Lab".
3. `windows-desktop-lab-lifecycle-controls` — closes the remaining in-app-dialogs ACs.
4. ~~`windows-desktop-import-lab-file`~~ ✅ done 2026-10-23 (Session 4).
5. `windows-desktop-embedded-lab-view` — re-point the import landing (`_apply_pending_selection`)
   at the new running view.
6. `designer-visual-topology-builder`.
7. `runtime-image-pull-progress` (largest; backend + desktop polling).

## Story-status bookkeeping format (for updating `user-story-status.json`)

Each story: `{id, epic, title, status (not_started|in_progress|blocked|done), notes,
acceptance_criteria: [{text, complete}]}`. Also update top-level `last_updated`,
`latest_checkpoint` (prose), `next_recommended_story`, `current_phase`, and the phase's
`status`. The `notes` field is where implementation detail lives — keep it specific (file
names, class names, test counts), matching the existing style.
