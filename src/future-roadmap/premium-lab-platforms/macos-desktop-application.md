# macOS Desktop Application

## User Story

As a student or instructor on a Mac,
I want Practicum to run natively on macOS with the Linux labs I have today,
so that Mac users are first-class members of a course before any paid macOS-specific feature
exists.

## Why This Matters

The desktop is PySide6 and the API is Python, so a Mac build is mostly packaging and
platform details; Docker Desktop for Mac runs the same Linux containers. A free Mac app is the
prerequisite for the paid macOS labs story and widens the free product's audience.

## Functional Requirements

- Build and sign a macOS app bundle (Apple silicon and Intel) with the embedded API, the same
  way `build-windows.ps1` produces the Windows build; notarisation for Gatekeeper.
- Platform adjustments: `Open shell` opens Terminal.app (or iTerm) with `docker exec`; menus,
  shortcuts and file dialogs follow macOS conventions; settings and screenshots go to
  `~/Library/Application Support/Practicum`.
- The Docker probe and readiness texts speak of Docker Desktop for Mac; Windows-container
  readiness reports "not available on macOS" (no switching instructions) and points to the
  hosted option.
- Everything free stays free on macOS: Ubuntu quick starts, designer, import/export, manual,
  results, screenshots.

## Acceptance Criteria

- The Phase 1–7 desktop acceptance criteria pass on macOS with Docker Desktop for Mac.
- Open shell works on a running Linux node via Terminal.app.
- A Windows lab on a Mac is importable and explained as not runnable locally.
- The app installs from a signed, notarised `.dmg`/`.pkg`.

## Paywall Guidance

Free. This is the open-source core on another host OS.

## Dependencies

- Existing desktop; `node_shell.py` (terminal launcher per platform); packaging scripts.

## Implementation Status

Not started (roadmap).
