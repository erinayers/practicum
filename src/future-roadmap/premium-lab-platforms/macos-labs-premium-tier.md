# macOS Labs Behind the Pro Plan

## User Story

As an instructor teaching macOS administration, Swift/Xcode tooling or Apple-platform security,
I want a macOS Quick Start — a macOS guest with a Terminal, and optionally a desktop — that
students on Apple-silicon Macs can run from Practicum,
so that macOS topics get the same reproducible, importable lab experience as Linux ones.

## Why This Matters

There are no macOS containers in Docker; a macOS lab is a virtual machine. Apple's software
licence permits macOS guests only on Apple hardware (at most two at a time), and the practical
route is Apple's Virtualization framework on Apple-silicon Macs (as used by Tart, UTM and
similar). That rules out Windows and Linux students and the free plan's "any laptop" promise,
so — like Windows labs — it is a paid, clearly explained capability.

## Functional Requirements

- A macOS guest runtime on Apple-silicon macOS hosts: create a VM from a pinned macOS IPSW /
  image, attach it to the lab's network with a fixed address, publish ports, keep it alive,
  stop / start / reset; report the same per-node progress steps (image download is large).
- Spec: `os: macos` on a node with `shell: zsh | bash`, the same validation pattern as Windows
  (one OS per lab; macOS nodes refuse Linux-only resources). Tool installation through Homebrew
  in an init script, mirroring the Chocolatey design (status marker, profile banner, readable
  package list in the node's environment).
- Desktop: a **macOS** quick-start template (Terminal sandbox; a screen-shared desktop later),
  a readiness check (Apple silicon, macOS version, free disk, the two-VM limit, the plan),
  **Open Terminal** (SSH into the guest), screenshots from the embedded view when a desktop is
  shared, the usual gate / progress / lifecycle / results.
- Gating as for Windows: visible with a "Pro" chip and an explanation on a free install; the
  spec remains importable, previewable and exportable everywhere.
- Hosted macOS runs (Apple-silicon cloud hosts) for students without a suitable Mac, through the
  hosted runtime story.

## Acceptance Criteria

- On a licensed Apple-silicon Mac a macOS quick start creates a one-node lab with a pinned
  image, starts it with a Terminal available, follows the existing gate / progress / lifecycle
  flows and exports/imports with its `os`/`shell`.
- On any other machine the template is visible, marked Pro, and explains hardware, licence and
  hosted options; nothing else changes.
- Apple's two-VM limit and licence terms are respected and stated.
- Windows and Linux behaviour is unchanged.

## Paywall Guidance

Paid, for the same reason as Windows labs: the platform requirement (Apple hardware, licence
terms) excludes the free plan's audience, and the hosted alternative costs compute.

## Dependencies

- [macOS Desktop Application](macos-desktop-application.md) (free prerequisite).
- [Entitlements and Feature Gating](entitlements-and-feature-gating.md)
- [Hosted Windows Labs for Ineligible Machines](hosted-windows-labs.md) (generalised to macOS).
- The Phase 8 patterns it mirrors: readiness check, pinned image matrix, declared `os`/`shell`,
  init script with status marker, per-OS shell launcher.

## Implementation Status

Not started (roadmap).
