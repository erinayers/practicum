# Hypothetical Epic: Remote Windows VM Service

## Status

Exploratory paid-service concept only. This is separate from the open-source Windows-container
Quick Start and does not assume that any particular Windows image, license, host, or customer access
model can be offered without further review.

## Epic Goal

Let an eligible Practicum customer request and access an isolated remote Windows virtual machine
for supported lab exercises from the Practicum desktop app.

This epic is about a full Windows guest VM, not a Windows container. It also differs from the
[general Hosted Lab Runtime](../hosted-lab-runtime/README.md), which targets Linux containers, and
the [Remote macOS VM Service](../remote-macos-vm-service/README.md), which requires Apple hardware
and separate platform review.

## Paywall Recommendation

Paid only. Compute, storage, GPU options if ever offered, licensing, secure remote access, support,
and operations all create ongoing costs. The open-source local Windows-container and Linux Docker
workflows remain usable without this service.

## Licensing and Product Gates

- Get specialist licensing and legal review for every target edition, host model, customer type,
  region, and access pattern before implementation or sale.
- Windows 11 virtualization rights depend on the customer's license and the chosen virtualization
  method; Windows Server guest licensing has separate rules. Microsoft guidance is a starting point,
  not a substitute for applicable agreements: [Windows 11 virtual desktop licensing](https://www.microsoft.com/licensing/guidance/Windows-11-Licensing-for-Virtual-Desktops),
  [Windows Server virtualization licensing](https://www.microsoft.com/licensing/guidance/Windows-Server-Virtualization-Technologies),
  and [SPLA guidance](https://www.microsoft.com/licensing/guidance/SPLA).
- Do not collect or reuse customer product keys unless a reviewed design specifically requires a
  supported licensing flow.
- Do not start a VM unless its software entitlement is established and recorded.

## Hypothetical Stories

- [Request an Eligible Windows VM](request-windows-vm.md)
- [Provision an Entitled Windows VM](provision-windows-vm.md)
- [Connect Practicum to a Remote Windows VM](connect-to-windows-vm.md)
- [Manage Windows VM Sessions and Charges](manage-windows-vm-sessions.md)
- [Operate a Compliant Windows VM Fleet](operate-windows-vm-fleet.md)
