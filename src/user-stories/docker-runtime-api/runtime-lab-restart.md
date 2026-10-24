# Restart a Lab and Start After Stop

## User Story

As a student using a lab,
I want Restart to work as one routine action and a stopped lab to start again without failing,
so that the lifecycle controls in the desktop app behave predictably.

## Why This Matters

`windows-desktop-lab-lifecycle-controls.md` exposes Restart, Stop and Reset, but until this story the runtime had no restart semantics at all, and a stopped lab could not be started again: Stop left the containers in place (`docker stop`) while Start always ran `docker run --name <same name>`, which Docker rejects with a name conflict, so the first Start after a Stop always failed and wiped the lab (Tigre/06 #2). Two lifecycle calls could also overlap on the same lab, because nothing guarded the `starting`/`stopping` transitions (Tigre/11 S-6).

## User Flow

1. A student stops a running lab; its containers are kept (stopped), its networks stay.
2. The student starts it again; the runtime restarts the existing containers, keeping their filesystems and addresses, instead of recreating them.
3. The student chooses Restart; the API stops and starts the lab as one action and reports a single result.
4. While a start or stop is in flight, any other lifecycle call on that lab is refused with a clear message instead of being run concurrently.

## Functional Requirements

- `DockerRuntime.start` checks whether each node's container already exists and uses `docker start <name>` for it; only missing containers are created with `docker run` and connected to their extra networks.
- `POST /labs/{lab_id}/restart` performs stop + start at the service level and returns one `RuntimeActionResult`; a lab that is not running is simply started.
- Lifecycle calls (`start`, `stop`, `restart`, `reset`, `delete`) on a lab whose status is `starting` or `stopping` return HTTP 409 with a message naming the lab and the state it is in (action lock).
- Teardown tolerates every wording Docker uses for an already-missing resource (`No such container`, `network <x> not found`, `No such object`), so a Reset of a lab whose resources are already gone still succeeds.
- The desktop client exposes `stop_lab`, `restart_lab` and `reset_lab` with the long lifecycle timeout, and reports a 409 as `busy` so the UI can explain rather than fail.

## Acceptance Criteria

- Starting a `stopped` lab reuses its existing containers (`docker start`) and ends in `running`.
- `POST /labs/{lab_id}/restart` on a running lab calls stop then start and ends in `running`; on a stopped or defined lab it just starts it.
- A lifecycle call made while the lab is `starting` or `stopping` is rejected with 409 and leaves the lab's status unchanged.
- Resetting a lab whose networks were already removed outside Practicum succeeds.

## Edge Cases

- The stopped container was deleted outside Practicum — the existence check finds nothing and the node is recreated with `docker run`.
- Stop succeeds but the following Start fails during Restart — the result carries the start failure and the lab ends in `error` with `last_error` set.
- The API process is restarted while a lab is `starting` — the in-memory lock is gone with the process; the Docker resources stay (persistence is S-1, out of scope).

## Implementation Notes

- Core: `src/practicum/runtime.py` (`_container_state`, `_is_missing_error`), `src/practicum/service.py` (`restart`, `_begin_transition`, `LabBusyError`, `BUSY_STATUSES`), `src/practicum/main.py` (`POST /labs/{lab_id}/restart`, 409 mapping). Desktop: `ApiClient._lifecycle_call` (shared by start/stop/restart/reset) in `desktop/src/practicum_desktop/api_client.py`.
- Resolves Tigre/11 C6 and Tigre/06 #2; promoted from proposal S-6 in `Tigre/11-user-story-review.md`.

## Implementation Status

Done 2026-10-24 (Session 5). Core tests in `tests/test_api.py` (`test_restart_*`, `test_lifecycle_calls_are_rejected_while_lab_is_busy`), `tests/test_runtime.py` (`test_docker_runtime_restarts_existing_containers_instead_of_recreating`, `..._reset_tolerates_dockers_network_not_found_wording`), `tests/test_service.py`. Verified end-to-end against a stateful fake `docker` CLI (start → stop → start → restart → reset → start); not yet run against Docker Desktop on Windows.
