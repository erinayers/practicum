# Manage VM Sessions and Charges

## Hypothetical User Story

As a customer using a paid macOS VM,
I want to see session time, remaining limits, and charges and to stop the VM when finished,
so that I can control usage and avoid unexpected costs.

## Functional Requirements

- Show session state, elapsed time, price basis, any plan allowance, and the next billing boundary
  before and during a session.
- Support stop, restart, and permitted session extension actions with clear confirmation where a
  charge or data-loss consequence applies.
- Enforce plan limits and hard maximum session duration server-side.
- Explain persistence and cleanup behavior before the customer starts the session.

## Acceptance Criteria

- The customer can see current usage and the applicable charge basis before starting and while
  connected.
- Session limits are enforced even if the client disconnects or closes unexpectedly.
- Stopping a VM ends compute billing according to the disclosed policy and revokes session access.
- The service applies the disclosed data-retention policy and confirms when temporary VM data is
  deleted.
- Usage records can be reviewed by the customer and reconciled with the account's billing record.

## Dependencies

- Billing and entitlement service.
- [Connect Practicum to a Remote Mac VM](connect-to-macos-vm.md).
- [Operate a Compliant Mac Host Fleet](operate-mac-host-fleet.md).

## Status

Hypothetical; not started.
