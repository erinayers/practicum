# Operate a Compliant Windows VM Fleet

## Hypothetical User Story

As a Practicum service operator,
I want to manage Windows VM hosts, images, capacity, and licensing records,
so that customer sessions stay secure, supportable, and within the approved service model.

## Functional Requirements

- Register eligible hosts and approved Windows editions, images, regions, and license paths.
- Block scheduling when entitlement, image integrity, host health, or policy checks fail.
- Patch host and guest images, monitor capacity and incidents, and clean up orphaned resources.
- Audit privileged access, image changes, licensing decisions, and emergency session termination.
- Define data retention, backup, incident response, and customer support procedures.

## Acceptance Criteria

- Hosts and images that fail security, integrity, or licensing checks cannot receive customer VMs.
- Operators can audit entitlement references and VM ownership without collecting product keys in
  logs or dashboards.
- Customer data, credentials, networks, and VM disks remain isolated between tenants.
- Orphaned compute, storage, credentials, and network resources are detected and removed according
  to policy.
- Licensing and policy approval is revisited when the Windows edition, hosting provider, region, or
  customer access model changes.

## Dependencies and Gates

- Written legal/licensing approval for each offered edition and hosting arrangement.
- Security architecture, patch management, monitoring, incident response, and support operations.

## Status

Hypothetical; not started.
