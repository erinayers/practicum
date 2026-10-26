# Connect Practicum to a Remote Mac VM

## Hypothetical User Story

As a customer with a ready macOS lab VM,
I want to connect to its desktop and terminal from Practicum on Windows,
so that I can follow the lab without managing remote access tools myself.

## Functional Requirements

- Establish an authenticated, encrypted connection to only the customer's assigned VM.
- Provide the access modes supported by the selected lab profile, such as a remote desktop and
  terminal, without exposing the host management network.
- Display connection state, VM name, guest version, and actionable reconnect guidance.
- Expire and revoke access when the session ends or is terminated by an administrator.

## Acceptance Criteria

- A customer can connect only to a VM associated with their active session and account.
- Remote desktop/terminal access works through the documented Windows Practicum flow.
- Lost connections can be resumed only while the VM session remains active and authorized.
- Ending or revoking the session invalidates existing access credentials promptly.
- Connection failures do not reveal host addresses, host credentials, or other tenants' details.

## Dependencies

- [Provision a Licensed macOS VM](provision-macos-vm.md).
- Secure gateway and identity/entitlement service.

## Status

Hypothetical; not started.
