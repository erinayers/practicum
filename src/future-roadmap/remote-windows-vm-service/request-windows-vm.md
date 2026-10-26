# Request an Eligible Windows VM

## Hypothetical User Story

As an instructor or learner with an eligible paid Practicum plan,
I want to request a Windows VM that matches my lab's supported profile,
so that I can practice Windows-specific workflows from my current computer.

## Functional Requirements

- Offer only Windows editions and profiles cleared for the service's host, region, and licensing
  model.
- Explain the VM edition, resource profile, supported use, session duration, persistence, and
  pricing before provisioning.
- Establish the required software entitlement before allocating a host.
- Require explicit customer confirmation of the request, terms, data handling, and any charge.

## Acceptance Criteria

- Eligible customers can review supported Windows VM profiles and pricing before requesting one.
- A request cannot proceed until required entitlement, region, capacity, and terms checks pass.
- Ineligible requests receive a clear explanation and allocate no VM resources.
- The service records the selected profile, entitlement source/reference, terms version, and
  requesting account for audit without logging product keys.

## Dependencies and Gates

- Licensing counsel and Microsoft program/provider review for the exact service model.
- Customer identity, subscription entitlement, and billing.
- [Operate a Compliant Windows VM Fleet](operate-windows-vm-fleet.md).

## Status

Hypothetical; not started.
