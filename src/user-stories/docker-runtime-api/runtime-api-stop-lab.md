# Stop Lab Through API

## User Story

As the desktop application,  
I want to call a local API endpoint to stop a lab,  
so that users can shut down lab resources safely.

## Why This Matters

Stop is the safe shutdown path. It should release active resources while preserving enough state for the student to restart the lab later.

## User Flow

1. The desktop app sends `POST /labs/{lab_id}/stop`.
2. The API loads the lab runtime state.
3. The runtime stops containers belonging to that lab.
4. The API updates the lab status.
5. The API returns the updated lab state.

## Functional Requirements

- The API exposes a stop endpoint.
- The API rejects unknown lab IDs.
- The runtime stops containers for the selected lab.
- The API handles already-stopped labs predictably.
- The API returns clear errors when stop fails.

## Acceptance Criteria

- API exposes `POST /labs/{lab_id}/stop`.
- Running containers for that lab are stopped.
- Lab status updates to `stopped`.
- Stopping an already stopped lab is handled predictably.

## Edge Cases

- Some containers no longer exist.
- Docker is unavailable during stop.
- A container ignores or fails stop.
- The lab is in `starting` or `error` state.

## Implementation Notes

- Stopping does not have to remove containers in the first version.
- Idempotent stop behavior will make the desktop UI simpler.
