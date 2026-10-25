# Open a PowerShell Shell on a Windows Lab Node

## User Story

As a student working in a Windows Quick Start lab,
I want **Open shell** to launch PowerShell inside the Windows container,
so that I can follow the lab instructions using native Windows commands.

## Why This Matters

The existing shell action enters Linux containers with `sh`. A Windows container has no POSIX
shell, so reusing that command would open a terminal that immediately fails.

## Functional Requirements

- Identify the node's declared container OS/shell instead of guessing from arbitrary image text.
- Launch `docker exec` with PowerShell for Windows nodes and preserve the current bash/sh behavior
  for Linux nodes.
- Keep the shell in a separate interactive host terminal and leave the existing error/copy-command
  behavior available if launch fails.
- Show the node name and shell type in the action and its success/error message.

## Acceptance Criteria

- **Open shell** on a running Windows Quick Start node opens an interactive PowerShell prompt in
  that container.
- **Open shell** on Linux nodes continues to prefer bash and falls back to sh.
- A stopped or missing Windows container produces a visible, actionable error rather than a
  silent terminal flash.
- The shell selection is preserved when a lab is exported and imported.

## Dependencies

- Enables `designer-windows-quick-start.md`.
- The lab spec must carry an explicit supported OS/shell hint if the image alone cannot determine
  the correct shell.

## Implementation Status

Not started.
