# Report Lab Runtime Status

## User Story

As a student,  
I want to see whether my lab is defined, running, stopped, or errored,  
so that I know what state my environment is in.

## Why This Matters

Reliable status keeps users oriented. It also lets the app decide which actions are currently safe or available.

## User Flow

1. The desktop app requests lab status.
2. The API returns the stored lab status.
3. The API may reconcile with Docker state.
4. The desktop app updates controls and status messages.
5. The student sees whether action is needed.

## Functional Requirements

- The API exposes runtime status for a lab.
- The status includes the lab-level state.
- The status includes container-level details when available.
- Missing Docker resources are detected and reported.
- The desktop app refreshes status after runtime actions.

## Acceptance Criteria

- API exposes lab runtime status.
- Desktop UI refreshes status.
- Container-level errors are visible.
- Missing Docker resources are detected and reported.

## Edge Cases

- Docker resources were manually removed outside Practicum.
- The API restarted and lost in-memory runtime state.
- A container is running but unhealthy.
- The desktop app polls while start or stop is in progress.

## Implementation Notes

- Current lab persistence is in-memory, so durable runtime state is a future concern.
- Status reporting should evolve before more advanced orchestration features are added.

## Update 2026-10-24

`RuntimeResourceStatus` gained `note`: for a running container, the first line of `/run/practicum-packages.status` if the container keeps one (the quick start's package-install marker), read with `docker exec <name> cat …` (5 s timeout, absent file → `null`). Lets the desktop show "installing packages…" / "packages ready" / "install FAILED" in the Lab nodes table.
