# 02 — Core API Architecture (`src/practicum/`)

Hexagonal-ish, small. Six modules, ~1,900 lines total (Session 6, 2026-10-25).

```
main.py (~270)   FastAPI routes — thin HTTP adapter, error → status-code mapping
service.py (~450) LabService — in-memory store + lifecycle orchestration + start progress store
runtime.py (~680) LabRuntime Protocol + DockerRuntime adapter (docker CLI via subprocess;
                 engine-mode probe / image inspect / streamed pull / docker start reuse /
                 progress callback; bridge or nat networks per lab OS)
ports.py (~110)  Host port-conflict detection + recommendations (TCP and UDP probes)
networks.py (~120) Subnet-overlap detection vs Docker networks + recommendations + subnet move
models.py (~430) Pydantic v2 domain + response models (all extra="forbid" on inputs);
                 Node.os / Node.shell (Windows labs, Session 6)
```

Dependency direction: `main → service → (runtime, ports, networks) → models`. Nothing imports
`main`. (`service.check_networks` feeds `runtime.list_networks()` output into `networks.py`.)

## main.py — routes

Single module-level `service = LabService()` (tests reset it via `service.clear()` and
`service.runtime = DockerRuntime()` in an autouse fixture). App title "Practicum API", version
0.1.0, docs at `/docs`.

| Method & path | Handler | Returns | Errors |
|---|---|---|---|
| `GET /health` | `health` | `{"status":"ok"}` | — |
| `POST /labs/validate` | `validate_lab` (takes raw `dict`) | `ValidationResult{valid, lab?, errors[]}` | never raises; 200 with `valid=false` |
| `POST /labs?origin=designer\|imported\|quick_start` | `create_lab` (typed `LabDefinition`) | `Lab` **201** | FastAPI 422 on invalid body / bad origin |
| `POST /labs/import?source_file=` | `import_lab` (raw `dict`) | `ImportResult{imported, lab?, errors[]}` (lab.origin = imported) | never raises |
| `GET /labs` | `list_labs` | `list[Lab]` (incl. origin/source_file/created_at/last_started_at/last_error) | — |
| `GET /labs/{id}` | `get_lab` | `Lab` | 404 |
| `PUT /labs/{id}` | `replace_lab` (typed `LabDefinition`) | `Lab` (same id/origin/timestamps, status `defined`; old Docker resources reset first) | 404, 422, **409** running / busy / cleanup failed |
| `DELETE /labs/{id}` | `delete_lab` | **204** (resets Docker resources first unless status is `defined`) | 404, **409** busy or cleanup failed (lab kept) |
| `GET /labs/{id}/export` | `export_lab` | `LabDefinition` (no id/status/bookkeeping — `LAB_RUNTIME_FIELDS`) | 404 |
| `GET /labs/{id}/preview` | `preview_lab` | `LabPreview` | 404 |
| `POST /labs/{id}/start?wait=true\|false` | `start_lab` | `RuntimeActionResult{success, lab, errors[], pending}`; `wait=false` → **202**, `pending=true`, Docker work on a background thread | 404, **409** busy |
| `POST /labs/{id}/stop` | `stop_lab` | `RuntimeActionResult` | 404, 409 busy |
| `POST /labs/{id}/restart` | `restart_lab` | `RuntimeActionResult` (stop + start; not-running labs just start) | 404, 409 busy |
| `POST /labs/{id}/reset` | `reset_lab` | `RuntimeActionResult` | 404, 409 busy |
| `GET /labs/{id}/status` | `lab_status` | `RuntimeStatusResult{lab, resources[], errors[], progress:[NodeStartProgress]}` | 404 |
| `GET /labs/{id}/ports` | `get_lab_ports` | `PortCheckResult{lab_id, has_conflicts, conflicts[]}` | 404 |
| `POST /labs/{id}/ports/apply-recommendation` | `apply_port_recommendation` body `{node_id, host_port, protocol="tcp", new_host_port?}` | `PortCheckResult` (fresh re-check); with `new_host_port` the user's port replaces the recommendation | 404, **409** if no conflict/recommendation, or the chosen port is unusable (`PortUnavailableError`: reserved by the API / used in the lab / bound on the host / the conflicting port itself — `ports.port_unavailable_reason`) |
| `GET /labs/{id}/networks` | `check_networks` | `NetworkCheckResult{lab_id, has_conflicts, conflicts:[SubnetConflict], error?}` — `error` set (200) when Docker can't be queried | 404 |
| `POST /labs/{id}/networks/apply-recommendation` | `apply_subnet_recommendation` body `{network_id}` | `NetworkCheckResult` (fresh re-check; lab + export now use the new subnet) | 404, **409** no conflict/recommendation |
| `POST /docker/sweep-leftovers` | `sweep_leftovers` | `LeftoverSweepResult{removed_containers[], removed_networks[], errors[], error?}` — Practicum-labelled resources whose lab id is unknown to this API; **also run by the `lifespan` startup hook** (D-40) | never raises |
| `GET /docker/engine` | `docker_engine` | `DockerEngineInfo{available, os_type: linux\|windows\|null, server_version, operating_system, kernel_version, host_build, isolation, detail}` — read-only `docker info`; which kind of container Docker Desktop serves (Session 6, D-42). Never switches it. | never raises (Docker down → `available=false` + detail) |
| `POST /labs/{id}/networks/remove-leftover` | `remove_leftover_network` body `{network_name}` | `NetworkCheckResult` (fresh re-check) | 404, **409** not a conflict / belongs to a listed lab / not Practicum's |

