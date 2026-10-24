# Lab Lifecycle Controls

## User Story

As a student or instructor running a lab,
I want clear, separate controls for restarting, stopping, and resetting it,
so that I don't accidentally wipe my work when I only meant to restart a container.

## Why This Matters

`student-reset-lab.md` already defines Reset at the product level: it is more destructive than Stop and must be visually distinct and confirmed. The desktop app currently has no Stop, Restart, or Reset controls in its running-lab view at all — only a Start button exists today. This story defines the toolbar that exposes all four lifecycle actions (Start is already covered elsewhere) consistently, and makes sure Reset cannot be triggered by the same casual click as Stop or Restart.

## User Flow

1. While a lab is running, the toolbar shows Restart, Stop, and Reset actions alongside Instructions.
2. Restart and Stop behave as routine, low-risk actions and do not require confirmation.
3. Reset requires an in-app confirmation dialog (per `windows-desktop-in-app-dialogs.md`) that explains it will remove all runtime containers and lab-created resources, returning the lab to its original instructor-provided state.
4. On confirming Reset, the app calls `POST /labs/{lab_id}/reset`, shows a progress state, and returns the lab to its pre-start (Stopped/Defined) state rather than leaving it running.
5. Reset does not touch the student's locally-tracked manual progress; that remains a separate, explicitly different action available from the manual flyout's existing "Reset Progress" control.

## Functional Requirements

- Reset is visually distinct from Stop and Restart (e.g., styled as a destructive action), not just another item in the same button row.
- Reset always requires confirmation; Stop and Restart do not.
- The confirmation text makes clear that Reset is more destructive than Stop and cannot be undone.
- Starting, restarting, and resetting all show the same kind of in-app progress state used elsewhere (see `windows-desktop-prestart-lab-gate.md` and `windows-desktop-import-lab-file.md`) rather than freezing the UI.
- Reset never clears locally-stored manual progress; only the existing "Reset Progress" control in the manual flyout does that.

## Acceptance Criteria

- The running-lab view exposes Restart, Stop, and Reset as distinct actions.
- Selecting Reset always shows an in-app confirmation before any destructive call is made.
- Confirming Reset calls the lab reset endpoint and the UI reflects the lab's returned-to-clean state afterward.
- Canceling the Reset confirmation leaves the lab running and unchanged.
- Manual progress survives a Reset; it is only cleared by the manual flyout's own "Reset Progress" action.

## Edge Cases

- Reset is requested while a Start or Stop call is already in flight — the UI should prevent overlapping lifecycle calls on the same lab.
- Reset partially fails (some containers removed, others not) — surface the partial failure rather than silently reporting success.
- The lab is already stopped when Reset is requested — Reset should still be offered and should still succeed, per the existing story's edge cases.
- Docker resources for the lab were changed outside of Practicum — Reset should not assume its own bookkeeping is authoritative and should re-check actual state.

## Implementation Notes

- Backend already exists: `POST /labs/{lab_id}/reset` (see `student-reset-lab.md`, already done). This story is desktop UI only: exposing Stop/Restart/Reset in the toolbar and wiring Reset through the shared in-app confirmation component.
- Reference design: the running-lab toolbar in the clickable mockup (`practicum-mockups.html`, `screen-running`) currently only shows Restart/Stop placeholders — Reset and its confirmation still need to be added there as well as in the real app.

## Implementation Status

Done 2026-10-24 (Session 5) in `desktop/src/practicum_desktop/running_view.py` (`RunningLabView`).

- Toolbar while running: **↻ Restart**, **■ Stop lab** (both unconfirmed) and **Reset** (red `kind="danger"`, always confirmed through `dialogs.confirm(destructive=True)` with text that says it is more destructive than Stop and cannot be undone); **📖 Instructions** toggles the flyout. When the lab is stopped/ready/error the toolbar shows **▶ Start lab** (which routes through `PreStartGateDialog`, D-4) plus Reset — Reset is offered whatever the state, as the story's edge case asks.
- While any lifecycle call is in flight every lifecycle button is disabled (`_busy`), the feedback banner shows "Stopping lab…"/"Restarting lab…"/"Resetting lab…", and the view polls `GET /status` every second so the same progress state (per-node `StartProgressPanel`) appears for Restart as for Start. A 409 from the API (another action already running) is explained as a warning, not a failure.
- After a confirmed Reset the badge returns to **Ready**, the message says the lab is back to its original state and that instruction progress is kept; `ManualFlyout`'s QSettings progress is untouched (test `test_reset_keeps_manual_progress`). Cancelling the confirmation changes nothing (test `test_reset_always_asks_first_and_cancel_changes_nothing`).
- Backend enablers built alongside: `runtime-lab-restart.md` (start after stop via `docker start`, `POST /restart`, action lock) so Restart does not hit Tigre/06 #2.
- Tests: `desktop/tests/test_running_view.py` (19). Verified end-to-end with the fake `docker` CLI (stop → start via gate → reset); Windows run pending.
