# Reconcile Saved Labs with Docker on Startup

As a returning user, I want Practicum to compare saved labs with Docker after startup so that the dashboard reflects the resources that actually exist.

## Acceptance criteria

- On API startup, each saved lab's containers and networks are inspected using the existing Practicum labels and deterministic resource names.
- A lab is reported as running only when its expected runtime resources are running; stopped, missing, partial, and failed resources produce a safe, actionable status.
- The service does not automatically start, reset, or delete lab resources during reconciliation.
- Resources belonging to saved labs are not treated as unknown leftovers by the startup sweep; unknown-lab Practicum resources continue to follow the existing cleanup policy.
- Docker being unavailable does not delete saved lab records; reconciliation reports that runtime state could not be confirmed and can be retried when Docker becomes available.
- Tests cover running, stopped, missing, partial, and unavailable-Docker cases.

## Notes

SQLite stores lab definitions and local metadata. Docker remains the authority for container/network runtime state; persisted status is only a hint to reconcile.