`validation_issues(exc)` flattens Pydantic `ValidationError` → `ValidationIssue{location[],
message, issue_type}`. `validate` and `import` return 200 + structured errors; `POST /labs`
relies on FastAPI's default 422 (`detail[].loc/msg/type`) — the desktop client parses both shapes.

Runtime failures are **not** HTTP errors: they come back as 200 with `success=false` and
`errors[]` of `RuntimeIssue{message, command[]}`.

## service.py — LabService

- `_labs: dict[str, Lab]` — in-memory only; **lost on restart**. `_progress: dict[lab_id, dict[node_id, NodeStartProgress]]`
  (latest start of each lab), `_transition_lock` (threading.Lock guarding the busy check),
  `_background_starts` (threads of `wait=false` starts).
- `runtime: LabRuntime` — injected or `DockerRuntime()`.
- `create(definition, origin="designer", source_file=None)` → `Lab(id=uuid4(), origin, source_file,
  created_at=now, **definition.model_dump())`, status `"defined"`.
- `replace(id, definition)` → edit: running → `LabRunningError`; busy check; reset unless `defined`
  (failure → `LabDeleteError`); `_with_definition` then status `defined`, `last_error` cleared.
- `sweep_leftovers()` → `runtime.list_practicum_containers()` (`docker ps -a --filter label=practicum.lab_id --format '{{.Names}}\t{{.Label "practicum.lab_id"}}\t{{.State}}'`) + `list_networks()`; removes every container/network whose `practicum.lab_id` is not a known lab; per-item errors collected; Docker down → `error`.
- `delete(id)` → busy check; **always** `runtime.reset` (cleanup failure ignored only for a never-started lab); `runtime.reset` unless status is `defined` (failure → status `error`,
  `last_error`, `LabDeleteError`); then forget the lab and its progress.
- `export(id)` → `LabDefinition.model_validate(lab.model_dump(exclude=LAB_RUNTIME_FIELDS))`.
  `_with_definition(lab, definition)` rebuilds a lab keeping id/status/origin/timestamps (used by
  the port and subnet recommendations).
- `preview(id)` → `LabPreview`: `required_images` (deduped, order preserved),
  `estimated_resources` (sum cpu / sum memory_mb or `None` if none provided; sorted union of
  `exposed_ports`; concatenated `port_mappings`), `topology` (full nodes/networks/interfaces),
  `manual`.
