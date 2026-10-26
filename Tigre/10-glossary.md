# 10 — Glossary and Naming

| Term | Meaning in this project |
|---|---|
| **Practicum** | The product name; also the core package (`practicum`) and API title. |
| **eduLabs** | The workspace/repo folder name (`eduLabs - Copy`). Not used in code. |
| **Tigre** | This memory folder (user-created, 2026-10-23). |
| **Lab spec / lab definition** | The portable JSON (`LabDefinition`): metadata + nodes + networks + interfaces + manual. |
| **Lab** | A stored spec with `id` (uuid4) and `status`. |
| **Node** | One Docker container in the topology (`image`, `command`, `environment`, `resources`). Mockups call these "machines"/"hosts". |
| **Network** | One Docker bridge network with a fixed IPv4 subnet. |
| **Interface** | Attachment of a node to a network with a static IP (`address` as `ip/prefix`). Mockups call these "connections". |
| **Manual** | Embedded instructional content: sections (markdown) with checkable tasks ("steps" in mockups). |
| **Manual flyout / Instructions flyout** | `ManualFlyout`, the side panel of the running view: numbered steps (one per manual section), checkable tasks, "Mark step complete", local progress. |
| **Designer Mode** | Instructor workflow — `DesignerView` screen (Machines / Network topology / Networks panels); mockup `screen-custom`. |
| **Import Mode** | Student workflow — import, preview, start/stop/reset, manual. |
| **Quick start** | Single-host lab from a template (`QuickStartScreen` + `quickstart.py`): **Ubuntu Desktop** (default; webtop desktop shown in the embedded lab view, packages via `INSTALL_PACKAGES`), **Ubuntu** (terminal; packages → apt-get node command) or **Windows** (Server Core PowerShell sandbox; tools via Chocolatey); name, instruction steps (→ manual sections), free /24 from 10.90.0.0/16. |
| **Engine mode / container OS** | Docker Desktop serves *either* Linux or Windows containers ("Switch to Windows containers…" in the whale menu). `DockerStatus.os_type` / `DockerEngineInfo.os_type` say which; a lab's nodes declare `os` (`LabDefinition.container_os`) and can only start when both agree. Practicum never switches the mode (D-42). |
| **Windows-container readiness** | `docker_status.windows_container_readiness()`: `docker_unavailable`, `linux_engine` or `ready` — gates the Windows template (Create screen panel with Retry + links). |
| **Windows template / Server Core** | `mcr.microsoft.com/windows/servercore:<ltsc tag>` pinned by `WINDOWS_IMAGES` to the newest tag the daemon host's build can run (Hyper-V isolation runs older images on newer hosts, never newer on older). Keep-alive: a PowerShell init passed as `-EncodedCommand`. |
| **Chocolatey** | The Windows package manager (`choco install <id>`) used by the Windows quick start to install command-line tools; ids from `WINDOWS_TOOL_CATALOG` or typed by the instructor, listed in `environment.PRACTICUM_PACKAGES`. |
| **Node os / shell** | Spec fields (`linux`\|`windows`; `bash`\|`sh`\|`powershell`\|`cmd`, default per OS) the runtime (network driver, engine check, status note) and Open shell / Open PowerShell follow; declared, never guessed from the image. |
| **Design icons / ink icons** | The nine icons of `design/icons.png` (`icons.py` meanings: success, error, warning, back, forward, play, terminal, desktop, tools; in topologies: host → desktop, gateway → forward; plus two *derived* icons `refresh` and `stop` drawn by the slicing tool in the same style). The black ones are stored as *ink masks* (alpha = darkness) so they can be tinted; the coloured status icons are used as drawn. |
| **MessageBanner** | `widgets.MessageBanner`: icon + copyable text, styled by the `banner` property (ok / warn / error / info); `NoteBanner` is its dismissible variant. |
| **Pre-start gate / readiness gate** | `PreStartGateDialog` — review (images, topology, manual, resources) + port/subnet-conflict resolution before Start; shows the real start progress. Every Start goes through it. |
| **Port conflict** | Host port problem: `duplicate_in_spec`, `reserved_by_practicum_api`, `in_use_on_host`; each has a `recommended_port`. |
| **Recommendation** | Server-suggested free host port; applying it rewrites the node's mapping. |
| **Exposed port** | `exposed_ports: [p]` → `-p p:p` tcp. **Port mapping** = `{host, container, protocol}`. |
| **Readiness** | Desktop app state: `ready` (API+Docker ok), `degraded` (API ok, Docker down), `blocked` (API down). |
| **Runtime** | `LabRuntime` protocol / `DockerRuntime` adapter; also "the local runtime" persona in stories. |
| **RuntimeFailure / RuntimeIssue** | Exception in runtime / its serialized form in API responses. |
| **Status (lab)** | `defined → starting → running → stopping → stopped`, plus `error`; `reset` → `defined`. |
| **Status (resource)** | `RuntimeResourceStatus{kind: network\|container, exists, status}` from `docker inspect`. |
| **Ready** | Dashboard badge for status `defined` (a stored, validated lab that is not running). The mockup's "Draft" was dropped (D-26) because unvalidated labs cannot be stored. |
| **Running view** | `RunningLabView`, the screen a lab is used from: lifecycle toolbar (Start/Restart/Stop/Reset/Instructions), embedded lab view, Lab nodes + Open shell, instructions flyout, status bar. |
| **Embedded lab view** | `EmbeddedLabView`: QWebEngineView showing what the lab publishes on a host port, with URL bar, a machine picker (one entry per machine and published port, e.g. "desktop-2 · localhost:3002"), waiting state and "open in system browser". |
| **Dashboard / lab card** | `DashboardScreen` / `LabCard` ("Your Labs"): one card per lab with origin meta, badge, activity line and Open / Start / Delete / Reset. |
| **Origin** | How a stored lab came to exist on this machine: `designer`, `imported` (+ `source_file`), `quick_start`. Bookkeeping only, never exported. |
| **Action lock / busy** | A lab that is `starting` or `stopping` refuses other lifecycle calls with 409; the desktop disables its lifecycle buttons meanwhile. |
| **Start progress** | Per-node `NodeStartProgress` (`checking_image`, `pulling_image` + percent, `creating_container`, `connecting_networks`, `ready`, `failed`) in `GET /status`, rendered by `StartProgressPanel`. |
| **Machine preset / catalogue** | `node_catalog.PRESETS`: ready-made node recipes (Ubuntu host, Alpine host, Router with IP forwarding, Web server, Ubuntu Desktop, Custom image) the designer adds machines from. |
| **Lab instructions panel / step editor** | `manual_editor.ManualStepsEditor` (+ `ManualPreview`): the shared manual editor - numbered steps with Markdown details that become manual sections; in the quick start screen and, since 2026-10-25, the Custom Lab designer (collapsible panel under the topology). |
| **Screenshot (evidence)** | An image a student attaches to a step the instructor flagged with `requires_screenshot`: captured from the embedded lab view or uploaded; stored by `screenshots.ScreenshotStore`, counted in the step's progress, exported with the results. |
| **Lab results** | What a student hands in: `lab_results.py`'s `practicum-lab-results` document (JSON, or a Markdown report) - student name, export time, lab facts, summary and every step/task with completion state and time, built from the flyout's local progress. Exported from the instructions flyout's **Export results**. |
| **Edit mode** | `DesignerView.load_lab()`: the designer pre-filled with an existing lab; Save → `PUT /labs/{id}`. |
| **Leftover** | A Practicum-labelled Docker network/container whose lab the API no longer knows (API restarted); the gate can remove it. |
| **Story / Epic / Phase** | Backlog units in `src/user-stories/`; tracked in `user-story-status.json`. |
| **Future roadmap** | `src/future-roadmap/` — paid-tier ideas, not built. |
| **Mockups** | `design/practicum-mockups.html` clickable HTML prototype used to derive Phase 7. |
| **Webtop** | `lscr.io/linuxserver/webtop` browser-accessible Linux desktop image used in `examples/ubuntu-webtop.json` (noVNC on 3000/3001). |

