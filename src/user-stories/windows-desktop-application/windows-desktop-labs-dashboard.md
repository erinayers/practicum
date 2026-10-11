# Labs Dashboard

## User Story

As a returning instructor or student,
I want to see all my existing labs when I open Practicum,
so that I can resume, manage, or clean up my work without recreating anything.

## Why This Matters

The desktop app currently has no home screen for returning users — it only offers "create" or "import" actions, with no way to see labs that already exist. `GET /labs` already returns the local lab list, but nothing in the UI surfaces it as a first-class destination. Without this, every session feels like a first run, and users have no way to resume, rename, or delete labs they already built or imported.

## User Flow

1. The user launches Practicum.
2. If one or more labs already exist locally, the app shows the Labs Dashboard instead of the zero-state welcome screen.
3. Each lab appears as a card showing its name, origin (imported file, quick start template, or custom build), and current status (Running, Stopped, or Draft).
4. The user chooses an action appropriate to that lab's status:
   - **Running** → Open (returns directly to the lab's running view).
   - **Stopped** → Start (goes through the pre-start readiness gate, see `windows-desktop-prestart-lab-gate.md`).
   - **Draft** (saved but never successfully started/validated) → Edit (reopens the lab in Designer Mode) or Delete.
5. The user can also delete any lab from its card, with an in-app confirmation (see `windows-desktop-in-app-dialogs.md`).
6. The user can start a brand-new lab (Create New Lab) or import one (see `windows-desktop-import-lab-file.md`) from the same screen.

## Functional Requirements

- The dashboard lists every lab known to `GET /labs`, refreshed when the screen is shown.
- Each card shows the lab's name, a short origin/meta line, and a status badge (Running / Stopped / Draft).
- Running labs offer an "Open" action that returns to that lab's running view without re-running Start.
- Stopped and Draft labs offer actions appropriate to their state (Start vs. Edit); only Stopped/Draft labs offer Delete.
- "Create New Lab" and "Import Existing Lab" remain reachable from the dashboard, not only from the zero-state screen.
- The zero-state welcome screen (no labs yet) remains the first-launch experience; the dashboard replaces it once at least one lab exists.

## Acceptance Criteria

- A user with zero labs sees the existing welcome screen with Create/Import actions.
- A user with one or more labs sees a dashboard listing each lab with its correct status.
- Opening a Running lab returns to its running view without issuing a new Start call.
- Starting a Stopped lab routes through the pre-start readiness gate before any containers are created.
- Deleting a lab requires an in-app confirmation and removes it from the list on confirm.
- Canceling a delete confirmation leaves the lab list unchanged.

## Edge Cases

- A lab is Running in the API but its containers died outside of Practicum (status is stale) — reopening should re-check status rather than trusting the cached badge blindly.
- A lab was never successfully validated (Draft) and has no preview data to show if the user tries to Start it directly — only Edit/Delete should be offered until it validates.
- Many labs accumulate over time — the list should scroll rather than overflow the window.
- The API is unreachable when the dashboard would load — fall back to the existing readiness/blocked state from `windows-desktop-launch.md` instead of showing an empty dashboard.

## Implementation Notes

- Backed entirely by existing, already-implemented endpoints (`GET /labs`, `GET /labs/{lab_id}/status`); this story is desktop UI only.
- Reference design: the "Your Labs" screen in the clickable mockup (`practicum-mockups.html`, `screen-dashboard`).
- Delete and any other destructive action must use the in-app confirmation modal described in `windows-desktop-in-app-dialogs.md`, not a native OS dialog.
