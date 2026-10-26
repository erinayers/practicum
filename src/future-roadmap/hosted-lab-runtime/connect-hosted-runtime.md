# Connect a Practicum Workspace to Hosted Runtime

## Hypothetical User Story

As a Practicum user with a hosted-runtime plan,
I want to connect my desktop app to my hosted workspace,
so that I can manage eligible labs on remote infrastructure from the familiar Practicum UI.

## Functional Requirements

- Authenticate the user and bind the desktop session to the correct account and workspace.
- Show whether a lab is local or hosted and identify the selected runtime before any lifecycle action.
- Keep local API/Docker controls separate from hosted controls to prevent actions on the wrong
  environment.
- Support sign-out, token expiration, and revocation without leaving reusable credentials in logs
  or exported lab specs.

## Acceptance Criteria

- An entitled user can sign in and see the workspaces they are authorized to access.
- The UI clearly identifies the target runtime before start, stop, reset, or delete actions.
- Expired or revoked credentials cause a clear sign-in prompt and do not trigger a lifecycle action.
- Users without hosted entitlement can continue using the local open-source workflow.

## Dependencies

- Account, authentication, entitlement, and hosted control-plane services.
- Security review for desktop credential storage and session handling.

## Status

Hypothetical; not started.
