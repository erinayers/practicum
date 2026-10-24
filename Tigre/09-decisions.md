# 09 — Decisions Log (product + technical)

Decisions already made in the project docs/code. **Don't re-litigate these without the user.**
Format: D-<n> · date (if known) · decision · source.

## Product

- **D-1 · Open-core boundary.** The full local loop (create, validate, export, import, run with
  Docker, read manual, stop, reset) stays free and open source forever. Paid = hosted marketplace,
  revenue share, advanced visual designer (drag/drop canvas, auto-layout), classrooms, cloud sync,
  SSO, analytics, enterprise. Source: `src/future-roadmap/README.md`,
  `open-source-core-sustainability/open-core-boundary.md`.
- **D-2 · 2026-10-11 · Import auto-starts.** A conflict-free imported lab proceeds straight to
  the start sequence and running view; if port conflicts exist it stops at the pre-start gate.
  Source: `student-import-spec.md`, `windows-desktop-import-lab-file.md`.
- **D-3 · In-app dialogs only.** No native/Qt message boxes; one reusable confirmation component
  (`dialogs.py`). Only native dialog allowed: the OS file-open picker. Source:
  `windows-desktop-in-app-dialogs.md`.
- **D-4 · Single pre-start gate.** `PreStartGateDialog` is the one authority that shows preview
  + port conflicts and gates Start, from every entry point. Source: `prestart_gate.py` docstring,
  `windows-desktop-prestart-lab-gate.md`.
- **D-5 · Reset ≠ Reset Progress.** Runtime reset (containers/networks) never clears local manual
  progress; manual progress is cleared only by the flyout's own "Reset Progress". Reset is
  destructive-styled and confirmed; Stop/Restart are not confirmed. Source:
  `student-reset-lab.md`, `windows-desktop-lab-lifecycle-controls.md`.
- **D-6 · Visual topology builder stays basic.** Phase-7 designer upgrade = cards + schematic
  auto-rendered view, same data model; no drag-and-drop/auto-layout (paid roadmap). Source:
  `designer-visual-topology-builder.md`.
- **D-7 · Manual progress is local-only.** Stored in QSettings, never sent to the API, never
  modifies the instructor's spec. Source: `manual-track-progress.md`.
- **D-8 · Target platform is Windows** (student-owned hardware, Docker Desktop). Linux/macOS
  aren't targets though nothing in the code is Windows-specific.

- **D-18 · 2026-10-23 · `.zip` lab files are not accepted (yet).** The import picker filters on
  `*.json`; a `.zip` chosen via "All files" is rejected with "Bundles aren't supported yet — choose
  the .json lab export". Re-enable when a bundle format (Tigre/11 S-13) is defined. Resolves C8.
- **D-19 · 2026-10-23 · Importing the same file twice creates a second lab** (interim). The API
  assigns a fresh id per import and nothing in the spec identifies a lab stably. Q-1 stays open;
  S-14 (`lab_key`) is the path to "resume existing".
- **D-21 · 2026-10-23 · Import falls back to the gate whenever it cannot prove "no conflicts".**
  If `GET /labs/{id}/ports` fails mid-flow, the lab is treated as conflicted (`gate_required`)
  and `PreStartGateDialog` opens rather than starting blind. Keeps D-2 and D-4 consistent.

## Technical

- **D-9 · Docker via CLI subprocess, not the SDK.** `DockerRuntime` builds `docker …` argv and
  runs it; tests assert argv. Keep it that way unless a story needs streamed output (image pull
  progress story suggests parsing `docker pull` output — still CLI).
- **D-10 · In-memory lab store.** No DB; everything lost on API restart. Persistence is not in
  scope for any current story (the Labs Dashboard story implicitly assumes labs survive — note
  this when building it; may need a simple JSON-file store eventually).
- **D-11 · Polling over push.** Progress/status will be exposed through a richer
  `GET /labs/{id}/status` polled by the desktop, not SSE/WebSockets. Source:
  `runtime-image-pull-progress.md`.
- **D-12 · Desktop has no business logic.** Validation/orchestration/port logic is server-side;
  desktop mirrors simple input rules only for UX.
- **D-13 · Deterministic Docker names** `practicum-{lab.id[:8]}-{id}` and labels
  `practicum.lab_id / practicum.node_id / practicum.network_id` — tooling and cleanup rely on them.
- **D-14 · Gateway = highest free usable IP** in each subnet (so instructor addressing like
  `.1` for routers stays available).
- **D-15 · Structured errors over HTTP errors** for runtime failures (200 + `success=false`);
  404/409/422 only for lookup/conflict/schema problems.
- **D-16 · Embedded lab view = QWebEngineView** from PySide6 QtWebEngineWidgets (already bundled;
  no new dependency). Source: `windows-desktop-embedded-lab-view.md`.
- **D-20 · 2026-10-23 · Schema major-version support is enforced server-side.**
  `LabDefinition.schema_version` accepts only majors in `SUPPORTED_SCHEMA_MAJOR_VERSIONS = (1,)`
  (minor versions pass); validate/create/import all report it as a structured `schema_version`
  error. The desktop never inspects `schema_version` (D-12).
- **D-22 · 2026-10-23 · Lifecycle calls get their own long timeout** (`ApiClient.lifecycle_timeout`,
  900 s) separate from the 3 s lookup timeout. Stop/reset/restart wrappers must use it too.
- **D-23 · 2026-10-23 · Sample labs ship inside the desktop package** (`practicum_desktop/samples/`)
  as byte-identical copies of `examples/`, guarded by `test_bundled_samples_match_repo_examples`.
  Update both places together.
- **D-24 · 2026-10-23 · Subnet conflicts are detected before Start and fixed from the gate.**
  `GET /labs/{id}/networks` compares the lab's subnets with every Docker network (not just
  Practicum's). Owner classes: listed lab → offer Reset; Practicum-labelled network whose lab
  is unknown (leftover) → offer Remove (containers + network, confirmed); foreign Docker network
  → never touched, offer a free subnet only. Recommendations come from `10.90.0.0/16`, same
  prefix length, avoiding all Docker networks and all known labs. Moving a subnet keeps each
  interface's host offset and warns that the manual may be stale. Source: `runtime-subnet-conflicts.md`.
- **D-17 · Quick-start subnets should come from `10.90.0.0/16`** to avoid colliding with
  hand-authored labs (intended; not yet wired — see Tigre/06 #1).

## Open questions (need the user)

- **Q-1** Duplicate import: importing the same file twice → duplicate lab, or detect and offer
  resume? (`windows-desktop-import-lab-file.md` edge case.) *Interim behaviour = duplicate lab
  (D-19); still needs a real decision.*
- **Q-2** Export + port conflicts: block export, warn, or ignore? Host-port conflicts are
  machine-specific, so blocking a portable export seems wrong; suggest "warn only" and close the
  AC that way. (`runtime-host-port-availability` last AC.)
- **Q-3** Should labs persist across API restarts before the Dashboard ships? (Dashboard UX
  assumes "returning users see their labs".)
- **Q-4** Stop → Start semantics: `docker start` existing containers (preserves container state)
  vs recreate. Affects Tigre/06 #2 and the Restart control.
- **Q-5** Repo/product naming: keep "eduLabs" as the folder/workspace and "Practicum" as the
  product, or unify?
- **Q-6** Lab "origin" (imported / quick start / custom) for dashboard cards: add to the spec,
  or track desktop-side only?
