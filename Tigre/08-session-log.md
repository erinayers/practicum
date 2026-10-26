# 08 — Session Log

Newest entry first. Each entry: date, goal, what was done, what was verified, what's next.

---

## 2026-10-26 ? Public website stories drafted

**Goal**: define how Practicum can market and distribute the open-source app through a website.

**Done**: added Phase 10 and four stories covering product positioning for instructors/students, canonical release downloads, getting started/help, and project transparency/contribution. Added the project-website epic index, updated the canonical status tracker, and summarized the phase in the backlog. The stories preserve the open-core boundary and treat hosted/paid features as future plans.

**Verified**: parsed the story-status JSON and confirmed each new story is indexed in Phase 10. No website code or hosting has been created.

**Next**: choose a static site implementation/hosting approach when ready to build; the release page should continue to link to canonical GitHub Releases.

---

## 2026-10-26 ? Persistence stories drafted

**Goal**: turn the agreed local SQLite approach into reviewable backlog stories.

**Done**: added Phase 9 and three stories: durable lab records (`lab-persistence-sqlite`), Docker runtime reconciliation on API startup (`lab-runtime-reconciliation`), and per-user/configurable database location (`local-data-directory`). Updated the canonical story tracker, resolved Q-3 and recorded D-51 (embedded SQLite; per-user Windows app-data; development override), and updated the suggested backlog order. Implementation is not started.

**Verified**: parsed `src/user-story-status.json` successfully and checked that all three new stories are listed in Phase 9.

**Next**: implement `lab-persistence-sqlite`; this work does not require the unavailable Windows-container setup.

---

## 2026-10-25 — Session 6: Phase 8 completed — Windows Quick Start (readiness, template, PowerShell, tools) + design icons

**Goal (user):** "complete all of the user stories under phase 8" — US 1 Windows container
readiness, US 2 Windows quick start template, US 3 Open PowerShell, US 4 Windows tools, and
"Use Design Icons Across the Desktop UI".

**Order followed:** core spec + runtime (`Node.os/shell`, `GET /docker/engine`, engine
re-check, `nat` driver) → icon assets + `icons.py` + `MessageBanner`/theme → icons applied
screen by screen → desktop readiness probe (`docker_status`) → Windows template / tool catalog /
init script → Create screen gating + readiness panel → `MainWindow` engine refresh → PowerShell
shell + running view → gate engine check → import engine stage → tests → screenshots → live-API
e2e with a fake Windows/Linux `docker` → docs.

**Done (core, `src/practicum`)** — 204 tests (was 173)
- `models.py`: `Node.os` (`linux`|`windows`), `Node.shell` (`bash`|`sh`|`powershell`|`cmd`,
  None = OS default, `effective_shell`), validators (shell fits OS; no `shm_size_mb`/`sysctls` on
  Windows; all nodes share one OS), `LabDefinition.container_os`, `LabPreview.container_os`,
  `DockerEngineInfo`.
- `runtime.py`: `engine_info()` + `parse_engine_info` (`docker info --format '{{json .}}'`:
  `OSType`, `ServerVersion`, `OperatingSystem`, `KernelVersion` → `host_build`, `Isolation`;
  daemon-down JSON with `ServerErrors` handled), `_require_engine_os` at the top of `start`
  (specific switch-instruction failure before anything is created; unknown mode lets Docker
  decide so the generic test fake still works), `NETWORK_DRIVERS` (`nat` for Windows labs),
  `CONTAINER_NOTE_COMMANDS` (`cmd /c type C:\practicum\packages.status`). `service.docker_engine()`,
  `main.py` `GET /docker/engine`. Postman +3 requests.
- Tests: `test_models` (+6), `test_runtime` (+9: parse, argv, refusal both ways, nat + PowerShell
  argv, unknown mode, Windows note), `test_api` (+6: engine endpoint, os/shell export→import
  round trip, preview `container_os`, mixed-OS rejection, structured start failure).

**Done (desktop, `desktop/src/practicum_desktop`)** — 350 tests (was 291, incl. the 3
pre-existing `test_docker_status` failures — `creationflags` — now fixed), 1 new module
- `icons.py` (new) + `assets/icons/*.png` cut from `design/icons.png` by
  `tools/slice_design_icons.py` (flood-fill matte removal keeps the white check/cross/bang;
  black icons stored as ink masks for tinting). `ICONS` meanings, cached multi-size `QIcon`s with
  tint + disabled states, `icon_label`, `set_button_icon` (trailing icons via RTL + padding),
  `icon_html`; null-safe when assets are missing.
