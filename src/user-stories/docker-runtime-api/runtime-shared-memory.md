# Node Shared Memory Settings

## User Story

As a lab designer,  
I want to request shared memory for a node,  
so that browser-based and GUI-heavy containers have enough shared memory to run reliably.

## Why This Matters

Browser desktop containers can fail or behave poorly with Docker's small default shared memory allocation. A spec-level `shm_size_mb` setting lets instructors define this requirement explicitly.

## Functional Requirements

- A node can define `resources.shm_size_mb`.
- The value must be positive.
- The value is exported and imported with the lab spec.
- The runtime applies the value using Docker's `--shm-size` option.

## Acceptance Criteria

- A lab spec can request shared memory in MB.
- Invalid shared memory values are rejected.
- The Docker runtime applies `--shm-size`.
- Browser desktop examples can use the setting.

## Status

Done.
