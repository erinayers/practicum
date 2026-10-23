# 02 — Core API Architecture (`src/practicum/`)

Hexagonal-ish, small. Five modules, ~1,070 lines total.

```
main.py (147)   FastAPI routes — thin HTTP adapter, error → status-code mapping
service.py (227) LabService — in-memory store + lifecycle orchestration
runtime.py (353) LabRuntime Protocol + DockerRuntime adapter (docker CLI via subprocess)
ports.py (88)    Host port-conflict detection + recommendations (networking "ports")
models.py (258)  Pydantic v2 domain + response models (all extra="forbid" on inputs)
```

Dependency direction: `main → service → (runtime, ports) → models`. Nothing imports `main`.

## main.py — routes

Single module-level `service = LabService()` (tests reset it via `service.clear()` and
`service.runtime = DockerRuntime()` in an autouse fixture). App title "Practicum API", version
0.1.0, docs at `/docs`.

| Method & path | Handler | Returns | Errors |
|---|---|---|---|
| `GET /health` | `health` | `{"status":"ok"}` | — |
| `POST /labs/validate` | `validate_lab` (takes raw `dict`) | `ValidationResult{valid, lab?, errors[]}` | never raises; 200 with `valid=false` |
| `POST /labs` | `create_lab` (typed `LabDefinition`) | `Lab` **201** | FastAPI 422 on invalid body |
| `POST /labs/import` | `import_lab` (raw `dict`) | `ImportResult{imported, lab?, errors[]}` | never raises |
| `GET /labs` | `list_labs` | `list[Lab]` | — |
| `GET /labs/{id}` | `get_lab` | `Lab` | 404 |
| `GET /labs/{id}/export` | `export_lab` | `LabDefinition` (no id/status) | 404 |
| `GET /labs/{id}/preview` | `preview_lab` | `LabPreview` | 404 |
| `POST /labs/{id}/start` | `start_lab` | `RuntimeActionResult{success, lab, errors[]}` | 404 |
| `POST /labs/{id}/stop` | `stop_lab` | `RuntimeActionResult` | 404 |
| `POST /labs/{id}/reset` | `reset_lab` | `RuntimeActionResult` | 404 |
| `GET /labs/{id}/status` | `lab_status` | `RuntimeStatusResult{lab, resources[], errors[]}` | 404 |
| `GET /labs/{id}/ports` | `get_lab_ports` | `PortCheckResult{lab_id, has_conflicts, conflicts[]}` | 404 |
| `POST /labs/{id}/ports/apply-recommendation` | `apply_port_recommendation` body `{node_id, host_port, protocol="tcp"}` | `PortCheckResult` (fresh re-check) | 404, **409** if no conflict/recommendation |

`validation_issues(exc)` flattens Pydantic `ValidationError` → `ValidationIssue{location[],
message, issue_type}`. `validate` and `import` return 200 + structured errors; `POST /labs`
relies on FastAPI's default 422 (`detail[].loc/msg/type`) — the desktop client parses both shapes.

Runtime failures are **not** HTTP errors: they come back as 200 with `success=false` and
`errors[]` of `RuntimeIssue{message, command[]}`.

## service.py — LabService

- `_labs: dict[str, Lab]` — in-memory only; **lost on restart**; not thread-safe by design.
- `runtime: LabRuntime` — injected or `DockerRuntime()`.
- `create(definition)` → `Lab(id=uuid4(), **definition.model_dump())`, status `"defined"`.
- `export(id)` → `LabDefinition.model_validate(lab.model_dump(exclude={"id","status"}))`.
- `preview(id)` → `LabPreview`: `required_images` (deduped, order preserved),
  `estimated_resources` (sum cpu / sum memory_mb or `None` if none provided; sorted union of
  `exposed_ports`; concatenated `port_mappings`), `topology` (full nodes/networks/interfaces),
  `manual`.