- `widgets.py`: `MessageBanner` (icon + copyable text; `NoteBanner` now subclasses it),
  `StatusPill` with icons by colour, `BackLink` icon, `make_button(icon=, icon_trailing=)`.
  `theme.py`: `BANNER_COLOURS`/`_banner_rules` for both banner shapes. Applied across
  `main_window` (chip, check lines via `<img>`), `dashboard` (origin tiles, Start, link arrow,
  blocked banner), `create_lab` (cards, template rows, CTAs, readiness panel), `running_view`
  (back, Start lab, Open shell/PowerShell, Docker light, feedback banner), `prestart_gate`
  (banners, Start Lab, engine panel), `progress_panel` (ready/failed marks), `manual` (done
  markers, Mark step complete), `designer` (validation banner, Save & Start), `embedded_view`.
- `docker_status.py` rewritten: JSON `docker info` → `DockerStatus{os_type, server_version,
  operating_system, host_build, isolation}`, `windows_container_readiness()` (three states +
  next action + doc URLs), `check_windows_container_readiness()`. `app_status.py`: Windows-mode
  note, `AppStatus.windows_containers`.
- `quickstart.py`: Windows template (kind/os/shell, 2 vCPU/2 GB, default tool `git`),
  `WindowsImage`/`WINDOWS_IMAGES`/`windows_image_for_host` (D-44), `WINDOWS_TOOL_CATALOG` (15
  Chocolatey ids) + kind-aware `catalog_option`/`packages_for_options`, `validate_package_name(kind)`,
  `WINDOWS_INIT_SCRIPT` + `windows_node_command` (`-EncodedCommand`, D-45) +
  `windows_package_environment`, `QuickStartDraft.windows_host_build`, per-template picker wording.
- `create_lab.py`: `template_availability()`, `TemplateOption.set_available/inspected`,
  `WindowsReadinessPanel` (state icon, next action, Docker + Microsoft links, Retry),
  `CreateLabScreen.set_docker_status/readiness_retry_requested`, fallback selection when the
  engine switches; `QuickStartScreen` Windows wording + `set_windows_host_build`.
- `main_window.py`: `_apply_status` (one renderer for panel/chip/running view/create screen),
  `refresh_engine` (worker `check_docker`; Retry + each Create visit), `show_quick_start` guard,
  `_check_then_create` (readiness re-check before creating a Windows draft), chip
  "Ready · Windows containers".
- `node_shell.py` rewritten: `shell_command(container, os, shell)`, `shell_label`,
  `container_state` pre-check (stopped/missing → in-app error), PowerShell/cmd argv without
  spaces or quotes. `running_view.py`: node os/shell from the preview, **Open PowerShell**
  button + tooltips/accessible names, wider State/button columns.
- `prestart_gate.py`: Container engine panel (`GET /docker/engine` vs `container_os`,
  `engine_verdict`, Retry) gating Start. `import_lab.py`: engine stage → hand over to the gate
  on mismatch/unreachable. `api_client.py`: `get_docker_engine`, `TopologyNodeInfo.os/shell`,
  `PreviewResult/LabSummary/ImportLabResult.container_os`. `labels.py`: `lab_icon_name`,
  "Windows" in `origin_meta`.
