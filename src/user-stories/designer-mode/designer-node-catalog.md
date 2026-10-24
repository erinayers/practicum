# Machine Catalogue for the Custom Lab Designer

## User Story

As an instructor building a custom lab,
I want to pick machines from a list of ready-made types — a host, a router, a web server, a desktop — and chain them into a topology,
so that I don't have to know which Docker image does what or how to make a container forward packets.

## Why This Matters

The designer asked for a raw Docker image per machine. That is fine for a Docker user, but the point of Practicum is that instructors think in topologies ("two hosts and a router between them"), not in images and kernel flags. A router in particular cannot be built from a plain image: it needs IP forwarding switched on, which in Docker means a `--sysctl` that the spec could not express (user feedback, 2026-10-24: "I want images of nodes to pre-select from … daisy chain multiple machines together with a specific network topology").

## User Flow

1. In the Machines panel the instructor picks a machine type: **Ubuntu host**, **Alpine host (tiny)**, **Router**, **Web server**, **Ubuntu Desktop**, or **Custom image**. A one-line description explains what it is for.
2. The id is pre-filled (`host-1`, `router-1`, `web-1` …) and can be changed; only Custom image asks for an image name.
3. Adding the machine creates a complete node — image, start command, environment, resources, kernel parameters — and the topology shows it with the type's glyph and role.
4. Connecting machines to networks works as before, with the connect form pre-filling the next free address (routers get `.1`, hosts start at `.10`) and a reference line listing who already has which address on that network, plus the reserved Docker gateway.
5. The Networks panel lists each attached machine with its address.

## Functional Requirements

- Presets (`node_catalog.PRESETS`): Ubuntu host (`ubuntu:22.04`), Alpine host (`alpine:3.21`), Router (`alpine:3.21` + `net.ipv4.ip_forward=1`), Web server (`nginx:latest`, host port 8080 → 80, image command kept), Ubuntu Desktop (webtop on 3000/3001, shm 1 GB, image command kept), Custom image (free-form, spec default command).
- The spec gains `resources.sysctls` (namespaced `net.*`/`kernel.*`/`fs.*` keys only) and the runtime passes each as `docker run --sysctl k=v`; no privileged mode.
- The machine rows and the topology reflect the preset (glyph, title) and the derived role (host/gateway).
- Address suggestion skips the network address, the broadcast address, the highest usable address (Practicum's Docker gateway, D-14) and every assigned address.
- Editing a stored lab recognises the preset from the node (router by its sysctl, others by image) for display only; the spec stores plain nodes.

## Acceptance Criteria

- Choosing Router and adding it produces a node with `sysctls: {"net.ipv4.ip_forward": "1"}`; the resulting `docker run` carries `--sysctl net.ipv4.ip_forward=1`.
- Choosing Ubuntu Desktop produces the webtop node with its ports, shm and `command: null`.
- Ids are suggested and never collide with existing machines.
- The connect form pre-fills the next free address for the chosen network and updates the reference line after each connection.
- The Networks panel shows `machine · address` per attached machine.

## Edge Cases

- A /30 network has room for one host besides the gateway — the suggestion becomes empty once it is taken and the instructor types an address (validation still applies).
- A preset's published host port (8080, 3000) is already used on this machine — the pre-start gate reports the conflict and offers a free port, as for any lab.
- Forwarding is on for the router, but the hosts still need the router as their default gateway inside the lab (`ip route add default via <router>`) — that remains part of the exercise; the manual should say so.

## Implementation Notes

- `desktop/src/practicum_desktop/node_catalog.py` (`NodePreset`, `PRESETS`, `preset_by_key`, `preset_for_node`, `next_node_id`, `suggest_address`), `designer.py` (preset combo, `_on_preset_changed`, `_on_connection_target_changed`, `NetworkRow` addresses), core `models.py` (`SysctlName`, `ResourceRequirements.sysctls`), `runtime.py` (`--sysctl`).
- Presets are desktop-side only (D-36); the API knows nothing about them.

## Implementation Status

Done 2026-10-24 (Session 5, user feedback round). Tests: `desktop/tests/test_designer.py` (presets, definition, address suggestion), `tests/test_runtime.py::test_docker_runtime_passes_sysctls_for_router_nodes`, `tests/test_models.py`. Not yet run against Docker Desktop: verify a host — router — host chain actually forwards once the hosts' default route points at the router.
