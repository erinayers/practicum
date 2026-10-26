# Define Open Core Boundary

## User Story

As the Practicum maintainer,  
I want a clear open-core boundary,  
so that the product can monetize without weakening the free local learning experience.

## Recommendation

Keep the complete local loop open source:

- Create a lab spec
- Validate a lab spec
- Export a lab spec
- Import a lab spec
- Run a lab locally with Docker
- Read the lab manual
- Stop and reset the lab

## Paywall Guidance

Do not paywall core local functionality. Paywall features that require hosted infrastructure, institutional coordination, commercial distribution, or advanced productivity.

## Acceptance Criteria

- The project documents which features are guaranteed open source.
- Paid features are documented separately from core features.
- Users can run local labs without marketplace accounts.
- Public specs remain importable without platform lock-in.

## Addendum 2026-10-25 — platform carve-out

"Run a lab locally with Docker" in the open core means **Linux containers**, the kind Docker
Desktop runs on every supported Windows edition (WSL 2) and on macOS. Labs whose guest is
Windows or macOS are carved out into the paid tier — not to withhold value, but because the
platforms themselves exclude the free audience (Windows containers need Windows
Pro/Enterprise/Education; macOS guests need Apple hardware under Apple's licence). The spec
fields that describe such labs, and authoring/validating/importing/exporting them, remain free.
Details: [Premium Lab Platforms](../premium-lab-platforms/README.md).

## Risks

- Paywalling too early could reduce trust.
- Paywalling local basics could weaken adoption.
- Unclear boundaries could confuse contributors.
