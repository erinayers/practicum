# Windows Container Readiness for Quick Start

## User Story

As a Practicum user on Windows,
I want the app to tell me whether this PC and Docker Desktop can run Windows containers,
so that I can prepare the host before creating a Windows Quick Start lab.

## Why This Matters

Practicum currently targets Docker Desktop's default Linux-container engine. Windows containers
have additional host, Docker Desktop installation-mode, and engine requirements. Switching the
Docker Desktop engine is a machine-wide change and may stop containers, so Quick Start must not
silently change it.

## User Flow

1. The user chooses the Windows Quick Start template.
2. Practicum checks whether Docker is reachable and which operating system the active Docker engine
   serves.
3. If Windows containers are unavailable, the app explains the detected blocker and links to the
   current Docker Desktop requirements and switching instructions. The user can retry after
   addressing it.
4. If the Docker engine is ready for Windows containers, the Windows template can be configured
   and started.

## Functional Requirements

- Detect Docker availability and the active daemon's operating system using a read-only check.
- Keep Windows Quick Start unavailable while the Docker daemon serves Linux containers or cannot
  be reached; explain the next step in plain language.
- Link to Docker's current requirements because eligible Windows editions, Docker Desktop install
  mode, and host/container compatibility can change.
- Provide a Retry action after the user switches the Docker Desktop engine or changes a host
  prerequisite.
- Never switch Docker Desktop's engine automatically. Switching affects every application using
  the local Docker daemon and may require elevated approval.
- Do not require Windows-container readiness to continue using Linux templates.

## Acceptance Criteria

- The check distinguishes an unavailable Docker daemon, a Linux-container daemon, and a
  Windows-container daemon.
- Windows Quick Start is disabled until the Windows-container daemon is ready.
- The disabled state explains that the user must meet the current host and Docker Desktop
  requirements and switch Docker Desktop to Windows containers.
- Retrying updates the state without restarting Practicum.
- A Docker or host compatibility failure is shown before lab creation, with a useful next action.
- Linux Quick Start remains available when Docker is in its normal Linux-container mode.

## Dependencies and References

- Enables `designer-windows-quick-start.md`.
- Docker Desktop's current Windows-container requirements and mode switching are documented in
  the [Windows installation guide](https://docs.docker.com/desktop/setup/install/windows-install/).
- Windows host and container image compatibility is documented in
  [Windows container version compatibility](https://learn.microsoft.com/en-us/virtualization/windowscontainers/deploy-containers/version-compatibility).

## Implementation Status

**Done 2026-10-25** (Session 6).

- **Detection (read-only).** `desktop/docker_status.py` now runs `docker info --format '{{json .}}'`
  and reads `OSType` (+ `ServerVersion`, `OperatingSystem`, `KernelVersion` → `host_build`,
  `Isolation`). `windows_container_readiness(docker)` gives one of three states -
  `docker_unavailable`, `linux_engine`, `ready` - each with a plain-words `detail` and
  `next_action`. The API exposes the same probe as `GET /docker/engine` (`DockerEngineInfo`,
  `DockerRuntime.engine_info()`), used by the pre-start gate and the import flow. Nothing ever
  calls Docker Desktop's mode switch; the next action tells the user how to do it themselves.
- **Create screen.** `CreateLabScreen.set_docker_status()` enables the templates the current
  engine can run (`template_availability`): the Ubuntu templates in Linux mode, the Windows
  template in Windows mode (then the Ubuntu ones are disabled with the reverse hint). The
  Windows row stays disabled (captioned "unavailable", tooltip = the reason) until readiness
  passes; clicking it opens the `WindowsReadinessPanel` with the blocker, the next action, links
  to Docker's Windows install/switching guide and Microsoft's compatibility matrix, and **Retry**.
  Retry (and every visit to the Create screen) re-probes Docker in a worker
  (`MainWindow.refresh_engine`) and updates the connection panel, title-bar chip
  ("Ready · Windows containers") and templates in place - no restart.
- **Elsewhere.** `app_status.py` says, in Windows mode, that Linux labs cannot run until the mode
  is switched back; the gate's new **Container engine** panel blocks Start (with Retry) when the
  lab's `container_os` and the engine disagree; Create Lab on a Windows draft re-checks readiness
  first; `POST /start` re-checks server-side and fails with the switch instructions.
- Tests: `test_docker_status.py` (three states, read-only probe), `test_app_status.py`,
  `test_create_lab.py` (availability per mode, panel, Retry), `test_main_window.py` (refresh
  wiring), `test_prestart_gate.py`, core `test_runtime.py` / `test_api.py` (`/docker/engine`).
- **Not yet verified on Windows** with Docker Desktop actually switched to Windows containers
  (the sandbox has no Docker); the `docker info` JSON shapes used in tests come from Docker 27.

## Scope note 2026-10-25

Windows containers require Windows 10/11 Pro, Enterprise or Education (Hyper-V and the
Containers features); Windows Home — the common student laptop — cannot run them. This feature
is therefore planned to move behind the paid tier; the implementation above stays as built and
the gating, eligibility check and hosted alternative are described in the roadmap epic
[Premium Lab Platforms](../../future-roadmap/premium-lab-platforms/README.md).
