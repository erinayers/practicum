# Pre-Start Readiness Gate

## User Story

As an instructor or student about to start a lab,
I want to see what will run on my machine and resolve any port conflicts first,
so that I never start a lab blind or have it fail midway through launch.

## Why This Matters

Two pieces of this already exist at the API level: `GET /labs/{lab_id}/preview` (name, description, required images, estimated resources, read-only topology, manual) from `student-preview-imported-lab.md`, and `GET /labs/{lab_id}/ports` + `POST /labs/{lab_id}/ports/apply-recommendation` from `windows-desktop-port-conflict-ui.md`. Both are marked done at the API/UI-table level, but neither is wired into a single, mandatory screen that gates every Start action, regardless of where that Start was triggered from (dashboard resume, Designer "Save Lab", or import). This story defines that unified screen.

## User Flow

1. The user triggers Start from any entry point: the Labs Dashboard, the Designer's "Save Lab" action, or (conditionally — see Implementation Notes) importing a lab file.
2. The app calls preview and port-check for that lab and shows a single screen with:
   - Lab name, description, author/version.
   - Required Docker images, each flagged as already local or needing a download (with size, when known).
   - Estimated CPU and memory.
   - The topology in read-only form.
   - A collapsible preview of the lab manual's step count.
   - A port-conflicts panel, if any exist.
3. If port conflicts exist, "Start Lab" is disabled and a banner explains how many conflicts remain.
4. The user applies a recommended port for each conflict; the panel updates in place.
5. Once no conflicts remain, "Start Lab" enables, and selecting it begins the normal start sequence (see `windows-desktop-lab-lifecycle-controls.md`).
6. The user can cancel out of this screen back to where they came from without starting anything.

## Functional Requirements

- This screen is the single place port conflicts are shown and resolved before Start, replacing any flow that would start a lab without checking first.
- Images already present locally are visually distinguished from images that will be pulled.
- The topology view here is read-only — no editing controls, even if reached from the Designer.
- "Start Lab" is disabled while any unresolved conflict remains and re-enables automatically once all are resolved.
- The manual preview is accessible from this screen without requiring the lab to be running first.

## Acceptance Criteria

- The screen shows lab name, description, required images, estimated resources, and read-only topology.
- Port conflicts block Start until resolved, and applying a recommendation re-checks and clears that conflict.
- A lab with zero conflicts shows a clear "ready to start" state and an immediately-enabled Start button.
- Canceling this screen does not start, modify, or delete the lab.
- The manual's step count/preview is visible from this screen.

## Edge Cases

- A required image needs to be pulled and that pull is large or slow — the subsequent start sequence should communicate progress rather than appearing frozen (see `windows-desktop-lab-lifecycle-controls.md`).
- A port becomes unavailable again after a recommendation was applied but before Start is pressed — re-verify on Start, not only when the recommendation was first applied.
- The lab has no manual — the manual preview section should say so rather than showing an empty list.
- Resource estimates are missing from the spec — show "unknown" rather than blank or zero.

## Implementation Notes

- Builds on existing, already-implemented endpoints: `GET /labs/{lab_id}/preview`, `GET /labs/{lab_id}/ports`, `POST /labs/{lab_id}/ports/apply-recommendation`. No new API work is expected; this is a desktop UI consolidation.
- Reference design: `screen-preview` in the clickable mockup (`practicum-mockups.html`), including both the "has conflicts" and "zero conflicts" states.
- Whether a freshly-imported lab always passes through this screen, or only when it has conflicts, is a product decision — see `windows-desktop-import-lab-file.md` for the proposed resolution.
