# Access Lab Services Remotely

## Hypothetical User Story

As a student using a hosted lab,
I want to reach its web services and terminal through secure remote access,
so that I can complete lab work without exposing the runtime host to the public internet.

## Functional Requirements

- Provide authenticated, time-bounded routes to explicitly published lab services.
- Avoid exposing Docker bridge addresses or host management ports directly to the customer.
- Show which service ports are available and how to open them from Practicum.
- Provide shell access only through a controlled, audited channel with per-session authorization.

## Acceptance Criteria

- A student can open published web services from the Practicum running view over an authenticated
  connection.
- Unpublished ports and other tenants' services cannot be reached through the student's session.
- Expired, ended, or revoked sessions lose access promptly.
- Shell access is limited to the selected lab and is logged without recording command contents by
  default.

## Dependencies

- [Start a Lab in Hosted Runtime](start-hosted-lab.md).
- Secure gateway, identity, and remote terminal services.

## Status

Hypothetical; not started.
