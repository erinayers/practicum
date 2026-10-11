# Node Environment Variables

## User Story

As a lab designer,  
I want to define environment variables for a node,  
so that container images can be configured without creating custom images.

## Why This Matters

Many Docker images are configured through environment variables. Browser desktops, dashboards, databases, and training services often need titles, passwords, modes, or feature flags supplied at container startup.

## Functional Requirements

- A node can define environment variable names and values.
- Environment variable names are validated.
- Environment variables are exported and imported as part of the lab spec.
- The Docker runtime passes variables to `docker run`.

## Acceptance Criteria

- A lab spec can include node-level environment variables.
- Invalid environment variable names are rejected.
- The runtime applies variables with `-e`.
- Preview/export/import preserve environment settings.

## Status

Done.
