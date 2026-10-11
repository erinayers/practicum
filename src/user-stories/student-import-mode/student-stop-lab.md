# Stop Lab

## User Story

As a student,  
I want to stop a running lab,  
so that I can free system resources.

## Why This Matters

Students need a safe way to reclaim memory and CPU without deleting their imported lab or losing the ability to restart later.

## User Flow

1. The student opens a running lab.
2. The student clicks Stop.
3. The app asks the API to stop the lab.
4. The runtime stops lab containers.
5. The app updates status to stopped.

## Functional Requirements

- The app exposes Stop only when meaningful.
- The app calls a local stop endpoint.
- The runtime stops containers belonging to the selected lab.
- The imported lab spec remains available.
- The app shows stop failures.

## Acceptance Criteria

- The student can stop a running lab.
- Containers are stopped.
- The lab status changes to `stopped`.
- The app does not delete the imported lab spec.

## Edge Cases

- Some containers are already stopped.
- Docker is unavailable when the student tries to stop.
- A container cannot be stopped.
- The app closes while stop is in progress.

## Implementation Notes

- Stopped should mean resources are inactive but the lab remains known.
- Decide later whether networks remain after stop or are removed only on reset.
