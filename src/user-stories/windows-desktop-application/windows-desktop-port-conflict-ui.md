# Port Conflict UI

## User Story

As a Windows app user,  
I want port conflicts shown clearly in the interface,  
so that I understand why a browser-accessible lab cannot start and how to fix it.

## Why This Matters

Port conflicts are common on developer and student machines. A clear UI should explain whether a port is used by Practicum, another lab, Docker, or another local process, then offer a recommended replacement.

## User Flow

1. The user imports or edits a lab with host port mappings.
2. The app checks port availability.
3. Conflicting ports appear with clear warning states.
4. The app shows recommended replacement ports.
5. The user applies a recommendation.
6. The app revalidates the lab.

## Functional Requirements

- Port fields show available/unavailable state.
- Conflicts show the affected host port and node.
- The app explains whether the port is reserved by Practicum when known.
- The app shows recommended replacement ports.
- Start/export actions are disabled or guarded while conflicts remain.

## Acceptance Criteria

- Host port conflicts are visible before runtime start.
- The UI prevents users from starting a lab with known port conflicts.
- Users can apply a recommended port from the UI.
- The app rechecks the port after a recommendation is applied.

## Edge Cases

- The port becomes unavailable after the UI check.
- The app cannot determine which process owns the port.
- Multiple nodes conflict with the same port.
- The user changes the Practicum API port.

## Implementation Notes

- The UI should not require users to understand Docker error messages.
- This should be integrated into both Designer Mode and Student Import preview/start workflows.

### Addendum 2026-10-25 — a port of your own (user request)

"When a port is already allocated the only option is to assume that port." The gate's port
conflicts are now cards ("web-1 · host port 8080/tcp / Already in use on this machine") with
**Use 8081** *and* a port field + **Apply** (Enter works too). The API's
`POST /labs/{id}/ports/apply-recommendation` accepts `new_host_port`; the service holds it to
the same rules as a recommendation (`ports.port_unavailable_reason`: not the conflicting port
itself, not the Practicum API's port, not used by another mapping in the lab, free on this
machine) and refuses with 409 + the reason, which the gate shows in the banner while keeping
the conflict card. Obvious mistakes (empty, out of 1-65535, the same port) never reach the API.
Tests: core `test_api.py::test_apply_a_chosen_port_instead_of_the_recommendation`,
`::test_a_chosen_port_is_refused_with_the_reason`, `test_ports.py::test_port_unavailable_reason_mirrors_the_conflict_rules`;
desktop `test_prestart_gate.py` (offers both, Enter applies, refusal explained),
`test_api_client.py::test_apply_port_recommendation_sends_a_chosen_port_and_surfaces_the_refusal`.

### Addendum 2026-10-25 — fixes start the machines fresh (user report)

"When a port is assumed all the previous session data persists." Worse: the assumed port was
not even in effect - a stopped lab's containers were reused by `docker start` with their old
mapping. A port or subnet fix now removes the lab's existing containers/networks first when the
lab has run (`LabService._store_rewritten_definition`, D-48); the lab returns to Ready, the
result carries `machines_reset`, and the gate says "machines were removed and will start fresh
… anything saved inside them from earlier sessions is gone". A never-started lab is rewritten
without touching Docker. Tests: core `test_api.py::test_port_fix_on_a_stopped_lab_recreates_its_machines`,
`test_network_conflicts_api.py` (recreate / nothing to reset / cleanup failure keeps the old
definition); desktop `test_prestart_gate.py::test_a_fix_that_recreated_the_machines_says_so`,
`test_api_client.py::test_port_and_network_fix_results_carry_machines_reset`.