- Status machine (string field on `Lab`):

  ```
  defined --start--> starting --ok--> running
                              --fail--> error
  running --stop--> stopping --ok--> stopped  (--fail--> error)
  any     --reset--> (ok) defined | (fail) error
  start when already "running"  → no-op success
  stop  when already "stopped"  → no-op success
  ```
  Note: `start` from `stopped` proceeds to call runtime.start (see Tigre/06 #2).
- `check_ports(id)` → delegates to `ports.check_lab_ports`.
- `apply_port_recommendation(id, node_id, host_port, protocol)`: re-runs the check, finds the
  matching conflict, and **rewrites the node's resources**: removes the port from
  `exposed_ports` (tcp only) or from `port_mappings`, then appends
  `PortMapping(host=recommended, container=<original container port>, protocol)`. Rebuilds the
  whole `LabDefinition` through validation and replaces the stored `Lab` (same id/status).
  Raises `PortRecommendationUnavailableError` if no matching conflict or `recommended_port is None`.
- `clear()` — test helper.

## runtime.py — LabRuntime + DockerRuntime

`LabRuntime(Protocol)`: `start(lab)`, `stop(lab)`, `reset(lab)`, `status(lab) -> list[RuntimeResourceStatus]`.

`RuntimeFailure(message, command)` — the only exception type; `FileNotFoundError` on the
`docker` binary becomes `RuntimeFailure("Docker CLI was not found", cmd)`.

### Naming / labels (deterministic; used by status & cleanup)

- Network: `practicum-{lab.id[:8]}-{network_id}`
- Container: `practicum-{lab.id[:8]}-{node_id}`
- Labels: `practicum.lab_id=<uuid>` on both; `practicum.network_id=` / `practicum.node_id=`.
- `_practicum_network_names()` lists networks with `--filter label=practicum.lab_id`.

### start(lab)
1. For each network → `_create_network`:
   - If `docker network ls --filter name=^<name>$` already shows it → reuse (idempotent restart).
   - Else `_remove_empty_practicum_networks_with_subnet(subnet)`: inspects all practicum-labelled
     networks, removes any with the same `IPAM.Config[].Subnet` and **no** `Containers`.
   - `docker network create --driver bridge --subnet S --gateway G --label ... name`.
     Gateway = **highest usable IP in the subnet not assigned to any interface** (`_gateway_ip`
     via `_usable_ips_descending`). Raises if none free.
   - "pool overlaps" Docker error is rewrapped into an actionable message telling the user to
     stop/reset the other lab or change the subnet.
2. For each node: collect its interfaces (error if none); `docker run -d --name N --label ...
   --network <first iface net> --ip <first iface ip> [--cpus] [--memory Xm] [--shm-size Xm]
   [-p p:p for exposed] [-p h:c/proto for mappings] [-e K=V ...] IMAGE [command...]`.
   `command` default is `["sleep","infinity"]`; `null` → image default CMD.
3. Remaining interfaces: `docker network connect --ip IP NET CONTAINER`.
4. Any `RuntimeFailure` → `_cleanup_after_failed_start` (= `reset`, errors swallowed) → re-raise.

### stop(lab) — `docker stop <container>` per node; ignores "no such container".
### reset(lab) — `docker rm -f <container>` per node (ignores "no such container"), then
`docker network rm <network>` per network (ignores "no such network").
### status(lab) — per network `docker network inspect <name>` (status "present"); per
container `docker inspect --format {{.State.Status}} <name>` (status = Docker's string e.g.
`running`, `exited`). Non-zero exit → `exists=False, error=stderr`. Never raises.

All subprocess calls: `capture_output=True, check=False, text=True`. Tests monkeypatch
`subprocess.run` and assert exact argv lists — **changing any flag order breaks tests**
(`tests/test_runtime.py`).

## ports.py — host port conflicts

- `api_reserved_port()` = `int(env PRACTICUM_API_PORT or 8000)`.
- `is_local_port_free(port)` — tries `bind(("127.0.0.1", port))` TCP; tests monkeypatch this.
- `check_lab_ports(lab) -> list[PortConflict]`. Collects `(node, host, container, proto)` from
  `exposed_ports` (host=container, tcp) and `port_mappings`. Conflict reasons, in priority
  order: `duplicate_in_spec` (same host+proto used >1 in the lab), `reserved_by_practicum_api`,
  `in_use_on_host`. Each conflict gets `recommended_port` = `find_available_port(start_after=host,
  unavailable=reserved ∪ all lab hosts ∪ earlier recommendations)` scanning upward from
  `max(host+1, 1024)` to 65535, or `None`.
- Note: UDP conflicts are still probed with a TCP bind (see Tigre/06).

## models.py — see Tigre/04 for the spec; response models summary

`ValidationIssue`, `ValidationResult`, `ImportResult`, `LabPreview` (+`ResourceEstimate`,
`TopologyPreview`), `RuntimeIssue`, `RuntimeActionResult`, `RuntimeResourceStatus{kind,id,name,
exists,status?,error?}`, `RuntimeStatusResult`, `PortConflict{node_id,host_port,container_port,
protocol,reason,recommended_port?}`, `PortCheckResult`, `ApplyPortRecommendationRequest`.
`Lab(LabDefinition)` adds `id: str`, `status: str = "defined"`.

## Tests (tests/, 100 passing)

| File | Count | Strategy |
|---|---|---|
| `conftest.py` | — | autouse `clear_labs` resets service + runtime; `client` = `TestClient(app)`; `lab_definition` = 3-node "Static Routing Fundamentals" dict (host-a, router, host-b; left 10.0.1.0/24, right 10.0.2.0/24; router has exposed 22 + mapping 2222→22) |
| `test_api.py` | 49 | End-to-end via TestClient; `RecordingRuntime` / `FailingRuntime` fakes assigned to `service.runtime`; port tests monkeypatch `practicum.ports.is_local_port_free` |
| `test_models.py` | 17 | Pydantic rule checks |
| `test_ports.py` | 9 | monkeypatched `is_local_port_free`, one real socket bind |
| `test_runtime.py` | 14 | monkeypatch `subprocess.run`, assert exact docker argv; covers cleanup-on-failure, stale network removal, network reuse, pool overlap message, missing CLI, idempotent stop/reset, no-gateway error |
| `test_service.py` | 11 | LabService with real `DockerRuntime` (no subprocess reached for CRUD/preview) |

Run: from repo root, `pytest` (needs the package importable — `pip install -e ".[dev]"` or
`PYTHONPATH=src`).

## Things the core does NOT do (yet)

- No persistence (no DB, no file store) — restart = empty lab list.
- No image pre-pull / progress (story `runtime-image-pull-progress`, not started). `docker run`
  implicitly pulls and blocks.
- No async/background start; `POST /start` blocks for the whole docker sequence (could be minutes
  on first pull; desktop client timeout is 3 s → see Tigre/06).
- No delete-lab endpoint (`DELETE /labs/{id}` does not exist — needed by the Labs Dashboard story).
- No port re-verification immediately before start (story edge case, open).
- Export is not guarded by the port-conflict check (open AC on `runtime-host-port-availability`).
