# Request an Eligible macOS Lab VM

## Hypothetical User Story

As an instructor or learner with an eligible paid Practicum plan,
I want to request a macOS lab VM for a supported use case,
so that I can practice macOS-specific tasks from my Windows computer.

## Why This Matters

Some classes and development exercises require macOS behavior that Linux containers cannot
provide. A remote Mac-hosted VM could make those exercises accessible to customers without a local
Mac, if the service model is permitted and supportable.

## Functional Requirements

- Show this capability only to authenticated customers whose plan, region, and requested use case
  are enabled for the service.
- Explain the host type, guest OS version, session duration, data handling, and expected charge
  before the customer confirms provisioning.
- Require explicit acceptance of the service terms and any applicable software terms.
- Refuse requests when eligibility, capacity, or required terms are missing.

## Acceptance Criteria

- An eligible customer can review a supported macOS VM profile and its pricing before requesting it.
- The customer must explicitly confirm the request and terms before any VM resources are allocated.
- Ineligible or unsupported requests receive a clear reason and do not allocate a host or VM.
- The service records who requested the VM, which profile was selected, and the terms version
  accepted.

## Dependencies and Gates

- Legal and platform-policy approval for the specific hosted access model.
- Account, entitlement, and billing service.
- [Operate a Compliant Mac Host Fleet](operate-mac-host-fleet.md).

## Status

Hypothetical; not started.
