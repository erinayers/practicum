# Node Command Options

## User Story

As a lab designer,  
I want to control whether a node uses the Practicum default command or the image's default command,  
so that both CLI-only containers and service-oriented containers can run correctly.

## Why This Matters

CLI lab nodes work well with a long-running command like `sleep infinity`, but web desktop and service images usually need their built-in entrypoint or command to start properly.

## Functional Requirements

- Nodes default to a long-running CLI-friendly command.
- A node can set `command` to `null` to use the image default startup behavior.
- A node can provide a custom command list.
- Export, import, preview, and runtime start preserve command behavior.

## Acceptance Criteria

- CLI nodes continue to run with `sleep infinity` by default.
- Browser/service nodes can opt into the image default command.
- Custom command lists are accepted by the spec.
- The Docker runtime applies the selected command behavior.

## Status

Done.
