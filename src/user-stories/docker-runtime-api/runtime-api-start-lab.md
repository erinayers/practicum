# Start Lab Through API

## User Story

As the desktop application,  
I want to call a local API endpoint to start a lab,  
so that Docker orchestration is handled consistently by the backend.

## Why This Matters

The local API should own Docker orchestration. This gives the desktop app and future automation a single reliable way to start lab environments.

## User Flow

1. The desktop app sends `POST /labs/{lab_id}/start`.
2. The API loads the lab definition.
3. The runtime creates required Docker networks.
4. The runtime creates and configures containers.
5. The API updates lab status and returns the result.

## Functional Requirements

- The API exposes a start endpoint.
- The API rejects unknown lab IDs.
- The runtime creates networks represented in the lab definition.
- The runtime creates containers represented by nodes.
- The runtime attaches containers to the correct networks.
- The API returns clear errors for Docker failures.

## Acceptance Criteria

- API exposes `POST /labs/{lab_id}/start`.
- Starting a lab creates required Docker networks.
- Starting a lab creates required Docker containers.
- API returns updated lab status.
- API reports Docker errors in a structured response.

## Edge Cases

- Docker is unavailable.
- Required images are not available.
- Network or container names collide with existing Docker resources.
- Startup partially succeeds and needs cleanup.
- The lab is already running.

## Implementation Notes

- Add a runtime abstraction before binding tightly to Docker.
- Use labels or a naming convention so Practicum can identify created resources.
- Consider statuses such as `defined`, `starting`, `running`, `stopping`, `stopped`, and `error`.
