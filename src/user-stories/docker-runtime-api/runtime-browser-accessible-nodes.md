# Browser Accessible Lab Nodes

## User Story

As a student,  
I want some lab nodes to expose browser-accessible services or desktops,  
so that I can use GUI tools without manually attaching to a container shell.

## Why This Matters

Some labs need more than CLI containers. Web desktops, Kali/Ubuntu GUI environments, dashboards, and custom web apps should be reachable from the student's browser while still being defined by the lab spec.

## Functional Requirements

- A node can expose host-to-container port mappings.
- A node can define environment variables.
- A node can use the image default command instead of Practicum forcing `sleep infinity`.
- A node can request shared memory for browser/desktop workloads.
- Browser-accessible nodes still participate in the lab topology.

## Acceptance Criteria

- A lab spec can map host ports to container ports.
- A lab spec can set node environment variables.
- A lab spec can set `command` to `null` to use the image default startup behavior.
- A lab spec can request `shm_size_mb`.
- The Docker runtime applies these settings when starting containers.

## Example

See [ubuntu-webtop.json](../../../examples/ubuntu-webtop.json).
