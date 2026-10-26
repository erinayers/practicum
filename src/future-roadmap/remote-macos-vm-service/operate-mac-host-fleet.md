# Operate a Compliant Mac Host Fleet

## Hypothetical User Story

As a Practicum service operator,
I want to manage eligible Mac hosts, guest capacity, and compliance records,
so that customer VM sessions remain available, isolated, and within the approved operating model.

## Functional Requirements

- Register and attest eligible Apple hardware, supported host OS versions, virtualization support,
  and available capacity.
- Gate provisioning on current platform-policy approval, approved software sources, and host health.
- Monitor capacity, security updates, host isolation, provisioning failures, and guest cleanup.
- Provide audited administrative access and emergency session termination.
- Keep customer data and credentials isolated; define retention, backup, incident response, and
  secure deletion procedures.

## Acceptance Criteria

- Hosts that fail eligibility, health, or policy checks cannot receive new customer VMs.
- Operators can see host capacity and active guest/session ownership without exposing guest data
  unnecessarily.
- Administrative actions, policy changes, and emergency VM termination are audited.
- Host retirement verifies that customer sessions ended and retained data was deleted or handled
  under the disclosed policy.
- A documented approval review is renewed when Apple terms, supported hardware, macOS versions, or
  the service model changes.

## Dependencies and Gates

- Written legal/platform review for the operator's specific hosting and customer-access model.
- Apple hardware procurement, infrastructure operations, security, and incident response.
- macOS virtualization and remote access implementation.

## Status

Hypothetical; not started.
