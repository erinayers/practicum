# Open a Node Shell in macOS Terminal

## User Story

As a student running a lab on macOS,
I want **Open shell** to open the selected node in a host terminal,
so that I can use the lab's command line alongside the Practicum app.

## Functional Requirements

- Open the existing `docker exec` shell command in Terminal.app using a supported macOS launch
  mechanism.
- Preserve Linux-node bash preference and sh fallback.
- Keep the terminal interactive and leave Docker errors visible to the user.
- If a terminal cannot be opened, show the command and offer a way to copy it.

## Acceptance Criteria

- **Open shell** on a running Linux node opens an interactive shell in Terminal.app.
- The shell prefers bash and falls back to sh for images without bash.
- A stopped/missing container or unavailable terminal produces a visible, actionable message.
- Existing Windows and Linux host shell behavior remains intact.

## Dependencies

- [Run Practicum on macOS](macos-desktop-run-app.md).
- [Run Linux Labs on macOS](macos-desktop-run-linux-labs.md).

## Implementation Status

Not started.
