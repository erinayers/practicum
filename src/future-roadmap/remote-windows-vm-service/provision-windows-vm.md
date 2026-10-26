# Provision an Entitled Windows VM

## Hypothetical User Story

As the Practicum hosted VM service,
I want to provision an isolated Windows VM from an approved profile after its entitlement is
verified,
so that the customer receives a ready-to-use and properly licensed environment.

## Functional Requirements

- Provision only on approved infrastructure with supported host virtualization and a reviewed
  licensing path for the selected Windows edition.
- Use an approved image or installation source and record its version, integrity, and entitlement
  reference.
- Apply a bounded CPU, memory, disk, network, and session profile with a unique VM identity.
- Report provisioning progress and failures without exposing host credentials or another tenant's
  information.

## Acceptance Criteria

- VM creation is blocked unless entitlement and policy gates succeed.
- The VM matches its approved edition and resource profile, and its image/source is auditable.
- The VM receives no reusable host credentials or another tenant's data.
- Failed provisioning releases reserved capacity and reports an actionable failure.
- No product key is written to logs, lab specs, or customer-visible diagnostics.

## Dependencies and Gates

- [Request an Eligible Windows VM](request-windows-vm.md).
- Approved host fleet, image lifecycle, and entitlement verification.

## Status

Hypothetical; not started.
