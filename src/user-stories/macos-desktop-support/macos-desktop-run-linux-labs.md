# Run Linux Labs on macOS

## User Story

As a student or instructor using Practicum on a Mac,
I want to import, design, and run supported Linux-container labs,
so that I can complete the same core lab workflows as users on Windows.

## Functional Requirements

- Support the existing Docker-based Linux lab lifecycle on Docker Desktop for Mac.
- Verify host port checks, Docker networks/subnets, image pull progress, container lifecycle, and
  embedded web interfaces on macOS.
- Keep host paths and platform assumptions out of lab specs so compatible specs remain portable.
- Clearly explain that Windows-container labs cannot run on macOS.

## Acceptance Criteria

- On a supported Mac with Docker Desktop ready, a user can import a sample Linux lab, pass the
  pre-start checks, start it, view its embedded web interface when present, open a node shell, and
  stop/reset/delete it.
- Host-port conflicts and Docker/network failures are shown with actionable messages.
- The same exported Linux lab spec can be used on Windows and macOS without platform-specific edits.
- Windows Quick Start cannot be started on macOS and explains why.

## Dependencies

- [Check macOS and Docker Readiness](macos-desktop-readiness.md).
- [Open a Node Shell in macOS Terminal](macos-desktop-open-node-shell.md).

## Implementation Status

Not started.
