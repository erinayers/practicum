# Start a Lab in Hosted Runtime

## Hypothetical User Story

As an instructor or student with an eligible lab,
I want to start it on managed remote Linux-container infrastructure,
so that I can use the lab without requiring local Docker capacity.

## Functional Requirements

- Validate lab compatibility, account entitlement, quota, and available region before provisioning.
- Create per-lab isolated runtime resources from the portable lab spec; do not silently upload
  private specs or secrets before the user confirms.
- Show image pull, startup, and failure progress through the existing lifecycle model.
- Preserve local runtime support and report unsupported lab features with specific explanations.

## Acceptance Criteria

- The user sees which lab data will be uploaded and confirms before first hosted provisioning.
- Supported lab specs start with progress and actionable errors visible in Practicum.
- Unsupported images, resource requirements, or features are identified before resource allocation
  when possible.
- A hosted lab is clearly distinguished from a local lab in the dashboard and running view.

## Dependencies

- [Connect a Practicum Workspace to Hosted Runtime](connect-hosted-runtime.md).
- Hosted scheduler, registry access, isolated Docker runtime, and compatible lab contract.

## Status

Hypothetical; not started.
