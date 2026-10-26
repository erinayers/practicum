# Manage Windows VM Sessions and Charges

## Hypothetical User Story

As a customer using a hosted Windows VM,
I want to see usage, limits, and charges and stop the VM when finished,
so that I can control costs and avoid leaving resources active.

## Functional Requirements

- Show session state, elapsed time, price basis, plan allowance, and resource profile before and
  during use.
- Let the customer stop, restart, or extend a session subject to entitlement and capacity.
- Enforce quotas and maximum duration server-side, including after client disconnection.
- Explain what happens to the VM disk, snapshots, and user files when the session ends.

## Acceptance Criteria

- Customers can inspect the charge basis and current usage before and during each session.
- Session limits remain enforced if Practicum closes or loses connectivity.
- Stopping a VM releases billable compute according to the disclosed plan.
- Persistence and deletion follow the selected plan and disclosed retention policy.
- Usage history is available to the account owner and can be reconciled with billing.

## Dependencies

- Billing, metering, entitlement, and quota services.
- [Connect Practicum to a Remote Windows VM](connect-to-windows-vm.md).

## Status

Hypothetical; not started.
