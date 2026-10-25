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

Not started.
