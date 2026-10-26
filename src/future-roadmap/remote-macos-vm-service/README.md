# Hypothetical Epic: Remote macOS VM Service

## Status

Exploratory paid-service concept only. This epic is not part of the open-source core backlog and
does not assume that Apple's terms permit any particular hosting, rental, or access model.

## Epic Goal

Let an eligible Practicum customer use a Windows Practicum client to request and access an isolated
macOS virtual machine running on an appropriately managed Mac host, for supported learning or
development labs.

This is a VM service, not a Docker image. Practicum's current Docker runtime cannot create macOS
guests. The service would require Mac hardware, a separate VM orchestration and access layer, and
an approved licensing and operating model. Apple documents macOS virtualization through its
[Virtualization framework](https://developer.apple.com/documentation/virtualization); current
permitted use must be reviewed against the [applicable Apple software license](https://www.apple.com/legal/sla/)
before implementation or sale.

## Paywall Recommendation

Paid only. The service depends on Mac hardware, hosting, capacity management, secure remote access,
operations, and ongoing licensing review. The open-source app can remain useful for local Linux
container labs without access to this service.

## Non-Goals and Constraints

- Do not distribute macOS VM images through Docker or imply macOS can run as a normal container.
- Do not provision or sell access until counsel and the relevant platform agreements confirm the
  proposed operator, customer, geography, and use case are permitted.
- Run guests only on eligible Apple hardware and through supported virtualization mechanisms.
- Do not bypass Apple account, activation, or software licensing controls.
- Keep VM access isolated, time-limited, auditable, and explicitly consented to by the customer.

## Hypothetical Stories

- [Request an Eligible macOS Lab VM](request-macos-vm.md)
- [Provision a Licensed macOS VM](provision-macos-vm.md)
- [Connect Practicum to a Remote Mac VM](connect-to-macos-vm.md)
- [Manage VM Sessions and Charges](manage-macos-vm-sessions.md)
- [Operate a Compliant Mac Host Fleet](operate-mac-host-fleet.md)
