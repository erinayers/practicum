# Run Practicum on macOS

## User Story

As a Practicum user with a Mac,
I want to launch the desktop app and its local API using a documented Mac workflow,
so that I can use Practicum without Windows-specific scripts or setup steps.

## Functional Requirements

- Provide a documented macOS development launch path using supported Python and project dependencies.
- Start and stop the desktop app and local API together in development, with clear behavior if the
  API port is already occupied.
- Resolve app resources such as icons and bundled files correctly from source and packaged builds.
- Replace Windows-specific setup guidance and readiness messages with platform-appropriate steps.

## Acceptance Criteria

- A developer can create an environment, install the project, and launch the desktop app on a
  supported macOS version using the documented commands.
- The local API starts and stops with the desktop app in the documented development workflow.
- An occupied API port produces a useful message and does not silently connect to an unrelated
  service.
- App resources load from both a source checkout and a packaged app bundle.

## Dependencies

- macOS Python and PySide6 support.
- [Check macOS and Docker Readiness](macos-desktop-readiness.md).

## Implementation Status

Not started.
