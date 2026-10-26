# Manage Hosted Lab Sessions and Usage

## Hypothetical User Story

As a customer using hosted labs,
I want to see active sessions, usage, limits, and charges and stop labs when finished,
so that I can control costs and avoid leaving remote resources running.

## Functional Requirements

- Display the plan, resource limits, price basis, session start time, and current usage before and
  during hosted use.
- Support stop, reset, and delete with clear explanations of storage and data-retention effects.
- Enforce quotas and maximum session duration server-side, including after desktop disconnection.
- Provide usage history and transparent handling of billing disputes or failed provisioning.

## Acceptance Criteria

- Customers can review usage and applicable charges for active and past sessions.
- Stopping or deleting a lab releases compute resources according to the disclosed policy.
- Session limits remain enforced when the client closes or loses network connectivity.
- Persistent data is retained or deleted according to the selected plan and disclosed retention
  policy.

## Dependencies

- Billing, metering, quota, and entitlement services.
- [Start a Lab in Hosted Runtime](start-hosted-lab.md).

## Status

Hypothetical; not started.
