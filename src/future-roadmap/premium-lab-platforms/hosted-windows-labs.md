# Hosted Windows Labs for Ineligible Machines

## User Story

As a student on a Windows Home laptop (or a Mac, or a Linux PC),
I want to run my course's Windows lab on a hosted runtime from inside Practicum,
so that the instructor's Windows lab works for the whole class regardless of each student's
machine.

## Why This Matters

Gating Windows labs to eligible PCs solves the false promise but not the classroom problem: a
class is mixed. The hosted runtime is the only way a Windows lab can be a course-wide
assignment. It is also the "Managed Runtime Later" item of the roadmap, made concrete.

## Functional Requirements

- A hosted runtime service that starts the lab's Windows containers (or VMs) from the same lab
  spec, with the same pre-start checks, progress reporting and lifecycle (start / stop / restart
  / reset) exposed through the existing API shapes, so the desktop's running view needs no new
  concepts.
- In the desktop, a lab whose platform the local machine cannot run offers **Run hosted** where
  **Start** would be, with the plan/quota state and an estimate of session time; the running
  view shows the hosted session the same way (embedded view for published ports over a secure
  tunnel, Open PowerShell through a browser terminal or a relayed `docker exec`).
- Session limits, idle shutdown and quota per plan; clear warnings before a session ends; the
  student's manual progress, screenshots and results stay local and work unchanged.
- Instructors can enable hosted runs for a course so students do not each need a plan
  (classroom plan integration).
- Privacy: the hosted service receives the lab spec and the session's container I/O, nothing
  from the student's machine beyond what they type.

## Acceptance Criteria

- A student on Windows Home can start, use (PowerShell and any published web port), stop and
  reset a Windows lab from Practicum without local Docker changes.
- The pre-start gate, progress panel, running view, manual flyout, screenshots and results
  export behave as for a local lab.
- Quota and session-end behaviour are visible in advance and on expiry.
- The hosted runtime is additive: the same lab still runs locally on an eligible PC with a
  licence.

## Paywall Guidance

Paid by nature (it costs compute); sold per student, per course, or as institution capacity.

## Dependencies

- [Entitlements and Feature Gating](entitlements-and-feature-gating.md)
- [Windows Labs Behind the Pro Plan](windows-labs-premium-tier.md)
- Hosted Collaboration and Classrooms epic (course-level enablement).
- Core API: a `LabRuntime` implementation that targets the hosted service (the Protocol already
  isolates Docker), plus authentication.

## Implementation Status

Not started (roadmap).