- Status machine (string field on `Lab`):

  ```
  defined/stopped/error --start--> starting --ok--> running   (last_started_at set, last_error cleared)
                                            --fail--> error   (last_error = message)
  running --stop--> stopping --ok--> stopped  (--fail--> error)
  running --restart--> stop then start
  any     --reset--> (ok) defined | (fail) error
  start when already "running"  → no-op success
  stop  when already "stopped"  → no-op success
  any lifecycle call (incl. delete) while "starting"/"stopping" → LabBusyError → 409
  ```
  `start` first re-checks host ports (`ports.check_lab_ports`) and fails with a structured
  `host port conflict: …` error without calling Docker; the runtime then re-checks the engine
  mode (`_require_engine_os`, Session 6: a Windows lab while Docker serves Linux containers — or
  vice versa — fails before anything is created, with the Docker Desktop switch instructions as
  `last_error`); then it records per-node progress via the runtime's `on_progress` callback
  (`_run_start`). `start(wait=False)` runs `_run_start` on a
  daemon-less `threading.Thread` and returns `pending=True` immediately. `status()` snapshots the
  progress *after* the Docker queries so it is never older than the lab status beside it.
  Start from `stopped` reuses the containers (`docker start`) — Tigre/06 #2 is fixed.
- `check_ports(id)` → delegates to `ports.check_lab_ports`.
- `docker_engine()` → `runtime.engine_info()`; a `RuntimeFailure` becomes `available=false`.
- `apply_port_recommendation(id, node_id, host_port, protocol, new_host_port=None)`: re-runs
  the check, finds the matching conflict, and **rewrites the node's resources**: removes the
  port from `exposed_ports` (tcp only) or from `port_mappings`, then appends
  `PortMapping(host=<recommended or chosen>, container=<original container port>, protocol)`.
  Rebuilds the whole `LabDefinition` through validation and stores it via
  `_store_rewritten_definition` (shared with the subnet fix): a lab that has run is **reset
  first** (containers/networks removed, status → `defined`, `machines_reset=True` in the
  result) so the next Start cannot `docker start` containers that still carry the old mapping
  and the old session data (D-48); a never-started lab is rewritten in place; cleanup failure
  → `LabDeleteError` (409), definition unchanged.
  Raises `PortRecommendationUnavailableError` if no matching conflict or `recommended_port is None`.
- `clear()` — test helper.

## runtime.py — LabRuntime + DockerRuntime

`LabRuntime(Protocol)`: `engine_info() -> DockerEngineInfo`, `start(lab, on_progress=None)`,
`stop(lab)`, `reset(lab)`, `status(lab) -> list[RuntimeResourceStatus]`, `list_networks()`,
`remove_network(info)`, `list_practicum_containers()`, `remove_container(name)`.
`ProgressCallback = Callable[[NodeStartProgress], None]` — test fakes must accept the second
argument of `start` and implement `engine_info` (see `RecordingRuntime` in `tests/test_api.py`).

`engine_info()` runs `docker info --format '{{json .}}'` (15 s timeout) and `parse_engine_info`
reads `OSType` (linux|windows), `ServerVersion`, `OperatingSystem`, `KernelVersion` (Windows:
"10.0 22631 (…)" → `host_build` 22631, which decides the Server Core tag the desktop pins),
`Isolation`. With the daemon down the CLI still prints the client JSON with `ServerErrors` and
exits 1 → `available=false` with that text; no JSON at all → stderr. The same parse lives in the
desktop's `docker_status.py` for its own probe.

`RuntimeFailure(message, command)` — the only exception type; any `OSError` launching the
`docker` binary becomes `RuntimeFailure(...)`: `FileNotFoundError` → "Docker CLI was not found",
anything else (e.g. `PermissionError`) → "Docker CLI could not be run: <exc>" (`_docker_cli_error`,
since 2026-10-23 — previously only `FileNotFoundError` was caught and `POST /start` could 500).

### Naming / labels (deterministic; used by status & cleanup)

- Network: `practicum-{lab.id[:8]}-{network_id}`
- Container: `practicum-{lab.id[:8]}-{node_id}`
- Labels: `practicum.lab_id=<uuid>` on both; `practicum.network_id=` / `practicum.node_id=`.
- `_practicum_network_names()` lists networks with `--filter label=practicum.lab_id`.

