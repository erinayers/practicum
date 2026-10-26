# Epic: Premium Lab Platforms (Windows and macOS labs)

## Epic Goal

Offer labs whose *guest* operating system is Windows or macOS — in addition to the Linux
container labs the open-source core runs — as a paid capability, because neither can be run on
the computers most students on the free plan have.

## Why this is paid, and why now (scope change 2026-10-25)

Phase 8 built Windows Quick Start on top of Docker Desktop's Windows-container mode. Working
through what that needs on a real student machine changed the picture:

- **Windows containers need Windows 10/11 Pro, Enterprise or Education.** Docker Desktop's
  Windows-container mode relies on the Hyper-V and Containers Windows features, which
  **Windows Home does not have**. Students on Home laptops (the common case) cannot run the
  Windows template at all, whatever Practicum does. The Linux-container path (WSL 2) works on
  Home, which is why the open-source core stays Linux-based.
- **macOS guests are harder still.** Docker has no macOS containers. A macOS lab means a macOS
  virtual machine, which Apple's licence only allows on Apple hardware (and limits to two
  concurrent VMs), using Apple's Virtualization framework on Apple-silicon Macs. There is no
  free, cross-platform way to give a student a macOS lab.

Both therefore fail the open-core test ("useful on the student's own computer without paying")
for reasons outside Practicum's control, and both need work the core does not — licence
entitlement, host-edition checks, possibly hosted runtimes. They belong in a paid tier, as this
epic describes. **The Phase 8 implementation stays in the codebase as built**; these stories
describe how it is gated, presented and extended later, not a rewrite.

## Paywall Recommendation

- Free: everything Linux — Ubuntu Desktop / Ubuntu quick starts, the designer, import/export,
  the runtime, the manual, results export, screenshots. Unchanged.
- Paid ("Pro" / institution plan): Windows-container labs (Windows Quick Start, Windows nodes in
  the designer, Open PowerShell), macOS labs, and the hosted runtime that lets students without
  an eligible machine run them anyway.
- The free app must say plainly *why* a Windows or macOS lab is unavailable (edition, hardware,
  plan) and what the options are; it must never silently hide the capability or break a lab an
  instructor already authored.

## Stories

1. [Entitlements and Feature Gating](entitlements-and-feature-gating.md) — how a paid feature is
   switched on in a desktop app that is otherwise open source.
2. [Windows Labs Behind the Pro Plan](windows-labs-premium-tier.md) — gate the Phase 8 Windows
   Quick Start, Windows nodes and PowerShell shell.
3. [Windows Edition and Virtualisation Eligibility Check](windows-edition-eligibility-check.md) —
   tell a student *before* they buy whether their PC can run Windows labs at all.
4. [Hosted Windows Labs for Ineligible Machines](hosted-windows-labs.md) — run the Windows lab
   for them when their PC cannot.
5. [macOS Desktop Application](macos-desktop-application.md) — the free prerequisite: Practicum
   on a Mac running Linux labs.
6. [macOS Labs Behind the Pro Plan](macos-labs-premium-tier.md) — macOS guests on Apple-silicon
   Macs, paid.
7. [Instructor Authoring for Premium Platforms](instructor-authoring-premium-platforms.md) — what
   an instructor without the plan (or without the hardware) can still do with a Windows/macOS
   lab spec.

## Dependencies

- Phase 8 stories (built 2026-10-25): `windows-desktop-windows-container-readiness`,
  `designer-windows-quick-start`, `windows-desktop-open-windows-shell`,
  `designer-windows-quick-start-packages`.
- [Open Core Boundary](../open-source-core-sustainability/open-core-boundary.md) — this epic
  adds an explicit carve-out to it (see its addendum).
- Future hosted runtime ("Managed Runtime Later" in the roadmap README).

## Open questions

- Plan names and prices are not decided; the stories say "the Pro plan" as a placeholder.
- Whether an instructor's licence should cover their students for a course (classroom plan) or
  each student needs their own — see the classrooms epic.
