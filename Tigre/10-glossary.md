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
| **Manual flyout** | The dockable `ManualFlyout` panel in the desktop app; mockups call it "Instructions flyout". |
| **Designer Mode** | Instructor workflow — `DesignerDialog` today; mockups `screen-custom`. |
| **Import Mode** | Student workflow — import, preview, start/stop/reset, manual. |
| **Quick Start** | One-click single-Ubuntu lab (`quickstart.py`). Mockups extend it to OS templates + packages + step editor. |
| **Pre-start gate / readiness gate** | `PreStartGateDialog` — review + port-conflict resolution before Start. |
| **Port conflict** | Host port problem: `duplicate_in_spec`, `reserved_by_practicum_api`, `in_use_on_host`; each has a `recommended_port`. |
| **Recommendation** | Server-suggested free host port; applying it rewrites the node's mapping. |
| **Exposed port** | `exposed_ports: [p]` → `-p p:p` tcp. **Port mapping** = `{host, container, protocol}`. |
| **Readiness** | Desktop app state: `ready` (API+Docker ok), `degraded` (API ok, Docker down), `blocked` (API down). |
| **Runtime** | `LabRuntime` protocol / `DockerRuntime` adapter; also "the local runtime" persona in stories. |
| **RuntimeFailure / RuntimeIssue** | Exception in runtime / its serialized form in API responses. |
| **Status (lab)** | `defined → starting → running → stopping → stopped`, plus `error`; `reset` → `defined`. |
| **Status (resource)** | `RuntimeResourceStatus{kind: network\|container, exists, status}` from `docker inspect`. |
| **Draft** | Mockup/dashboard term for a saved-but-never-started/validated lab (maps to status `defined`). |
| **Story / Epic / Phase** | Backlog units in `src/user-stories/`; tracked in `user-story-status.json`. |
| **Future roadmap** | `src/future-roadmap/` — paid-tier ideas, not built. |
| **Mockups** | `design/practicum-mockups.html` clickable HTML prototype used to derive Phase 7. |
| **Webtop** | `lscr.io/linuxserver/webtop` browser-accessible Linux desktop image used in `examples/ubuntu-webtop.json` (noVNC on 3000/3001). |

## Naming conventions

- IDs (node, network, section, task): `^[a-z][a-z0-9-]*$` (kebab-case).
- Docker: `practicum-{lab.id[:8]}-{node_id|network_id}`; labels `practicum.lab_id`,
  `practicum.node_id`, `practicum.network_id`.
- QSettings: org `Practicum`, app `Practicum Desktop`; keys `api_base_url`,
  `manual_progress/{lab_id}/{section_id}/{task_id}`.
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
