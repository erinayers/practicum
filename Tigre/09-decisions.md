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
- **D-10 ? Original in-memory lab store.** The initial service kept labs in memory, so restarts
  lost the dashboard contents. Superseded for planned work by D-51.
- **D-51 ? 2026-10-26 ? Local persistence uses SQLite.** The embedded database file ships as app
  data and runs in the Practicum process; it is not a Docker container or separate server.
  Packaged Windows use stores it in the per-user local application-data directory; development
  can override the path. Docker remains authoritative for runtime state and is reconciled on API
  startup. Source: user preference in persistence planning; stories in
  `src/user-stories/backend-storage/`.
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
- **D-17 · Quick-start subnets come from `10.90.0.0/16`** to avoid colliding with hand-authored
  labs — wired 2026-10-24 (`quickstart.build_quick_start_lab` avoids every known lab's subnets).
- **D-25 · 2026-10-24 · Delete resets Docker resources first.** `DELETE /labs/{id}` removes the
  lab's containers/networks (unless it never started) and only then forgets it; if cleanup fails the
  lab is kept (status `error`, `last_error`) and the API answers 409. Nothing is orphaned silently.
  Source: `runtime-delete-lab.md`.
- **D-26 · 2026-10-24 · Status → badge mapping** (resolves Tigre/11 C3): `running` Running,
  `stopped` Stopped, `defined` **Ready** (not "Draft": every stored lab is validated), `error`
  Error (+ `last_error` shown, Reset offered), `starting`/`stopping` Starting…/Stopping… (busy;
  only Open). `theme.STATUS_BADGES`.
- **D-27 · 2026-10-24 · Node "role" is derived, not stored** (resolves C12): 0 interfaces
  "unconnected", 1 "host", ≥2 "gateway" (`widgets.node_role`). No data-model change.
- **D-28 · 2026-10-24 · The embedded view trusts self-signed certificates for localhost only**
  (`LocalLabPage.certificateError`), and probes `http://` before `https://` per published port.
- **D-29 · 2026-10-24 · Designer Save does not start** (resolves C2): **Save Lab** stores and
  returns to the dashboard; **Save & Start** stores and opens the gate. Quick start's **Create
  Lab** = save + gate (the mockup's straight-to-running is replaced by the gate, per D-4).
- **D-30 · 2026-10-24 · Export is not blocked by host-port conflicts** (resolves Q-2 / C11): the
  exported spec is portable and host ports are machine-specific. Start re-checks ports
  server-side instead (`runtime-host-port-availability` last AC narrowed to Start).
- **D-31 · 2026-10-24 · Start stays synchronous by default; `?wait=false` is the async variant.**
  `POST /start` without the flag blocks as before (existing tests/Postman unchanged); the desktop
  always uses `wait=false` + `GET /status` polling for real progress. Lifecycle calls on a lab that
  is `starting`/`stopping` are refused with 409 (action lock).
- **D-32 · 2026-10-24 · Quick start packages become the node command**
  (`bash -c "apt-get update && apt-get install -y … || warn; exec sleep infinity"`) and steps
  become one manual section each with a single "Done: <title>" task — no spec changes for either.
  The Windows template is listed but disabled until Windows-container mode is supported.
- **D-33 · 2026-10-24 · Origin/timestamps live on the stored `Lab`, never in the exported spec**
  (resolves Q-6): `origin`, `source_file`, `created_at`, `last_started_at`, `last_error` =
  `LAB_RUNTIME_FIELDS`, stripped by export and preserved by definition rewrites.
- **D-35 · 2026-10-24 · Quick start defaults to the Ubuntu *Desktop* template** (user request: "a
  simple image for simple or non-IT related labs"). `lscr.io/linuxserver/webtop:ubuntu-xfce` on
  3000/3001 with `command: null`, `TITLE`, and packages via the LinuxServer
  `universal-package-install` mod (`DOCKER_MODS` + `INSTALL_PACKAGES=a|b|c`); the terminal-only
  `ubuntu:22.04` template stays one click away (apt-get command path). Flip `DEFAULT_TEMPLATE`
  in `quickstart.py` if the user prefers the terminal as default.
- **D-36 · 2026-10-24 · Machine presets are desktop-side.** `node_catalog.PRESETS` produce ordinary
  nodes; the API/spec know nothing about presets (the designer re-derives them for display when
  editing). The only spec change they needed is `resources.sysctls` (namespaced keys only).
- **D-37 · 2026-10-24 · Editing replaces the definition and resets the lab.** `PUT /labs/{id}`
  refuses running labs (409), removes a stopped lab's containers/networks, keeps id/origin/
  timestamps, returns the lab to `defined`. Manual progress (keyed by lab id) survives.
- **D-38 · 2026-10-24 · No emoji in the UI** (user feedback); status = words + colour, icons =
  geometric glyphs. The app forces the Fusion style and a light palette regardless of the OS theme.
- **D-39 · 2026-10-24 · Export uses the system save picker** — the second (and last) sanctioned
  native dialog (D-3 amended).
- **D-40 · 2026-10-24 · Practicum resources of unknown labs are removed at API startup.** Labs are
  in memory only, so after a restart the previous session's containers/networks can never be
  used again; the API sweeps everything carrying a `practicum.lab_id` label it does not know
  (never other Docker resources). Revisit when persistence (S-1) lands: then the sweep must only
  remove resources of labs that were deleted, and reconcile the rest.
- **D-41 · 2026-10-24 · Worker threads are self-registering (`ManagedThread`).** Screens may keep
  single worker attributes again; a running thread cannot be destroyed by losing its reference.
- **D-34 · 2026-10-24 · No lambdas capturing `self` on child-widget signals** (engineering rule
  from Tigre/06 #15); `widgets.bind()` is the sanctioned way to pass a payload with a click.
- **D-42 · 2026-10-25 · Practicum reads Docker Desktop's engine mode, never switches it.** The
  switch (Linux ↔ Windows containers) is machine-wide, restarts the engine, may stop other
  people's containers and may need elevation, so every surface (Create screen panel, gate
  "Container engine" check, import flow, `POST /start`) only *reports* the mode with the Docker
  Desktop instructions and a Retry. Two read-only probes exist on purpose: the desktop's own
  `docker info` (works when the API is down; status chip + Create screen) and `GET /docker/engine`
  (server-authoritative for Start). Source: `windows-desktop-windows-container-readiness.md`.
- **D-43 · 2026-10-25 · A node's OS and shell are declared in the spec, not derived.**
  `Node.os` (`linux` default, `windows`) and `Node.shell` (None = OS default) are portable spec
  fields: the runtime picks the network driver (`bridge`/`nat`), the start-time engine check and
  the status-note command from `os`; Open shell picks bash→sh / PowerShell / cmd from `shell`.
  One OS per lab (Docker serves one kind at a time). Guessing from image names was rejected as
  unreliable (custom registries, tags). Source: `windows-desktop-open-windows-shell.md`.
- **D-44 · 2026-10-25 · Windows Server Core tags are pinned from a host-build matrix.**
  `quickstart.WINDOWS_IMAGES` (ltsc2025 ≥ 26100, ltsc2022 ≥ 20348, ltsc2019 ≥ 17763) and
  `windows_image_for_host(build)` = the newest tag ≤ the daemon host's build (from `docker info`
  `KernelVersion`); unknown build → ltsc2022; older hosts are refused. Never a floating tag.
  Revisit when Microsoft publishes a new LTSC or if process isolation on client builds bites
  (Tigre/06 #26 f).
- **D-45 · 2026-10-25 · Windows tools come from Chocolatey, installed by a PowerShell init passed
  as `-EncodedCommand`.** winget is not available in Server Core; Chocolatey is the documented,
  unattended path. The script (`WINDOWS_INIT_SCRIPT`) is generic — the package list is in the
  node's `environment.PRACTICUM_PACKAGES` so exported specs stay readable — installs one package
  at a time (failures name the package), keeps the same status-marker contract as the Ubuntu
  script (`C:\practicum\packages.status`, read by `GET /status`, printed by the PowerShell
  profile) and ends in a keep-alive loop. `-EncodedCommand` because a multi-line script with
  quotes cannot be passed reliably through Docker's Windows command-line escaping.
- **D-46 · 2026-10-25 · Icons are requested by meaning from one module.** `icons.py` owns the
  file names and meanings of `design/icons.png`; screens ask for `success`/`error`/`warning`/
  `back`/`forward`/`play`/`terminal`/`desktop`/`tools` and never load files themselves. Black
  icons are shipped as ink masks and tinted per context (white on primary buttons, muted when
  disabled); the coloured status icons are never tinted. Missing assets degrade to null icons /
  text glyphs, never to a failure. Every icon-only control has a tooltip and accessible name, and
  every state is also worded (D-38 amended: icons join words + colour; still no emoji).
- **D-48 · 2026-10-25 · A port or subnet fix recreates the lab's machines.** Stop keeps
  containers so Start can `docker start` them (D-4/Q-4: state preserved). But a container
  carries its port mappings and addresses from creation, so after the gate moves a port or a
  subnet, reusing it would bring back the *old* mapping - and the old session data the user
  saw as "persisting". `LabService._store_rewritten_definition` therefore resets the lab's
  Docker resources (status → `defined`) whenever a rewrite lands on a lab that has run, and
  the result says so (`machines_reset`) so the gate can tell the user the machines start
  fresh. A never-started lab is rewritten without touching Docker; a cleanup failure keeps the
  old definition (409). Edit (`PUT`) already behaved this way (D-37). Source: user report.
- **D-50 · 2026-10-25 · Windows (and macOS) guest labs are a paid-tier capability; Linux labs stay
  the free core.** Rationale: Docker's Windows-container mode needs Windows
  Pro/Enterprise/Education (Hyper-V + Containers), which Windows Home students do not have;
  macOS guests need Apple hardware under Apple's licence. The Phase 8 implementation stays as
  built; gating, an edition/eligibility check, a hosted runtime and the macOS counterpart are
  *stories only* for now (`src/future-roadmap/premium-lab-platforms/`). Authoring, validating,
  importing and exporting such labs remain free (open-core boundary addendum). Source: user
  scope change 2026-10-25.
- **D-49 · 2026-10-25 · Screenshot evidence is per step, local, and part of the results.**
  The instructor flags a step (`requires_screenshot`); the student captures the embedded lab
  view (what Practicum renders — never the whole screen, which could expose unrelated windows)
  or uploads an image; the PNG lives under the app's data folder and is referenced from the
  same local progress store as the ticks, so it is never in the spec and leaves the machine
  only inside the exported results (embedded in JSON, copied beside Markdown, bundled in ZIP).
  A requested screenshot counts as a progress item, so "all complete" means evidence attached.
  Source: user request; `manual-track-progress.md` addendum.
- **D-47 · 2026-10-25 · The manual is authored as steps, in one shared editor.** Both the quick
  start and the Custom Lab designer use `manual_editor.ManualStepsEditor`: a step = one manual
  section (title + Markdown details) with one generated "Done: <title>" task, which is what
  the instructions flyout renders. Hand-authored specs that carry richer sections survive an
  edit untouched (`QuickStartStep.section_id` / `tasks` ride along; only the task the editor
  generated itself is regenerated on rename). Rationale: one mental model for instructors, one
  rendering for students, no second spec shape. Source: `designer-author-manual.md`.
  Addendum (user review): when a needed meaning has no artwork on the sheet, the slicing tool
  may *derive* an icon in the sheet's own language (measured geometry of the black discs) and
  mark it `derived=True` — today `refresh` and `stop` — rather than fall back to a text glyph
  beside real icons; real artwork replaces it when supplied.

## Open questions (need the user)

- **Q-1** Duplicate import: importing the same file twice → duplicate lab, or detect and offer
  resume? (`windows-desktop-import-lab-file.md` edge case.) *Interim behaviour = duplicate lab
  (D-19); still needs a real decision.*
- ~~**Q-2** Export + port conflicts~~ → resolved by D-30 (not blocked).
- ~~**Q-3** Persistence format and location~~ ? resolved 2026-10-26: SQLite in per-user local
  application data for packaged Windows use, with a development path override (D-51).
- ~~**Q-4** Stop → Start semantics~~ → resolved: `docker start` of the existing containers
  (`runtime-lab-restart`), container state preserved; Reset is the way to recreate.
- **Q-5** Repo/product naming: keep "eduLabs" as the folder/workspace and "Practicum" as the
  product, or unify?
- ~~**Q-6** Lab "origin"~~ → resolved by D-33 (API-side bookkeeping on the stored lab).
- **Q-7** (new) Should the quick start's **Instructor setup** toggle do more than reveal
  author/version/description — e.g. hide the step editor for students? Today it only reveals the
  metadata fields.
- ~~**Q-7**~~ partly answered by usage: the step editor is the manual editor everywhere
  (quick start and designer) since 2026-10-25; the Instructor setup toggle still only reveals
  metadata.
- **Q-10** (new, 2026-10-25) Plan shape for premium platforms: per-student licence, an
  instructor/course licence that covers students, or institution capacity on the hosted runtime?
  Also: should a free install keep the Windows template *visible with a Pro chip* (the stories
  assume yes) or hide it entirely?
- **Q-9** (new, 2026-10-25) Windows quick start on a Windows 10 host: `ltsc2019` is what the
  matrix picks (build 19045 < 20348). Is Windows 10 a target at all, or can the template require
  Windows 11 / Server 2022 and always use `ltsc2022`? Also: should the Custom Lab designer get a
  "Windows host" preset (today a Windows lab can only be edited, not composed, there)?
- ~~**Q-8** Edit lab before/after persistence~~ → done before (user request, `designer-edit-existing-lab`).
