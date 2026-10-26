# Windows Labs Behind the Pro Plan

## User Story

As the Practicum maintainer,
I want the Windows-container capabilities built in Phase 8 to be part of the paid plan,
so that the free product promises only what a student's Windows Home laptop can deliver,
while the work already done keeps its value for paying users.

## Why This Matters

Docker Desktop's Windows-container mode requires Windows Pro/Enterprise/Education (Hyper-V and
the Containers feature). Students on Windows Home cannot use the Windows template, so offering
it in the free plan sets them up to fail. Kept as a paid capability — with the eligibility check
and hosted option from the sibling stories — it becomes a coherent product instead of a trap.

## What is gated

Everything Phase 8 added that is specific to Windows guests:

- The **Windows** quick-start template (Create screen) and its Chocolatey tool catalog.
- Designer support for `os: windows` nodes (a future Windows host preset, editing Windows labs).
- Starting any lab whose `container_os` is `windows` (the pre-start gate's Container engine
  check gains the entitlement check next to the engine-mode check).
- **Open PowerShell** follows the node, so it is only ever reachable on a started Windows lab.

Not gated: the spec fields themselves (`os`, `shell`, `requires_screenshot`), validation,
import/export/preview/edit/delete of Windows labs, the `GET /docker/engine` probe, the design
icons, the manual editor, results export — all of which are core behaviour that merely
*supports* Windows labs.

## Functional Requirements

- With no entitlement, the Windows template row shows a "Pro" chip and the readiness panel
  explains: what the plan includes, that Windows Pro/Enterprise/Education with Docker Desktop in
  Windows-container mode is required (link to the eligibility check), and where to get the plan.
- With an entitlement, behaviour is exactly the Phase 8 behaviour (readiness check, template,
  tools, PowerShell, gate).
- An imported Windows lab on a free install: dashboard card shows a "Pro" chip; Open/Edit/
  Export/Delete work; Start opens the gate, which explains the entitlement (and, if relevant,
  the edition) instead of the engine-mode text.
- The API stays unaware of plans: gating is a desktop concern; `POST /start` keeps refusing only
  on real engine mismatches.

## Acceptance Criteria

- Free install: Linux templates unchanged; Windows template visible, marked Pro, not startable;
  the explanation names the edition requirement and the plan.
- Licensed install: all Phase 8 acceptance criteria still pass unchanged.
- Switching a licence on or off changes only the Windows controls.
- No Windows-specific code path is removed; the Phase 8 tests continue to run (under the
  licensed configuration in CI).

## Paywall Guidance

This carve-out from "the local runtime is free" is justified by a platform requirement outside
Practicum's control (Windows edition), not by withholding value; document it as such in the
open-core boundary so contributors understand the line.

## Dependencies

- [Entitlements and Feature Gating](entitlements-and-feature-gating.md)
- [Windows Edition and Virtualisation Eligibility Check](windows-edition-eligibility-check.md)
- Phase 8: `windows-desktop-windows-container-readiness`, `designer-windows-quick-start`,
  `windows-desktop-open-windows-shell`, `designer-windows-quick-start-packages`.

## Implementation Status

Not started (roadmap). The Phase 8 implementation it gates is complete and stays as built.