- Side fix: dashboard cards with an error line were clipped in a multi-row grid (Tigre/06 #25).
- `examples/windows-quickstart.json` (+ bundled sample), `build-windows.ps1` / `Practicum.spec`
  `--add-data` for `practicum_desktop/assets` and `samples`.

**Verified**
- Unit suites: core 204, desktop 350; `-s` grep shows no swallowed tracebacks; the desktop suite
  exits 0 in repeated full runs. ruff clean on everything touched (pre-existing `main.py` F821 /
  `tools/create_app_icon.py` I001 left alone); pure-reformat hunks stripped from old test files
  to keep diffs focused.
- Offscreen screenshots of welcome, dashboard (+ connection panel), Create (Linux mode with the
  Windows blocker panel; Windows mode), Windows + Ubuntu quick start forms, running view
  (Windows node, ok/error banners), gate (Windows lab on Linux engine → Retry → ready), designer.
  Caught: ink icons rendering as solid discs (fixed by the mask encoding), trailing icon gap,
  clipped "Open PowerShell" column, the pre-existing clipped error card.
- Live API + a stateful fake `docker` (Linux/Windows/down modes, `nat` vs `bridge` enforcement,
  Server Core pull, `exec cmd /c type`): create Windows quick start → start in Linux mode refused
  with the switch text (`last_error`) → switch → reset → `wait=false` start → running with the
  install note → stop → restart → export/import keeps os/shell → delete; an Ubuntu lab in Windows
  mode is refused symmetrically.
- **Nothing has run on Windows** (neither Session 5 nor 6); checklist in Tigre/05.

**Coverage pass (user question "is there adequate coverage?")**: audited every Phase 8 AC
against a test and closed the gaps — `tests/test_windows_quickstart_contract.py` (the
desktop-built Windows lab validated by the core model for each host build; Ubuntu builders
unchanged; every example validates; the shipped example carries the current init script),
`test_api.py` (Windows lab through preview/engine/ports → async start with progress → stop /
restart / reset / export / delete; engine switched back after creation → mismatch visible +
structured start failure), gate start flow for a Windows lab with Server Core pull progress,
Lab nodes table rendering of installing / failed / ready markers, shell-launch failure text
with the command, designer edit keeping `os`/`shell`, dashboard card actions for a Windows lab.
AC → test map in the story files' Implementation Status.

**User review of the icons**: two missed spots fixed — the painted topology cards (■/◆) and
the embedded view's toolbar (↗). Cards and designer machine rows now use the icons by role
(host → desktop, gateway → forward; custom images by link count), "open in your system
browser" uses forward; reload keeps its glyph (no artwork) with an accessible name. Tests:
`test_widgets`, `test_designer`, `test_embedded_view`.

**Second icon review (user)**: Restart / Stop lab / reload and the designer's preset picker.
No refresh or stop artwork exists, so the slicing tool now *derives* `refresh` (↻) and `stop`
in the discs' language (measured: 248 px disc, 24 px strokes) — `ICONS[...].derived`; the
preset combo shows each preset's icon. Tests in `test_icons`, `test_running_view`,
`test_embedded_view`, `test_designer`.

**Designer manual (user: "there isn't a section in build your own custom lab to add the lab
manual")**: new `manual_editor.py` (`ManualStepsEditor` = the quick start's step editor moved
out and shared, + `ManualPreview` rendering steps like the flyout); the designer gets a
collapsible **Lab instructions** panel in a vertical splitter (topology row min 330 px,
panel 190 px default), the status pill counts steps, `load_lab` loads the manual (authored
tasks/ids preserved via `QuickStartStep.section_id/tasks`; only the generated "Done: <title>"
task is regenerated; `steps_to_manual` keeps ids unique), `PASS_THROUGH_FIELDS` is just
`schema_version` now. Tests: `test_manual_editor.py` (6), `test_designer.py` (+3), quick start
tests unchanged. Screenshot-reviewed at 1200×760 (tight but usable; drag the splitter or
collapse the panel on small windows). Closes Tigre/11 S-9.

**Several desktops in one lab (user: "you can only see one of the interfaces")**: the picker
above the lab view now lists machines by name ("desktop-1 · localhost:3000", "desktop-2 ·
localhost:3002"; https siblings marked) from per-node ports the API client now parses out of
the preview's topology (`TopologyNodeInfo.port_mappings`, `PortMappingInfo.node_id`); waiting
/ not-running messages name the machine; the designer assigns a second desktop/web server the
next free host ports (`node_catalog.free_host_ports`) instead of leaving a clash for the gate.
Tigre/06 #27. Tests in `test_embedded_view`, `test_running_view`, `test_api_client`,
`test_designer`.

**Port of your own (user: "the only option is to assume that port")**: the gate's port
conflicts became cards with **Use <recommended>** plus a port field + **Apply**; the API's
`apply-recommendation` takes `new_host_port`, checked like a recommendation
(`ports.port_unavailable_reason`, `PortUnavailableError` → 409 with the reason, shown in the
banner with the conflict kept). The old 4-column table could not fit the controls in the side
column. Tests in core `test_api`/`test_ports`, desktop `test_prestart_gate`/`test_api_client`.

**Stale machines after a port fix (user: "when a port is assumed all the previous session
data persists … the image needs to be washed clean")**: root cause was worse than stale data -
the fix was ignored: `docker start` reused the stopped containers with their *old* mapping.
`_store_rewritten_definition` now resets a lab that has run before storing a port/subnet
rewrite (`machines_reset` in `PortCheckResult`/`NetworkCheckResult`; the gate appends "machines
were removed and will start fresh"), D-48, Tigre/06 #29. Tests: core `test_api`,
`test_network_conflicts_api` (reset / never-started / cleanup failure), desktop
`test_prestart_gate`, `test_api_client`.

**Export lab results (user: "after a student has completed all of the lab instructions")**:
new `lab_results.py` (pure: `build_results` → `practicum-lab-results` 1.0 JSON with student,
export time, lab facts, summary, every step/task with `completed` + `completed_at`;
`results_to_markdown`; `write_results` by extension; `results_file_name`), the flyout records
`completed_at` per tick and gains **Export results** + an all-complete banner, the running view
emits `export_results_requested(lab_id, results)`, `MainWindow` asks the student's name
(`dialogs.ResultsExportDialog`, remembered) → save picker (`ask_save_path` now takes filter +
title) → file → note in the running view. Tests: `test_lab_results` (5), `test_manual`,
`test_running_view`, `test_main_window`, `test_dialogs`.

**Screenshots (user: instructors request, students capture from the embedded window or
upload)**: spec `ManualSection.requires_screenshot`; editor checkbox per step + preview hint;
`screenshots.ScreenshotStore` (PNG under AppData, keys beside the ticks); flyout
`ScreenshotRow` (Capture lab view → `EmbeddedLabView.capture()` web page only, Upload image… →
`main_window.ask_image_path`, Remove, thumbnail); progress counts requested screenshots and the
footer says what is missing; results 1.1 (per-step screenshot, counts, `all_complete` needs
them; JSON embeds base64+sha256, MD copies to a folder, new ZIP bundle). Tests:
`test_screenshots` (3), `test_manual` (+3), `test_manual_editor`, `test_embedded_view`,
`test_running_view`, `test_main_window`, `test_lab_results` (+2), core `test_models`.

**Scope change (user)**: Windows containers need Windows Pro/Enterprise/Education, so the
Windows-container features are to be paywalled later rather than offered to free-plan students.
Stories only, nothing removed: new roadmap epic `src/future-roadmap/premium-lab-platforms/`
(README + 7 stories: entitlements/feature gating, Windows labs behind the Pro plan, Windows
edition/virtualisation eligibility check, hosted Windows labs, macOS desktop application
(free prerequisite), macOS labs behind the Pro plan, instructor authoring stays free); roadmap
README paywall lists and the open-core boundary got the platform carve-out; the four Phase 8
story files carry a scope note; D-50, Q-10.

**Docs**: 5 story files (implementation status), `user-story-status.json` (54/54 done, phase 8
done, checkpoint, next = Windows verification of Sessions 5 + 6), `user-stories.md`, README (API,
install note, quick start paragraph, status), Postman, HANDOFF, Tigre 02/03/05/06/09 (D-42…D-46,
Q-9)/10.

**Next**: Windows smoke run (Tigre/05, both sessions' lists); then S-1 persistence.

---

## 2026-10-24 — Session 5: Phase 7 completed — lifecycle controls, dashboard, embedded view, designer re-skin, pull progress, full mockup UI

**Goal (user):** "complete the UI outlined in the mockup and all of the remaining functionality in
the outlined user stories; create any other stories needed; document everything. Start with
`windows-desktop-lab-lifecycle-controls`."

**Order actually followed** (Tigre/05's recommendation: backend enablers first, restructure the
window once): core enablers → pull progress → `ApiClient` → theme + widgets → running view →
screen-stack `MainWindow` (welcome / dashboard / create / quick start / designer / running) →
gate re-skin → tests → two real-app e2e runs → docs.

**Done (core, `src/practicum`)** — 159 tests (was 132)
- `runtime.py`: `start(lab, on_progress)` — `docker image inspect` → streamed `docker pull`
  (`Popen`, per-layer parsing → percent + "n of m layers") only when missing → `docker start` for
  containers left by Stop (**Tigre/06 #2 fixed**) else `docker run` + connects; per-node steps
  reported through a callback; failures attributed to the node; `_is_missing_error` tolerates
  Docker's `network X not found` (**#16**, latent since Phase 3, found by the e2e run).
- `service.py`: `create(origin, source_file)`, `delete` (reset first, 409 on failure — D-25),
  `restart`, action lock (`LabBusyError` → 409 while starting/stopping), start-time port
  re-check (structured `host port conflict` failure), per-lab progress store, `start(wait=False)`
  on a background thread (`pending=True`), `last_error` / `last_started_at` bookkeeping,
  `_with_definition` keeps bookkeeping across port/subnet rewrites, `from __future__ import
  annotations` (the `list` method shadowed the builtin in an annotation).
- `models.py`: `Lab.origin/source_file/created_at/last_started_at/last_error`,
  `LAB_RUNTIME_FIELDS` (stripped from export), `NodeStartProgress`, `RuntimeStatusResult.progress`,
  `RuntimeActionResult.pending`. `main.py`: `DELETE /labs/{id}`, `POST …/restart`,
  `POST /labs?origin=`, `POST /labs/import?source_file=`, `POST …/start?wait=`, 409 mappings.
  `ports.py`: UDP probed with UDP (**#4**), `describe_conflict`.
- Tests: `conftest.py` now makes every port free by default (`real_port_probe` fixture for the
  two real-socket tests) because start re-checks ports and the sandbox cannot bind 22.

**Done (desktop, `desktop/src/practicum_desktop`)** — 270 tests (was 134), 11 new modules
- `theme.py` (mockup tokens → one QSS keyed on role properties; `badge_for_status`, D-26),
  `widgets.py` (Panel, Badge, Chip, RemovableChip, StatTile, StatusPill, BackLink, FlowLayout,
  AutoSizeStack, `TopologyView`/`TopologyCanvas` schematic, `bind`/`payload_of`,
  `style_frame`/`edge_frame`, `discard`), `labels.py`, `dashboard.py`, `create_lab.py`,
  `quickstart.py` (rewritten: templates, packages → command, steps → manual, free /24 — **#1**
  fixed), `designer.py` (rewritten as `DesignerView` screen), `running_view.py`,
  `embedded_view.py` (QWebEngineView, probe, waiting, port picker, fallback), `manual.py`
  (rewritten as the instructions flyout panel; `markdown_to_html` wraps code blocks),
  `progress_panel.py`, `prestart_gate.py` (re-skin + `wait=false` polling), `import_lab.py`
  (`source_file`, real start progress), `api_client.py` (`stop/restart/delete`, `start(wait)`,
  progress/last_error/origin parsing, `_lifecycle_call` with 409 → `busy`), `startup.py`
  (health retries — **#11**), `app_status.py` (timeout wording), `main.py`
  (`AA_ShareOpenGLContexts`, `apply_theme`), `main_window.py` (rewritten: title bar + status chip
  + connection panel + `QStackedWidget`; owns all API calls; `_pending_selection` lands on the
  running view; `_notify` to both home screens).
- **Tigre/06 #15** — the expensive find: after all tests passed, the process aborted on exit
  (`malloc_consolidate(): unaligned fastbin chunk detected`). Bisected to lambdas capturing
  `self` connected to child-widget signals (repro: a `ManualFlyout` with two sections). Replaced
  every such connection app-wide with `widgets.bind()` / bound methods; per-file and full-suite
  runs now exit 0 repeatedly. Rule recorded in Tigre/03, 07, 09 (D-34).
- Hygiene: all desktop `.py` files CRLF (new ones converted); new modules `ruff format`ed; ruff
  check clean for `src` + `tests` in both packages; no line > 100 in new/modified code
  (pre-existing long lines in `api_client.py`/`runtime.py` left alone).

**Verified**
- Unit suites: core 159, desktop 270, `-s` grep shows no swallowed tracebacks; the desktop
  suite exits 0 in 5 consecutive runs and per file.
- Offscreen screenshots of every screen compared with the mockup (dashboard, welcome, create,
  quick start, designer, running, gate); several layout fixes came from that (QFrame selector
  leaking to labels, ghost rows without `discard()`, mnemonic `&` in "Save & Start", clipped
  table buttons, elided topology pills, non-wrapping code blocks).
- Live API + stateful fake `docker` (extended with `image inspect`, `pull`, `start`): import →
  async start with 18 %→100 % pull progress → stop → start (docker start path) → restart → reset
  (idempotent) → start → delete; busy 409s; missing-image failure attributed to the node; port
  re-check blocks start (sandbox cannot bind 22 — expected).
- Two scripted runs of the **real `MainWindow`** (real QThreads, real dialogs) against that API:
  (1) welcome → import sample → running view → Stop → Start via gate → Reset (confirm) → back →
  dashboard → Delete → welcome; (2) Quick start form (packages + step) → Create → gate with live
  pull progress → running view with the step in the flyout; designer (3 machines, 2 networks,
  4 connections) → Validate → Save & Start → gate → running view with 3 nodes. All screenshots
  reviewed.
- **Nothing from this session has run on Windows.** Checklist in Tigre/05.

**Docs**: 7 new story files (`runtime-lab-restart`, `runtime-delete-lab`,
`lab-origin-and-timestamps`, `windows-desktop-visual-theme`, `windows-desktop-create-lab-screen`,
`designer-quick-start-lab`, `windows-desktop-status-polling`) + addenda on 11 existing stories;
epic READMEs and `user-stories.md` (items 30–38); `user-story-status.json` (47 stories, all done,
phase 7 done, checkpoint, next = Windows verification); README (API list, desktop description);
Postman (+5 requests, query params, status assertions); HANDOFF refreshed; Tigre 00, 02, 03
(rewritten), 05 (rewritten), 06, 07, 09 (D-25…D-34, Q-2/4/6 closed, Q-7/Q-8 opened), 11.

**Addendum (same day, user request):** "I would like a UI ubuntu desktop as part of the quick
start … a simple image for simple or non-IT related labs." Added the **Ubuntu Desktop** quick
start template (`quickstart.py`: `QuickStartTemplate.kind` desktop|terminal, webtop image on
3000/3001, `command: null`, `TITLE`, packages via `DOCKER_MODS=linuxserver/mods:universal-package-install`
+ `INSTALL_PACKAGES=a|b|c`; made it the default — D-35), the Create screen now shows three
template radios in a `QButtonGroup` (they sit in separate frames, so Qt would not have made them
exclusive) with per-template icon/description/hint, the Quick start screen adapts its name,
base chip and package caption per template, `TopologyView(compact=True)` uses narrower
connectors so the Create card's illustration fits. Tests 273 (+3). E2E with the fake docker +
a local HTTP server on 3000: desktop quick start with `libreoffice` → gate → running view shows
`http://localhost:3000` in the embedded view and the step in the flyout. Docs: story addendum,
status JSON (new AC), Tigre 05/06/09/10, README.

**Second feedback round (same day, after the user's first Windows run):**
1. *Emoji indicators* → removed app-wide (words + colour, geometric glyphs; D-38).
2. *Connect-form dropdown black/unreadable* → Windows dark mode + `selection-background-color`
   leaking into the popup; fixed with Fusion style + fixed light palette + explicit popup rules
   (Tigre/06 #20).
3. *Pre-selectable machine images, daisy-chaining* → `node_catalog.py` presets incl. a Router that
   really forwards (`resources.sysctls` → `docker run --sysctl net.ipv4.ip_forward=1`, new spec
   field), id + address suggestions, per-network address reference (`designer-node-catalog`).
4. *Edit a lab, even a quick start* → `PUT /labs/{id}` (`LabService.replace`, D-37), designer
   `load_lab` edit mode, dashboard **Edit** (`designer-edit-existing-lab`).
5. *Export* → dashboard **Export** → system save picker (D-39), `ApiClient.export_lab`.
6. *Instructions panel clipped / sideways scroll / not resizable* → Ignored size policies,
   `TaskRow`, QSplitter (Tigre/06 #21).
7. *100 % packet loss between hosts* → diagnosed as stale manual addresses after the gate moved
   the subnet; `move_subnet` now rewrites the manual and the Lab nodes table shows real
   addresses (Tigre/06 #19). Could not reproduce real Docker networking in the sandbox.
8. *Reference for host IPs in the designer* → covered by 3.
Tests: core 167, desktop 285; e2e re-run (import → running view with addresses; dropdown
screenshot readable). Docs: 2 new stories + 7 addenda, status JSON, README, HANDOFF, Postman
(PUT), Tigre 02/03/05/06/09/10.

**Third feedback round:** the desktop quick start now shows a display on Windows (first real
confirmation that QtWebEngine + webtop work there), but with nginx's "400 … plain HTTP request
was sent to HTTPS port" — the view had loaded `http://localhost:3001`. Fixed the probe (400 +
that sentence ⇒ https) and the default-port choice (plain-web before TLS-only ports regardless
of mapping order) — Tigre/06 #22.

**Fourth feedback round (Windows log attached):** (1) "window randomly shutting down" = Qt abort
`QThread: Destroyed while thread '' is still running` — the gate's single worker attributes
(second "Use <port>" click; 1 s poll while `docker inspect` was slow) garbage-collected a running
thread. Root fix: `ManagedThread` self-registry (D-41), poll ticks skip while busy, closeEvent
waits; Tigre/06 #6 closed. (2) "containers need to be removed when a lab is deleted" → `delete`
always resets + startup leftover sweep + `POST /docker/sweep-leftovers` (D-40, Tigre/06 #23).
Core 173 / desktop 289 tests; fake-docker e2e: seeded leftover removed at API start, delete
leaves nothing.

**Fifth feedback round:** (1) welcome/dashboard notes → dismissible `NoteBanner`, readable
width, and a delete message that says what happened (containers removed, files untouched, no
labs left → create/import) — Tigre/06 #24. (2) "git not recognised" → the install simply had
not finished (and failures were silent): status marker written by the quick-start script,
`RuntimeResourceStatus.note` via `docker exec cat`, shown in the Lab nodes table
("running · installing…"), printed by login shells (`bash -l`) — Tigre/06 #18.
(3) Curated "Popular software" picker per template kind (`PACKAGE_CATALOG`, `ToggleChip`,
`FlowHost` so chip rows never clip) with an "Other packages" fallback. Core 173 / desktop 291.

**Next**: Windows smoke run per Tigre/05 checklist; then S-1 persistence.

---

## 2026-10-23 — Session 4: Story `windows-desktop-import-lab-file` implemented

**Goal:** Build the desktop "Open Lab File" import-and-launch flow (user's pick; taken ahead of the
dashboard in the Tigre/05 order).

**Done (product code)**
- `desktop/.../lab_file.py` (new, pure Python): `read_lab_file()` with specific errors (missing,
  directory, >5 MB, non-UTF-8, JSON syntax + line/col, non-object, `.zip` unsupported),
  `format_issue()` (`nodes[0].image: Field required`), `sample_lab_files()`, `LabFileEntry`.
- `desktop/.../samples/*.json` (new): byte-identical copies of `examples/` shipped in the wheel;
  a test fails if they drift.
- `desktop/.../import_lab.py` (new): `ImportLabDialog` — page 0 = recent (QSettings
  `recent_lab_files`) + samples list with a `LabFileRowDelegate` (icon / bold name / muted hint)
  and **Browse computer…** (`QFileDialog.getOpenFileName`, the one native dialog); page 1 =
  staged progress (read → import → ports → start) with inline error list, "Choose another file",
  and close blocked while a stage is in flight. `ImportOutcome{lab_id, lab_name, source_path,
  started, gate_required}`. `RecentLabFiles` helper.
- `api_client.py`: `ImportLabResult` + `ApiClient.import_lab()`; `LIFECYCLE_TIMEOUT_SECONDS = 900`
  used by `start_lab` (+ specific timeout wording) — **closes Tigre/06 #3**.
- `main_window.py`: **Import Lab File…** button beside New Lab…; `_on_import_clicked` opens the
  dialog, opens `PreStartGateDialog` when `gate_required`, then refreshes and selects the lab via
  `_pending_selection` / `_apply_pending_selection` (shows the manual when started). Stores
  `_last_status` so the dialog can show a "API not available" banner.
- Core `models.py`: `SUPPORTED_SCHEMA_MAJOR_VERSIONS = (1,)`; `schema_version` field validator
  rejects e.g. `2.0` with "not supported by this version of Practicum (supported: 1.x)".
- Robustness found by the e2e run: `runtime.py` and `docker_status.py` caught only
  `FileNotFoundError` from `subprocess.run(["docker", …])`; a non-executable docker binary
  (PermissionError) produced an HTTP 500 from `POST /start` and killed the desktop's startup
  thread (window stuck on "Checking Practicum status…", Retry disabled). Both now catch `OSError`
  → structured failure / Degraded. Logged as Tigre/06 #12 (fixed).

**Tests**: core **104** (+4), desktop **105** (+56: `test_lab_file` 19, `test_import_lab` 21,
`test_main_window` 7 — first MainWindow tests, `test_api_client` +8, `test_docker_status` +1;
shared `desktop/tests/qt_helpers.py` with `ImmediateWorker`/`StalledWorker`). All pass.

**Verified**
- **PySide6 6.12 installs in the sandbox now** (`pip install PySide6`) and the full Qt suite runs
  with `QT_QPA_PLATFORM=offscreen` — no stub needed any more (Tigre/07 updated).
- Rendered the dialog offscreen (`widget.grab().save()`) and reviewed screenshots: chooser,
  blocked banner, schema-error list, start-failure, in-flight "Starting containers…", main window.
- End-to-end against a live `uvicorn` API in the sandbox (no Docker): valid sample import; schema
  `2.0` rejected inline; multi-error file; forced host-port conflict (socket on 3000) → `gate_required`;
  conflict-free quick-start sample → start → structured "Docker CLI could not be run" shown with
  "select it and use Start" guidance; recent list updated; no 500s.
- **Not verified on Windows** — needs one smoke run (`start-practicum.bat`): native picker, auto-start
  landing (lab selected, manual flyout opens), recent list persists across launches.

**Decisions recorded** (Tigre/09): D-18 `.zip` not accepted until a bundle format exists (C8);
D-19 duplicate import = new lab for now (Q-1 still open); D-20 schema major-version check is
server-side; D-21 import flow falls back to the gate when the port check itself fails.

**Docs**: `user-story-status.json` (story done, 5th AC added per Tigre/11 §2.1, in-app-dialogs
file-picker AC ticked, checkpoint/last_updated), story markdown "Implementation Status" addendum,
Tigre 00/03/05/06/07/09/11 updated. README/Postman untouched (no new endpoint).

**Manual probe kit** (added at the user's request): `examples/import-probes/` — 7 files, one per
flow path (auto-start, API-port conflict → gate, schema 2.0, multi-error, malformed, JSON list,
`.zip`) + README with expected outcomes; each verified against the live API in the sandbox.
`test_bundled_samples_match_repo_examples` only globs `examples/*.json`, so the subfolder is
not bundled into the desktop package.

**Windows smoke run (user report, same day):** importing the bundled `ubuntu-quickstart.json` got
through read → import → ports → start and then failed at start with Docker's "Pool overlaps with
other one on this address space" on `10.50.0.0/24` — i.e. the import flow itself worked end-to-end
on Windows (native picker, progress, structured start failure shown with guidance, lab kept in the
list). Diagnosed as Tigre/06 #13: the sample shares its subnet with the Quick Start button lab, and
the owner is a still-listed lab (Stop keeps networks) or an orphan from an earlier API session.
Fixed the misleading "Stop or reset" wording in `runtime.py` (now "Reset … Stop is not enough" +
`docker network ls --filter label=practicum.lab_id` recipe; test updated). Gave the user the
inspect/reset/`docker network rm` steps. Promotes S-16 (subnet overlap in the gate) and S-1.

**Second user report, same error after the wording fix** → built the real fix (Tigre/11 S-16,
now story `runtime-subnet-conflicts`, **done**):
- Core: `networks.py` (`find_subnet_conflicts`, `recommend_subnet` from `10.90.0.0/16`,
  `move_subnet` keeping host offsets); `DockerRuntime.list_networks()` (`docker network ls
  --format {{.Name}}` + `docker network inspect <all>` → subnets / `practicum.lab_id` label /
  attached containers; `_query()` helper) and `remove_network()`; `LabService.check_networks` /
  `apply_subnet_recommendation` / `remove_leftover_network`; routes `GET /labs/{id}/networks`,
  `POST …/networks/apply-recommendation`, `POST …/networks/remove-leftover` (409s);
  models `DockerNetworkInfo`, `SubnetConflict`, `NetworkCheckResult(error)`; `LabDefinition`
  rejects overlapping subnets within a lab (one old test retargeted: duplicate IPs on the *same*
  network). README API list + Postman (4 requests) updated.
- Desktop: `ApiClient.check_networks/apply_subnet_recommendation/remove_leftover_network/
  reset_lab`; `PreStartGateDialog` "Network Conflicts" group (owner text per reason; fixes
  **Remove leftover** / **Reset '<lab>'** with `confirm(destructive=True)`, **Use <subnet>** →
  re-renders topology + "manual may still mention the original addresses"; Start requires
  both checks answered clean; Issue column stretches; "Loading lab details…" now clears);
  `ImportLabDialog` stage "Checking host ports and networks…" → gate on subnet conflicts.
- Tests: core **132** (+27), desktop **122** (+17).
- **Verified with a stateful fake `docker` CLI** (`/tmp/fakedocker/docker`, Python script with
  JSON state; rejects overlapping pools like Docker): seeded an old-session Quick Start network
  with its container attached → `POST /start` failed with the user's exact message →
  `GET /networks` named the leftover → gate showed *Remove leftover* / *Use 10.90.0.0/24* →
  each path (and *Reset 'Ubuntu Quick Start'* for a listed owner) cleared the conflict and Start
  succeeded; topology re-rendered as `10.90.0.10/24` after a subnet move. Screenshots reviewed.
  **Not yet verified with real Docker Desktop on Windows.**
- Note for the fake: `docker network rm` refuses networks with active endpoints, like Docker —
  `remove_network` removes containers first for that reason.

**Third user report: the gate fix "worked great"; then `ssh localhost@10.93.1.0` timed out.**
Three causes: `.0` is the network address; Docker Desktop keeps bridge subnets inside its VM (host
can only reach *published* ports); the probe nodes are `alpine` + `sleep infinity` with no sshd —
the only way in is `docker exec`, which the app didn't offer (Tigre/11 #2 / S-11, P0). Built the
MVP → story **`windows-desktop-open-node-shell`** (done):
- `node_shell.py`: `shell_command()` = `docker exec -it <c> sh -c "command -v bash … && exec bash
  || exec sh"`; `open_node_shell()` → Windows `cmd.exe /k …` with `CREATE_NEW_CONSOLE` (window
  stays open on error), Linux first available terminal, else returns the command to copy.
- `ApiClient.get_status()` → `StatusResult{lab_status, resources, containers}` (first desktop use
  of `GET /status`).
- `main_window.py`: **Lab Nodes** table (Node / Container / State / **Open shell**) via
  `_refresh_nodes()` on selection and after Start; button only for `running`; status line says
  node addresses are reachable only inside the lab. Default size 560×760.
- Lesson: **Qt swallows exceptions raised in slots** — `test_main_window` passed while the fake
  client lacked `get_status`; run `pytest -s` and grep for `Traceback` when touching slots.
  Fake now has `get_status`; +4 MainWindow tests, `test_node_shell.py` (5), api_client +3 → **134**.
- Probe kit: lab 1's manual now tells the student to use Open shell; README gets a "don't ssh/ping
  node addresses from Windows" note.

**User confirmation received before closing**: the subnet-conflict gate fix "worked great" on
Windows with real Docker Desktop (leftover removed, lab started) — so stories 1 and 2 of this
session are Windows-verified; only Open shell is not.

**Session close state**: all work uncommitted on `baseline`; Tigre 00 "Resume here" rewritten with
a Windows verification checklist; tests core 132 / desktop 134 green; no `.ruff_cache` left.

**Next**: user verifies on Windows (**Open shell** on probe 1 — watch the
`cmd /k` + `CREATE_NEW_CONSOLE` behaviour with Docker Desktop's `docker.exe`); then
`windows-desktop-labs-dashboard` (its
"Import Existing Lab" action = `ImportLabDialog`; its Start = `PreStartGateDialog`), preceded by
the backend enablers (`DELETE /labs/{id}`, start-after-stop Tigre/06 #2).

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
