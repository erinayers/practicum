# Subnet Conflict Detection and Resolution

## User Story

As a student or instructor about to start a lab,
I want Practicum to tell me before starting when one of the lab's subnets is already used by a Docker network on my machine, and to fix it for me,
so that a lab that looks fine never fails at the last step with Docker's "Pool overlaps with other one on this address space".

## Why This Matters

Docker refuses to create a bridge network whose subnet overlaps an existing one. Every Practicum lab creates its own networks (named per lab id), so two labs that share a subnet cannot coexist — and this happens constantly in practice: the Quick Start template and the bundled `ubuntu-quickstart.json` sample both use `10.50.0.0/24`; importing the same lab file twice gives the same subnets; and because labs live in memory only, an earlier session's networks and containers outlive the API and become invisible **leftovers** that still hold the address space. Until this story, the first sign of any of these was a failed Start (observed on Windows, 2026-10-23, Tigre/06 #13), with advice the user could only act on in a terminal.

## User Flow

1. The pre-start readiness gate (and the import-and-launch flow before it) asks the API to check the lab's subnets against every network on the Docker host.
2. Each overlapping subnet is listed with who owns the address space:
   - another lab in the user's list (by name and status),
   - a leftover Practicum network from an earlier session (with how many containers are still attached), or
   - a Docker network not created by Practicum.
3. Each conflict offers a one-click fix appropriate to its owner: **Remove leftover** (after an in-app confirmation), **Reset '<that lab>'** (after an in-app confirmation), and/or **Use <free subnet>** (moves the network and remaps its interface addresses, keeping each host offset).
4. Start stays disabled until every conflict is cleared; applying a fix re-checks and re-renders from the API's fresh answer.
5. When Docker itself cannot be queried, the gate says so and keeps Start disabled rather than guessing.

## Functional Requirements

- Within a single lab, overlapping subnets are a validation error.
- `GET /labs/{lab_id}/networks` reports, per conflicting lab network: the owner network's name and subnet, the owner's Practicum lab id (from the `practicum.lab_id` label) and — when that lab is still known — its name and status, the number of attached containers, and a recommended free subnet of the same size drawn from `10.90.0.0/16` that avoids every Docker network and every other known lab.
- A lab's own networks (same lab id) are never reported as conflicts, so a stopped lab can be started again.
- `POST /labs/{lab_id}/networks/apply-recommendation` moves a network to its recommended subnet and remaps the interface addresses on it; the stored lab and its export reflect the change.
- `POST /labs/{lab_id}/networks/remove-leftover` force-removes the attached containers and the network, but only for Practicum-labelled networks whose lab is unknown to the API and which actually conflict with the given lab; networks of listed labs (use reset) and foreign Docker networks are refused with a clear 409.
- The desktop gate renders the conflicts and the fixes; the import flow treats a subnet conflict (or an unanswerable check) exactly like a port conflict and hands over to the gate.
- Destructive fixes (remove leftover, reset another lab) use the shared in-app confirmation component.

## Acceptance Criteria

- A lab whose subnet overlaps an existing Docker network is reported by `GET /labs/{lab_id}/networks` with the owner identified and a recommended subnet, before any Start is attempted.
- The pre-start gate blocks Start while subnet conflicts exist and shows the owner of each.
- Removing a leftover from the gate deletes that network and its containers and clears the conflict; the lab definition is unchanged.
- Resetting the owning lab from the gate clears the conflict.
- Applying the recommended subnet moves the network and its addresses, the topology shown in the gate updates, and the user is told the manual may still mention the old addresses.
- Importing a lab with a subnet conflict stops at the gate instead of failing at start.
- Overlapping subnets within one lab are rejected at validation.

## Edge Cases

- Docker is not running when the check runs — the result carries an `error`, the gate shows it, and Start stays disabled.
- The leftover disappears between the check and the removal — the removal is a no-op and the fresh check is returned.
- The recommended subnet is itself taken by the time it is applied — the apply re-runs the check first and reports 409 if no recommendation remains.
- A lab subnet larger than the recommendation pool (`/16` or wider) gets no recommendation; the owner-based fixes still apply.
- Moving a subnet cannot keep the instructor's manual text in sync; the gate warns about this.

## Implementation Notes

- Implemented 2026-10-23. Core: `src/practicum/networks.py` (`find_subnet_conflicts`, `recommend_subnet`, `move_subnet`), `DockerRuntime.list_networks()` / `remove_network()` in `runtime.py`, `LabService.check_networks` / `apply_subnet_recommendation` / `remove_leftover_network`, three routes in `main.py`, models `DockerNetworkInfo`, `SubnetConflict`, `NetworkCheckResult`. Desktop: `ApiClient.check_networks` / `apply_subnet_recommendation` / `remove_leftover_network` / `reset_lab`, the "Network Conflicts" section of `PreStartGateDialog`, and the combined "Checking host ports and networks…" stage in `ImportLabDialog`.
- Recommendations come from `10.90.0.0/16` (D-17/D-24) so they never collide with the hand-authored `10.0.x` / `10.50.x` examples.
- The runtime's older `_remove_empty_practicum_networks_with_subnet` (auto-removes *empty* leftovers with the exact same subnet at start) is kept; this story covers the cases it cannot: leftovers with containers, partial overlaps, listed labs, and foreign networks.
- Proper fixes for the root causes remain separate: persistence/reconciliation of labs across API restarts (Tigre/11 S-1) and quick-start subnets allocated from the pool (Tigre/06 #1).
