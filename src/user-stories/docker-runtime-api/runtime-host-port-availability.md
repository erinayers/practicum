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
