# Port Conflict UI

## User Story

As a Windows app user,  
I want port conflicts shown clearly in the interface,  
so that I understand why a browser-accessible lab cannot start and how to fix it.

## Why This Matters

Port conflicts are common on developer and student machines. A clear UI should explain whether a port is used by Practicum, another lab, Docker, or another local process, then offer a recommended replacement.

## User Flow

1. The user imports or edits a lab with host port mappings.
2. The app checks port availability.
3. Conflicting ports appear with clear warning states.
4. The app shows recommended replacement ports.
5. The user applies a recommendation.
6. The app revalidates the lab.

## Functional Requirements

- Port fields show available/unavailable state.
- Conflicts show the affected host port and node.
- The app explains whether the port is reserved by Practicum when known.
- The app shows recommended replacement ports.
- Start/export actions are disabled or guarded while conflicts remain.

## Acceptance Criteria

- Host port conflicts are visible before runtime start.
- The UI prevents users from starting a lab with known port conflicts.
- Users can apply a recommended port from the UI.
- The app rechecks the port after a recommendation is applied.

## Edge Cases

- The port becomes unavailable after the UI check.
- The app cannot determine which process owns the port.
- Multiple nodes conflict with the same port.
- The user changes the Practicum API port.

## Implementation Notes

- The UI should not require users to understand Docker error messages.
- This should be integrated into both Designer Mode and Student Import preview/start workflows.
