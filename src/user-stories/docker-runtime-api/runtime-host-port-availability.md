# Host Port Availability Checks

## User Story

As a lab designer or student,  
I want Practicum to detect host ports that are already in use,  
so that browser-accessible lab nodes do not fail at runtime because of port conflicts.

## Why This Matters

Browser-accessible labs depend on host port mappings. If a requested host port is already used by the Practicum API, another lab, Docker, a local dev server, or another application, the lab may fail to start or the student may open the wrong service.

## User Flow

1. The designer defines a node with host port mappings.
2. The app checks whether the requested host ports are available.
3. Ports already in use are marked as unavailable.
4. The app blocks validation/export/start until conflicts are resolved.
5. The app suggests available replacement ports.

## Functional Requirements

- Practicum can check whether a host port is already bound locally.
- Practicum can detect ports reserved by the Practicum API itself.
- Practicum can detect host ports already assigned in the current lab spec.
- Practicum can detect host ports already assigned to other known labs.
- Validation results identify the node and port mapping that conflicts.

## Acceptance Criteria

- A host port already used by the Practicum API is rejected.
- A host port already used by another process is rejected.
- Duplicate host ports within one lab spec are rejected.
- Port conflict errors identify the affected node and port.
- The UI prevents start/export when unresolved port conflicts exist.

## Edge Cases

- A port is available during validation but becomes unavailable before start.
- A user changes the API port to a value used by a lab.
- Another application releases a port after validation.
- UDP and TCP mappings use the same numeric port.

## Implementation Notes

- This likely needs both API validation and desktop UI support.
- The backend should expose a port availability check so the Windows app does not need to implement OS-specific probing alone.
- Port availability should be checked again immediately before runtime start.

## Implementation Status (update 2026-10-24)

- `POST /labs/{lab_id}/start` now re-checks the host ports immediately before starting and returns a structured `host port conflict: <node> <port>/<protocol>: <reason> (try <port>)` failure (status `error`, `last_error` set) without calling Docker, so the "UI prevents start" half of the last AC holds even when conditions changed after the gate.
- UDP mappings are now probed with a UDP socket (Tigre/06 #4).
- Export is deliberately **not** blocked by host-port conflicts (decision D-30, Tigre/09 Q-2): host ports are machine-specific and the exported spec is portable; the last AC's wording is narrowed to start (the desktop has no export action yet — Tigre/11 S-10).
