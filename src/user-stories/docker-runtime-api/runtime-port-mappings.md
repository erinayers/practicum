# Node Port Mappings

## User Story

As a lab designer,  
I want to map host ports to container ports,  
so that students can open web apps, dashboards, and browser desktops from their local browser.

## Why This Matters

Some lab nodes expose useful HTTP/HTTPS services. Students need predictable local URLs like `http://localhost:3000` or `https://localhost:3001` without manually running Docker commands.

## Functional Requirements

- A node can define host-to-container port mappings.
- Port mappings include protocol.
- Duplicate host/protocol mappings are rejected.
- Port mappings cannot overlap with simple exposed ports.
- Runtime applies mappings with `docker run -p`.
- Preview includes port mappings.

## Acceptance Criteria

- A lab spec can map host ports to container ports.
- Invalid ports are rejected.
- Duplicate host/protocol mappings are rejected.
- Preview shows mapped ports.
- The Docker runtime applies mapped ports.

## Status

Done.
