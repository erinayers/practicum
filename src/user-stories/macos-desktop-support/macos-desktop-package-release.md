# Install Practicum on macOS

## User Story

As a Mac user,
I want to download and install Practicum as a native macOS app,
so that I can use it without installing Python or building it from source.

## Functional Requirements

- Produce a macOS application bundle containing the desktop app, local API, Qt WebEngine runtime,
  icons, and other required resources.
- Document and publish the supported macOS versions and processor architectures for each release.
- Provide a downloadable distribution with appropriate Apple signing/notarization for the chosen
  release channel, plus clear installation and removal instructions.
- Build the app on macOS for its target architecture; do not treat the Windows build as a
  cross-platform artifact.

## Acceptance Criteria

- A Mac user can install and launch the release without a separate Python installation.
- The bundled API, Qt WebEngine view, app resources, and Docker readiness checks work after
  installation.
- The app opens without an unidentified-developer warning for the documented distribution path.
- Release notes state supported macOS versions, processor architectures, and Docker Desktop
  requirements.
- The app can be removed using the documented macOS steps without deleting user lab data silently.

## Dependencies

- [Run Practicum on macOS](macos-desktop-run-app.md).
- [Run Linux Labs on macOS](macos-desktop-run-linux-labs.md).
- [Open a Node Shell in macOS Terminal](macos-desktop-open-node-shell.md).

## Implementation Status

Not started.