## Naming conventions

- IDs (node, network, section, task): `^[a-z][a-z0-9-]*$` (kebab-case).
- Docker: `practicum-{lab.id[:8]}-{node_id|network_id}`; labels `practicum.lab_id`,
  `practicum.node_id`, `practicum.network_id`.
- QSettings: org `Practicum`, app `Practicum Desktop`; keys `api_base_url`,
  `manual_progress/{lab_id}/{section_id}/{task_id}`, `recent_lab_files`.
- Qt style roles (theme.py): `kind` (buttons), `role` (labels), `panel`, `badge`, `chip`,
  `banner`; object names `titlebar`, `brandBadge`, `brandName`, `screen`, `panelHead`,
  `bottomBar`, `urlBar`, `instructionsFlyout`.
- Env: `PRACTICUM_API_PORT` (default 8000).
- Story ids: `<epic-prefix>-<kebab>` e.g. `windows-desktop-labs-dashboard`, file
  `src/user-stories/<epic-folder>/<story-id>.md`.
- Desktop modules: one widget/dialog per file, `_on_<thing>_clicked` slot naming,
  `_render_<x>` for table fills, `_build_ui` for construction.

## Added in Session 4 (2026-10-23)

- **Leftover** — a Docker network/container carrying a `practicum.lab_id` label whose lab the API
  no longer knows (labs are in-memory; Docker state survives restarts). Detected by
  `GET /labs/{id}/networks` as `overlaps_leftover`; removable from the gate.
- **Subnet conflict** — one of the lab's subnets overlaps an existing Docker network (Docker:
  "Pool overlaps with other one on this address space"). Owner classes: other listed lab /
  leftover / foreign Docker network. Recommendations come from `10.90.0.0/16`.
- **Gate** — `PreStartGateDialog`; now checks ports *and* subnets; the only authority for Start.
- **Probe kit** — `examples/import-probes/`: 7 files, one per import-flow path, with a README of
  expected outcomes. Probe labs use `10.93.x.0/24`.
- **Samples** — `desktop/src/practicum_desktop/samples/*.json`, byte-identical copies of
  `examples/*.json`, shown in the Open Lab File list.
- **Recent files** — QSettings key `recent_lab_files` (newest first, max 8).
- **Open shell** — main-window button per running node: `docker exec -it <container> sh -c
  "…bash or sh"` in a new console window (`node_shell.py`).
- **Lab Nodes table** — main-window table fed by `GET /labs/{id}/status` (container name/state).
- **Lifecycle timeout** — `ApiClient.lifecycle_timeout` (900 s) for start/reset/remove-leftover.
- **ImmediateWorker / StalledWorker** — test doubles for `CallableWorker` in `tests/qt_helpers.py`.
