# Windows Edition and Virtualisation Eligibility Check

## User Story

As a student (or an instructor advising students),
I want Practicum to tell me whether this PC can run Windows labs at all — before I pay and
before I try to switch Docker Desktop — so that I do not buy a plan or follow switching
instructions that cannot work on my machine.

## Why This Matters

Today's readiness check (Phase 8) answers only "is Docker serving Windows containers right
now?" and, if not, tells the user to switch Docker Desktop. On Windows Home the switch is
impossible: the Hyper-V and Containers features do not exist. The app should say that.

## Functional Requirements

- Detect the Windows edition (Home / Pro / Enterprise / Education; build number) and whether
  the **Hyper-V** and **Containers** optional features are present and enabled; read-only,
  never elevating, never changing features.
- Detect whether the CPU reports virtualisation support and whether it is enabled (where
  Windows exposes it without elevation), and whether Docker Desktop is installed.
- Fold the verdict into the Windows readiness panel with four outcomes: *eligible and ready*,
  *eligible but Docker is in Linux mode* (switch instructions, as today), *eligible but a
  feature is missing* (how to enable it, what it implies), *not eligible* (Windows Home: no
  Hyper-V/Containers; offer the hosted option and the Linux templates).
- Show the verdict on the plan page / upgrade prompt so nobody pays for a feature their edition
  cannot use.
- Keep the Microsoft and Docker requirement links; requirements change per release.

## Acceptance Criteria

- On Windows Home the panel states that Windows containers are not available on this edition
  and does not show switching instructions.
- On Pro/Enterprise/Education with the features disabled the panel names the missing feature
  and links to the enabling steps (which need administrator rights and a restart).
- On an eligible PC the behaviour is the Phase 8 behaviour.
- The check is read-only and runs without elevation; failures to detect degrade to the Phase 8
  message, never to a false "eligible".

## Paywall Guidance

The check itself should be free — it protects the user from buying the wrong thing and is
part of presenting the paid feature honestly.

## Dependencies

- Phase 8 `windows-desktop-windows-container-readiness` (extends its panel).
- [Windows Labs Behind the Pro Plan](windows-labs-premium-tier.md)
- [Hosted Windows Labs for Ineligible Machines](hosted-windows-labs.md)

## Implementation Status

Not started (roadmap).
