# Check macOS and Docker Readiness

## User Story

As a Practicum user on macOS,
I want the app to check its local API and Docker connection and explain any problem,
so that I know what to fix before starting a lab.

## Functional Requirements

- Check the local API and Docker CLI/daemon without showing an unnecessary terminal window.
- Present actionable guidance for a missing Docker CLI, stopped Docker Desktop, unreachable API, or
  API port conflict.
- Keep the check read-only; Practicum does not start Docker Desktop or change Docker settings.
- Describe Linux-container readiness accurately and do not offer Windows-container workflows on
  macOS.

## Acceptance Criteria

- The readiness panel distinguishes API availability from Docker CLI/daemon availability.
- Each unavailable dependency has a macOS-appropriate next step and a Retry action.
- Docker checks do not open a terminal window or modify Docker Desktop state.
- Windows Quick Start remains unavailable on macOS, while Linux Quick Start is available when the
  Docker daemon is ready.

## Dependencies

- [Run Practicum on macOS](macos-desktop-run-app.md).

## Implementation Status

Not started.
