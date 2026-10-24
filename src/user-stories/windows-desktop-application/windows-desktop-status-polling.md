# Live Status Polling in the Running View

## User Story

As a student working in a lab,
I want the app to keep showing the real state of my containers,
so that a container that died, a start that is still pulling images, or a change made outside Practicum is reflected without me guessing.

## Why This Matters

Until this story the desktop never called `GET /labs/{lab_id}/status` after an action; the badge showed whatever the lab list said when the screen opened (Tigre/11 finding #8, proposal S-12). `runtime-image-pull-progress.md` also needs a consumer for its per-node progress.

## User Flow

1. The running view opens and reads the lab's status; the badge, the Lab nodes table and the "N containers running" status bar follow it.
2. While the lab is starting or stopping (or an action is in flight) the view polls every second and shows the per-node start progress in place of the browser pane; otherwise it polls every 5 seconds.
3. Leaving the screen (or hiding the window) pauses polling; coming back resumes it.
4. A lab that ends in `error` shows the reason from the API (`last_error`) and offers Start and Reset.

## Functional Requirements

- Polling uses the existing `GET /labs/{lab_id}/status` (D-11) and never blocks the UI thread.
- The embedded view is told about running/not-running transitions only when they change, so it does not reload the page on every tick.
- Status changes that happen outside a lifecycle action still update the badge and notify the dashboard cache.

## Acceptance Criteria

- A starting lab shows the per-node progress panel and fast polling; once running, the browser pane returns and polling slows down.
- Stopping the containers outside Practicum flips the badge on the next tick.
- Hiding the view stops the poll timer.
- An `error` status surfaces `last_error` in the view.

## Edge Cases

- The API is unreachable mid-session — the status request fails; the nodes panel shows the detail and the last known badge stays.
- The user leaves while an action is in flight — the action still completes server-side; the dashboard shows the final state on its next refresh.

## Implementation Notes

- `desktop/src/practicum_desktop/running_view.py` (`_poll_timer`, `FAST_POLL_MS`, `SLOW_POLL_MS`, `_schedule_polling`, `_on_status_loaded`). Absorbs the `runtime-api-status` AC "Desktop UI refreshes status".

## Implementation Status

Done 2026-10-24 (Session 5). Tests: `desktop/tests/test_running_view.py` (`test_starting_lab_shows_real_progress_panel`, `test_error_status_from_polling_surfaces_last_error`, `test_polling_stops_when_hidden`).
