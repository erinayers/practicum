# Provision a Licensed macOS VM

## Hypothetical User Story

As the Practicum VM service,
I want to create an isolated macOS VM on an eligible Mac host from an approved profile,
so that a customer receives a predictable, clean lab environment.

## Functional Requirements

- Provision only on approved Apple hardware using an approved macOS version and virtualization
  configuration.
- Use a documented image or installation workflow whose source, integrity, and authorization are
  recorded; never bundle an unapproved OS image with Practicum.
- Assign each VM a unique identity, isolated storage, bounded CPU/memory/disk resources, and a
  short-lived session credential.
- Report provisioning progress and failures without exposing host credentials or other customers'
  data.

## Acceptance Criteria

- A request creates a VM only after eligibility and legal-policy gates pass.
- The VM runs on an eligible Mac host and receives the approved guest version and resource limits.
- The system records host ID, guest version, image/install source, VM identity, and provisioning
  outcome for audit.
- Failed provisioning releases reserved capacity and reports a useful status to the customer.
- No VM can access another customer's VM disk, credentials, or session.

## Dependencies and Gates

- Approved licensing/operating model and macOS installation source.
- Mac host fleet and virtualization orchestrator.
- [Request an Eligible macOS Lab VM](request-macos-vm.md).

## Status

Hypothetical; not started.
