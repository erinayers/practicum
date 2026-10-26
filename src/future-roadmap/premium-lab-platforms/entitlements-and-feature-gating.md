# Entitlements and Feature Gating

## User Story

As the Practicum maintainer,
I want a small, honest entitlement mechanism in the desktop app,
so that premium capabilities (Windows and macOS labs) can be switched on for paying users
without weakening, obscuring or instrumenting the open-source core.

## Why This Matters

The app is open source and runs offline. Gating must therefore be simple to reason about,
impossible to confuse with a bug ("why is the Windows template greyed out?"), and must not turn
the free app into a nag screen or a telemetry client.

## Functional Requirements

- A single place in the desktop app answers "is feature X enabled?" (a feature catalogue with
  `free` / `pro` tiers), read by the Create screen, designer, import flow and gate.
- Entitlement comes from a locally stored licence (key or signed token) entered in a Settings /
  Account panel; validation works offline after activation, with a generous grace period, and
  never requires an account to use free features.
- A gated feature is shown, not hidden: the control is visible with a "Pro" chip and a short,
  plain explanation plus a link to the plan page. Nothing else in the UI changes.
- Importing or opening a lab that uses a gated platform always succeeds at the spec level
  (validate, preview, export, edit, delete); only *starting* it is gated, with the same plain
  explanation in the pre-start gate.
- The open-source build behaves identically with no licence present: no time bombs, no
  reduced functionality elsewhere, no phone-home. Any licence check that needs the network is
  opt-in and explained.
- A build-time switch lets a self-hosting institution compile the app with the premium features
  enabled for its own users (the code stays in the repository).

## Acceptance Criteria

- With no licence, every Linux feature works exactly as today; Windows/macOS controls carry a
  Pro chip and explanation instead of disappearing.
- Entering a valid licence enables the gated features without restarting the app; removing it
  disables them again, leaving existing labs intact in the list.
- A lab that uses a gated platform can be imported, previewed, edited, exported and deleted
  without a licence; Start is refused with the reason.
- The app works fully offline once activated; grace-period expiry degrades only the gated
  features.

## Paywall Guidance

This is the mechanism the rest of the epic depends on. Keep it boring: one feature catalogue,
one licence store, one explanation component reused everywhere.

## Dependencies

- [Open Core Boundary](../open-source-core-sustainability/open-core-boundary.md)
- The desktop's existing readiness/explanation patterns (Windows readiness panel, gate banners)
  are the natural place to surface the "Pro" state.

## Implementation Status

Not started (roadmap).
