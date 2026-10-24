# Delete a Lab Through the API

## User Story

As a returning user cleaning up,
I want to delete a lab I no longer need,
so that my labs dashboard only shows what I still use and no containers or networks are left behind.

## Why This Matters

`windows-desktop-labs-dashboard.md` offers Delete on every stopped or ready lab card, but the API had no way to forget a lab (Tigre/11 C5, proposal S-4). Deleting also has to take the lab's Docker resources with it, otherwise every deleted lab would become exactly the kind of invisible leftover that `runtime-subnet-conflicts.md` exists to clean up.

## User Flow

1. The user chooses Delete on a lab card and confirms in the in-app dialog.
2. The API removes the lab's containers and networks (if it ever started) and forgets the lab.
3. The card disappears; when it was the last lab, the app returns to the welcome screen.
4. If the Docker resources cannot be removed (Docker down), the lab is kept and the user is told why, so nothing is orphaned silently.

## Functional Requirements

- `DELETE /labs/{lab_id}` returns 204 on success and 404 for an unknown lab.
- A lab whose status is `defined` (never started) is removed without touching Docker.
- Any other status triggers the runtime reset first; a reset failure keeps the lab, marks it `error` with `last_error`, and answers 409 with the reason.
- Deleting a `starting`/`stopping` lab is refused with 409 (action lock, see `runtime-lab-restart.md`).
- Deleting never touches files the user exported or imported.
- The desktop client exposes `ApiClient.delete_lab` (`DeleteResult`), treating a 404 as already gone.

## Acceptance Criteria

- Deleting a running lab removes its Docker resources and the lab; `GET /labs` no longer lists it.
- Deleting a never-started lab succeeds even when Docker is unavailable.
- When cleanup fails, the lab is still listed and the 409 detail explains what went wrong.
- Deleting an unknown lab returns 404.

## Edge Cases

- The lab's containers were already removed outside Practicum — reset tolerates missing resources and the delete proceeds.
- Two deletes race — the second one sees 404 and the desktop treats that as success.

## Implementation Notes

- Core: `LabService.delete` + `LabDeleteError` (`src/practicum/service.py`), route in `src/practicum/main.py`. Desktop: `ApiClient.delete_lab` and the dashboard's Delete action (`main_window.py::_on_delete_requested`, confirmed through `dialogs.confirm(destructive=True)`).
- Decision D-25 (Tigre/09): delete resets Docker resources first rather than refusing.

## Implementation Status

Done 2026-10-24 (Session 5). Tests: `tests/test_api.py` (`test_delete_*`), `tests/test_service.py`, `desktop/tests/test_api_client.py` (`test_delete_lab_*`), `desktop/tests/test_main_window.py` (delete flow incl. cancel and failure). Verified end-to-end with the fake `docker` CLI; Windows run pending.

## Update 2026-10-24 (user report: containers still in Docker after deleting a lab)

- `delete` now always runs the runtime reset for the lab's Docker names, whatever status the API believes the lab has (only a never-started lab whose cleanup fails because Docker is down is still removed from the list).
- **Leftover sweep**: because labs live in memory only, every Practicum container/network that exists when the API *starts* belongs to a previous session and can never be used again — the API now removes them at startup (`lifespan`) and offers `POST /docker/sweep-leftovers` to do it on demand (D-40). Only resources carrying the `practicum.lab_id` label of an unknown lab are touched; other Docker containers/networks are never removed. Tests: `test_delete_always_sweeps_the_labs_docker_names`, `test_sweep_*`, `test_api_startup_sweeps_leftovers`, `test_docker_runtime_lists_practicum_containers_with_lab_ids`. Verified with the fake docker CLI (seeded leftover removed at startup; unrelated container kept; delete leaves nothing behind).
