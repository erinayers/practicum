# Connect Practicum to a Remote Windows VM

## Hypothetical User Story

As a customer with a ready Windows VM,
I want to open its desktop or terminal securely from Practicum,
so that I can complete the lab without configuring remote access myself.

## Functional Requirements

- Authenticate and encrypt the connection, binding it to the customer's active VM session.
- Provide only the access modes enabled by the profile, such as remote desktop and PowerShell.
- Keep remote access separate from host management networks and other customers' sessions.
- Expire or revoke credentials when the session ends, is revoked, or the user loses entitlement.

## Acceptance Criteria

- A customer can access only their assigned VM while its authorized session is active.
- Remote desktop/terminal access works through a documented Practicum workflow.
- A disconnected session can be resumed only while authorization and the VM session remain valid.
- Stopping or revoking a session promptly prevents further remote access.
- Errors do not reveal host addresses, credentials, product keys, or other tenants' details.

## Dependencies

- [Provision an Entitled Windows VM](provision-windows-vm.md).
- Identity service, secure gateway, and remote desktop/terminal components.

## Status

Hypothetical; not started.
