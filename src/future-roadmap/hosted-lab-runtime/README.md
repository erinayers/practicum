# Hypothetical Epic: Hosted Lab Runtime Service

## Status

Exploratory paid-service concept. This is separate from Practicum's local open-source runtime and
from the specialized [Remote macOS VM Service](../remote-macos-vm-service/README.md).

## Epic Goal

Let customers run compatible Linux-container labs on managed remote infrastructure when their
computer cannot or should not run Docker locally. Practicum remains the lab authoring and control
surface; the hosted service supplies isolated runtime capacity, secure access, and lifecycle
management.

This epic assumes ordinary Linux containers, not macOS guests. A remote macOS VM requires Apple
hardware and its own licensing, operating, and access review.

## Paywall Recommendation

Paid. Remote compute, persistent storage, network isolation, operations, monitoring, and support
create ongoing per-customer costs. The local API and Docker runtime remain available in the
open-source product.

## Hypothetical Stories

- [Connect a Practicum Workspace to Hosted Runtime](connect-hosted-runtime.md)
- [Start a Lab in Hosted Runtime](start-hosted-lab.md)
- [Access Lab Services Remotely](access-hosted-lab-services.md)
- [Manage Hosted Lab Sessions and Usage](manage-hosted-lab-usage.md)
- [Operate Isolated Hosted Runtime Capacity](operate-hosted-runtime.md)

## Product and Security Gates

- Define supported lab profiles, regions, quotas, data retention, and service availability.
- Specify isolation guarantees for containers, networks, storage, secrets, and tenant data.
- Review privacy, security, and regulatory obligations before accepting customer labs or data.
- Make remote hosting optional; importing/exporting compatible lab specs and running them locally
  must remain possible without a paid account.
