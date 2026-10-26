# Instructor Authoring for Premium Platforms

## User Story

As an instructor,
I want to author, validate, preview and export a Windows or macOS lab even when my own machine
cannot run it (or my plan does not include running it),
so that I can prepare course material on any computer and let the hosted runtime or students'
eligible machines do the running.

## Why This Matters

Authoring is the open-source core; running a premium guest is the paid part. Keeping that line
clear avoids the worst outcome of a paywall: an instructor who cannot even open the lab they
wrote last term.

## Functional Requirements

- The designer and quick-start screens can create and edit Windows (and later macOS) labs on a
  free install: the template/presets are available for *authoring*, with a clear note that
  starting requires an eligible machine and the Pro plan (or a hosted run).
- Validate, preview, export, import, duplicate and delete work regardless of plan or platform.
- The pre-start gate is the single place that explains why Start is unavailable (edition, plan,
  hardware) and what the options are, reusing the readiness panel's wording.
- Export notes the platform requirement in the lab's description or a spec field so students
  importing it see it before they try to start.
- A "test run" for instructors on the hosted runtime (short session) so a lab can be verified
  without owning eligible hardware.

## Acceptance Criteria

- On a Windows Home PC without a plan, an instructor can build a Windows quick start, add
  tools and steps, export it, and re-import it; only Start is refused, with the explanation.
- Students importing that export see the platform requirement before starting.
- A licensed student on an eligible PC runs the exported lab unchanged.

## Paywall Guidance

Free. Authoring must never be gated; it is what makes the paid runtime worth buying.

## Dependencies

- [Entitlements and Feature Gating](entitlements-and-feature-gating.md)
- [Windows Labs Behind the Pro Plan](windows-labs-premium-tier.md),
  [macOS Labs Behind the Pro Plan](macos-labs-premium-tier.md)
- Phase 8 `designer-windows-quick-start` (the template stays; only Start is gated).

## Implementation Status

Not started (roadmap).