### start(lab)
0. `_require_engine_os(lab)`: `engine_info()`; when the daemon's `os_type` is known and differs
   from `lab.container_os` (every node's `os`, validated to agree) → `RuntimeFailure("This lab
   needs Windows containers, but Docker Desktop is currently serving Linux containers. … switch
   Docker Desktop to Windows containers (right-click the whale icon → 'Switch to Windows
   containers...') …", ["docker","info"])` before anything is created and outside the
   failed-start cleanup (nothing to clean). Unknown mode (empty answer, as the generic test fake
   gives) → let Docker decide.
1. For each network → `_create_network`:
   - If `docker network ls --filter name=^<name>$` already shows it → reuse (idempotent restart).
   - Else `_remove_empty_practicum_networks_with_subnet(subnet)`: inspects all practicum-labelled
     networks, removes any with the same `IPAM.Config[].Subnet` and **no** `Containers`.
   - `docker network create --driver bridge --subnet S --gateway G --label ... name`
     (`--driver nat` for Windows labs: Windows has no bridge driver; `NETWORK_DRIVERS`).
     Gateway = **highest usable IP in the subnet not assigned to any interface** (`_gateway_ip`
     via `_usable_ips_descending`). Raises if none free.
   - "pool overlaps" Docker error is rewrapped into an actionable message telling the user to
     stop/reset the other lab or change the subnet.
2. For each node (progress reported per step through `on_progress`, 2026-10-24):
   - `checking_image`: `docker image inspect --format {{.Id}} IMAGE`; rc 0 → present; "No such
     image" → `pulling_image`: `docker pull IMAGE` via `Popen` (stdout+stderr merged), parsing
     per-layer lines with `_PULL_LAYER_LINE` ("<id>: Downloading [bar] 1MB/2MB", "Download complete",
     "Extracting", "Pull complete", "Already exists") into a 0–99 % figure (layer fractions:
     downloading share×0.7, extracting 0.7+share×0.3, complete 1.0) and "n of m layers"; 100 % on
     exit 0; non-zero → `RuntimeFailure("could not pull image 'X': <last error line>")`.
     Non-TTY Docker usually prints status lines without byte counts → layer-granular progress.
     Other inspect errors (daemon down) raise.
   - `creating_container`: `_container_state(name)` (`docker inspect --format {{.State.Status}}`;
     rc≠0 or empty stdout → None). Exists → `docker start NAME` (a container left by Stop keeps
     its filesystem and endpoints). Else `docker run -d --name N --label ... --network <first
     iface net> --ip <first iface ip> [--cpus] [--memory Xm] [--shm-size Xm] [-p p:p for exposed]
     [-p h:c/proto for mappings] [-e K=V ...] IMAGE [command...]` (`command` default
     `["sleep","infinity"]`; `null` → image CMD) then `connecting_networks`: `docker network
     connect --ip IP NET CONTAINER` for the remaining interfaces.
   - `ready`.
3. Any `RuntimeFailure` → the current node is reported `failed` with the message, the message is
   prefixed `node '<id>' (<image>): …`, `_cleanup_after_failed_start` (= `reset`, errors swallowed),
   re-raise.

### stop(lab) — `docker stop <container>` per node; ignores already-missing containers.
### reset(lab) — `docker rm -f <container>` per node, then `docker network rm <network>` per
network; both ignore already-missing resources via `_is_missing_error` (matches "No such
container/network/object" **and** Docker's "network X not found" wording for `network rm` —
the old check only knew "no such network", so resetting a lab whose networks were gone failed).
### status(lab) — per network `docker network inspect <name>` (status "present"); per
container `docker inspect --format {{.State.Status}} <name>` (status = Docker's string e.g.
`running`, `exited`). Non-zero exit → `exists=False, error=stderr`. Running containers also get
`note` = first line of `/run/practicum-packages.status` via `docker exec … cat` (5 s timeout;
missing → None) — the quick start's package-install marker; Windows nodes (`node.os`) read
`C:\practicum\packages.status` with `cmd /c type` (`CONTAINER_NOTE_COMMANDS`). Never raises.

All `subprocess.run` calls: `capture_output=True, check=False, text=True`; the pull uses
`subprocess.Popen(stdout=PIPE, stderr=STDOUT, text=True, bufsize=1)`. Tests monkeypatch
`subprocess.run` (and `subprocess.Popen` with a `FakePullProcess`) and assert exact argv lists —
**changing any flag order breaks tests** (`tests/test_runtime.py`). With the generic fake that
answers rc 0 / empty stdout to everything, `_image_present` is True (no pull) and
`_container_state` is None (fresh `docker run`), which is why the older start tests still hold.

## ports.py — host port conflicts

- `api_reserved_port()` = `int(env PRACTICUM_API_PORT or 8000)`.
- `is_local_port_free(port, protocol="tcp")` — tries `bind(("127.0.0.1", port))` with a TCP or
  UDP socket; tests monkeypatch this (`tests/conftest.py` makes every port free by default and
  exposes the real probe as the `real_port_probe` fixture).
- `check_lab_ports(lab) -> list[PortConflict]`. Collects `(node, host, container, proto)` from
  `exposed_ports` (host=container, tcp) and `port_mappings`. Conflict reasons, in priority
  order: `duplicate_in_spec` (same host+proto used >1 in the lab), `reserved_by_practicum_api`,
  `in_use_on_host`. Each conflict gets `recommended_port` = `find_available_port(start_after=host,
  unavailable=reserved ∪ all lab hosts ∪ earlier recommendations)` scanning upward from
  `max(host+1, 1024)` to 65535, or `None`.
- `describe_conflict(conflict)` → "router 2222/tcp: already in use on this machine (try 2223)";
  used by `LabService.start` for the start-time re-check.

## networks.py — subnet conflicts (added 2026-10-23, story `runtime-subnet-conflicts`)

`move_subnet` also calls `rewrite_addresses(manual, renames)` (2026-10-24): whole-token replacement
of every moved interface address and the subnet in section markdown and task text, longest key
first, so "ping 10.93.1.20" in the manual follows the lab to its new subnet.

- `find_subnet_conflicts(lab, docker_networks, known_labs) -> list[SubnetConflict]`: for each lab
  network, the first Docker network (skipping those labelled with the lab's own id) whose IPv4
  subnet overlaps. Reason: `overlaps_other_lab` (label's lab id is in the store → name/status
  filled), `overlaps_leftover` (Practicum label, lab unknown), `overlaps_docker_network` (no
  label). `owner_container_count` = attached containers.
- `recommend_subnet(prefixlen, unavailable)`: first block of that size in `RECOMMENDATION_POOL =
  10.90.0.0/16` overlapping nothing in `unavailable` (= lab's subnets + all Docker subnets + other
  known labs' subnets + earlier recommendations); `None` for prefixes < /16 or > /30.
- `move_subnet(lab, network_id, new_subnet) -> dict`: definition with the network moved and every
  interface on it re-addressed at the same host offset (`10.50.0.10/24 → 10.90.0.10/24`); same
  prefix length required.
- Runtime side: `DockerRuntime.list_networks()` = `docker network ls --format {{.Name}}` then one
  `docker network inspect <all names>` → `DockerNetworkInfo{name, subnets (IPv4 only), lab_id
  (practicum.lab_id label), container_names}`; `remove_network(info)` = `docker rm -f` each
  container, then `docker network rm` (both tolerate "no such …"). `_query()` is the read-only
  subprocess helper (OSError/non-zero → `RuntimeFailure`).
- `LabDefinition` also rejects overlapping subnets *within* one lab.

## models.py — see Tigre/04 for the spec; response models summary

`ValidationIssue`, `ValidationResult`, `ImportResult`, `LabPreview` (+`ResourceEstimate`,
`TopologyPreview`), `RuntimeIssue`, `RuntimeActionResult`, `RuntimeResourceStatus{kind,id,name,
exists,status?,error?}`, `RuntimeStatusResult`, `PortConflict{node_id,host_port,container_port,
protocol,reason,recommended_port?}`, `PortCheckResult`, `ApplyPortRecommendationRequest`,
`DockerNetworkInfo`, `SubnetConflict`, `NetworkCheckResult`, `ApplySubnetRecommendationRequest`,
`RemoveLeftoverNetworkRequest`, `NodeStartProgress{node_id,image,step,percent?,detail?}`
(`NodeStartStep` literal), `RuntimeActionResult.pending`, `RuntimeStatusResult.progress`.
`Lab(LabDefinition)` adds `id`, `status = "defined"`, `origin: LabOrigin = "designer"`,
`source_file`, `created_at`, `last_started_at`, `last_error`; `LAB_RUNTIME_FIELDS` names the
non-spec fields that export/move_subnet/_with_definition strip or preserve.
`Node.os: NodeOS = "linux"` and `Node.shell: NodeShell | None` (Session 6, D-43): declared, not
guessed; `effective_shell` = shell or the OS default (bash / powershell); validators: shell fits
the OS, Windows nodes have no `shm_size_mb`/`sysctls`, all nodes of a lab share one OS
(`LabDefinition.container_os`). `LabPreview.container_os`. `DockerEngineInfo` for `GET /docker/engine`.

## Tests (tests/, 204 passing)

| File | Count | Strategy |
|---|---|---|
| `conftest.py` | — | autouse `clear_labs` resets service + runtime **and makes `is_local_port_free` answer True** (POST /start re-checks ports; the sandbox cannot bind 22); `real_port_probe` fixture returns the real function; `client` = `TestClient(app)`; `lab_definition` = 3-node "Static Routing Fundamentals" dict (host-a, router, host-b; left 10.0.1.0/24, right 10.0.2.0/24; router has exposed 22 + mapping 2222→22) |
| `test_api.py` | 79 | End-to-end via TestClient; `RecordingRuntime` / `FailingRuntime` fakes (`start(lab, on_progress=None)`, `engine_info()`) assigned to `service.runtime`; restart/delete/busy-409/origin/timestamps/progress/async-start tests added 2026-10-24; `/docker/engine`, Windows os/shell export→import round trip, preview `container_os`, mixed-OS rejection, structured engine-mode start failure added 2026-10-25 |
| `test_models.py` | 26 | Pydantic rule checks (+ os/shell rules, one OS per lab) |
| `test_ports.py` | 10 | monkeypatched `is_local_port_free(port, protocol)`, real TCP and UDP socket binds |
| `test_runtime.py` | 38 | monkeypatch `subprocess.run` (+ `Popen` → `FakePullProcess`), assert exact docker argv; covers cleanup-on-failure, stale network removal, network reuse, pool overlap message, missing CLI, idempotent stop/reset, no-gateway error, `docker start` reuse, image check/skip pull, layer progress, pull failure attribution, "network not found" tolerance; 2026-10-25: `parse_engine_info` (Windows/Linux/down), `engine_info` argv, engine-mode refusal both ways (nothing created), `nat` driver + PowerShell command for Windows labs, unknown mode lets Docker decide, Windows note via `cmd /c type` |
| `test_service.py` | 16 | LabService with real `DockerRuntime` (no subprocess reached for CRUD/preview); delete/restart/busy/export-strips-bookkeeping |
| `test_networks.py` | 11 | pure `networks.py` logic: recommendations, owner classification, own-network exemption, partial overlaps, `move_subnet` |
| `test_network_conflicts_api.py` | 11 | `FakeRuntime` (in-memory network list) assigned to `service.runtime`; the three `/networks` routes incl. 409 refusals |
| `test_windows_quickstart_contract.py` | 9 | **Cross-package** (imports `desktop/src`, skipped if absent): the lab the desktop's Windows quick start builds validates against `LabDefinition` for every host build in the matrix (pinned tag, one node, PowerShell, manual steps); Ubuntu builders unchanged (no `os`/`shell`/`PRACTICUM_*` leak); every `examples/*.json` validates; `windows-quickstart.json` carries the current `WINDOWS_INIT_SCRIPT` |

Run: from repo root, `pytest` (needs the package importable — `pip install -e ".[dev]"` or
`PYTHONPATH=src`).

## Things the core does NOT do (yet)

- No persistence (no DB, no file store) — restart = empty lab list, Docker resources become
  "leftovers" (Tigre/11 S-1).
- No image inventory endpoint (S-17), no host-resource feasibility check (S-19), no
  logs/diagnostics (S-20). (`PUT /labs/{id}` exists since 2026-10-24.)
- It reads Docker Desktop's engine mode but never switches it (D-42); a lab of the other kind
  simply refuses to start with the instructions.
- Export is deliberately not guarded by host-port conflicts (D-30): ports are machine-specific.
- The action lock is per process (in memory); a `starting` lab whose API restarts loses it.
- `wait=false` starts are plain threads (no cancellation — `student-start-lab` edge case).
