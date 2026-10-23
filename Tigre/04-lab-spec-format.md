# 04 — Lab Spec Format (the JSON contract)

Defined by `LabDefinition` in `src/practicum/models.py` (Pydantic v2). **All input models use
`extra="forbid"`** — unknown keys are validation errors. This is the file instructors export and
students import; it is the public contract the future-roadmap promises to keep stable
(`public-spec-compatibility.md`).

## Top level — `LabDefinition`

| Field | Type | Rules / default |
|---|---|---|
| `schema_version` | str | default `"1.0"`, pattern `^\d+\.\d+$` (no version negotiation exists yet — any `X.Y` accepted) |
| `name` | str | required, 1–120 chars |
| `description` | str? | ≤ 2000 |
| `author` | str? | 1–120 |
| `version` | str? | 1–40 (free text) |
| `manual` | `LabManual`? | optional |
| `nodes` | `list[Node]` | **min 1** |
| `networks` | `list[Network]` | **min 1** |
| `interfaces` | `list[Interface]` | **min 1** |

Cross-field validator `validate_topology`: unique node ids; unique network ids; every interface
references an existing node and network; `interface.address.ip ∈ network.subnet`; a node may
have at most one interface per network; an IP may be assigned only once **across all networks**.

Stored form `Lab` adds `id` (uuid4 string) and `status` (string; see Tigre/02 state machine).
`export` strips these two.

## `Node`

| Field | Type | Rules / default |
|---|---|---|
| `id` | str | `^[a-z][a-z0-9-]*$` — becomes part of the container name |
| `image` | str | required, non-empty (any Docker ref) |
| `command` | `list[str] \| null` | default `["sleep","infinity"]`; **`null` = use image CMD** (needed for service/GUI images) |
| `environment` | `dict[EnvName, str]` | keys match `^[A-Za-z_][A-Za-z0-9_]*$`; passed as `-e K=V` |
| `resources` | `ResourceRequirements`? | optional |

## `ResourceRequirements`

| Field | Type | Rules |
|---|---|---|
| `cpu` | float? | > 0 → `--cpus` |
| `memory_mb` | int? | > 0 → `--memory {n}m` |
| `shm_size_mb` | int? | > 0 → `--shm-size {n}m` |
| `exposed_ports` | `list[int]` | each 1–65535, unique; each → `-p p:p` (tcp, host == container) |
| `port_mappings` | `list[PortMapping]` | `{host, container, protocol="tcp"\|"udp"}`; `(host, protocol)` unique; may not overlap an exposed port (as tcp) |

## `Network` — `{id: ^[a-z][a-z0-9-]*$, subnet: IPv4Network}` (must be a proper network
address; Pydantic/ipaddress strict). Gateway is chosen at runtime (highest free usable IP).

## `Interface` — `{node: str, network: str, address: IPv4Interface}` e.g. `"10.0.1.10/24"`.
The prefix length is carried but only `.ip` is used by Docker (`--ip`).

## `LabManual` → `sections: list[ManualSection]` (unique section ids)

`ManualSection`: `id` (`^[a-z][a-z0-9-]*$`), `title` (1–120), `content_markdown` (1–10000,
rendered with `QTextBrowser.setMarkdown` — headings, lists, code fences, links), `tasks:
list[ManualTask]` (unique ids within a section). `ManualTask`: `id` (same pattern), `text`
(1–500). Student progress is keyed by `lab_id/section_id/task_id` in desktop QSettings — so
**renaming task/section ids resets student progress**.

## Minimal valid example

```json
{
  "name": "Tiny",
  "nodes": [{"id": "a", "image": "alpine:3.21"}],
  "networks": [{"id": "n", "subnet": "10.0.0.0/24"}],
  "interfaces": [{"node": "a", "network": "n", "address": "10.0.0.10/24"}]
}
```

## Bundled examples (`examples/`)

| File | Purpose | Notable |
|---|---|---|
| `static-routing.json` | Canonical 3-node 2-network topology (host-a, router, host-b) | router: exposed `22` + mapping `2222→22`, cpu/mem on all nodes, 2 manual sections. Same data as the `lab_definition` test fixture. |
| `ubuntu-quickstart.json` | One `ubuntu:22.04` container on `10.50.0.0/24` | Mirrored in `desktop/.../quickstart.py` |
| `ubuntu-webtop.json` | Browser-accessible desktop `lscr.io/linuxserver/webtop:ubuntu-xfce` | `command: null`, env `TITLE`, cpu 2 / 2048 MB / shm 1024, ports 3000 & 3001 (noVNC at https://localhost:3001), network `10.10.1.0/24` |

## Subnet conventions in use

`10.0.x.0/24` examples · `10.10.1.0/24` webtop · `10.50.0.0/24` quick start ·
`10.90.0.0/16` reserved pool for auto-picked quick-start subnets (not yet actually used).
Two labs with the same subnet cannot run simultaneously (Docker "pool overlaps").

## Ideas not yet in the schema (seen in mockups / stories — do not assume they exist)

- Lab "origin" (imported / quick start / custom) and "last run" timestamps (dashboard cards).
- Per-image local/size info (pre-start gate).
- `.zip` lab exports (import story mentions `.json` or `.zip`; only JSON exists).
- Quick-start package list / OS template (mockup `screen-quickstart`).
- Per-node start progress state (image pull story).
