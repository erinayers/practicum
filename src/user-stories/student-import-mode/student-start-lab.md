# Start Lab

## User Story

As a student,  
I want to start an imported lab,  
so that Docker creates the required environment for the exercise.

## Why This Matters

Starting the lab is the central student action. It should create the needed Docker resources reliably and make failures understandable.

## User Flow

1. The student opens an imported lab.
2. The student clicks Start.
3. The app asks the API to start the lab.
4. The API creates Docker networks and containers.
5. The app displays progress and final status.

## Functional Requirements

- The app calls a local start endpoint.
- The app shows startup progress or pending state.
- The runtime creates Docker networks.
- The runtime creates Docker containers.
- The runtime attaches containers to the correct networks.
- Startup errors are visible and actionable.

## Acceptance Criteria

- The app starts the lab using the local API.
- Docker networks are created.
- Docker containers are created and attached to the correct networks.
- The lab status changes from `defined` to `running`.
- Startup errors are shown clearly.

## Edge Cases

- Docker is unavailable.
- A required image cannot be pulled.
- A container name already exists.
- A network succeeds but container creation fails.
- The student cancels startup while work is in progress.

## Implementation Notes

- The runtime API epic defines the backend start behavior.
- The UI should wait for API confirmation before showing `running`.
