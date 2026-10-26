# 04 — Lab Spec Format (the JSON contract)

Defined by `LabDefinition` in `src/practicum/models.py` (Pydantic v2). **All input models use
`extra="forbid"`** — unknown keys are validation errors. This is the file instructors export and
students import; it is the public contract the future-roadmap promises to keep stable
(`public-spec-compatibility.md`).

## Top level — `LabDefinition`

| Field | Type | Rules / default |
|---|---|---|
| `schema_version` | str | default `"1.0"`, pattern `^\d+\.\d+$`; since 2026-10-23 the **major must be in `SUPPORTED_SCHEMA_MAJOR_VERSIONS = (1,)`** (`models.py`) — `1.7` passes, `2.0` fails with "schema_version '2.0' is not supported by this version of Practicum (supported: 1.x)" (D-20) |
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
| `os` | `"linux" \| "windows"` | default `linux` (2026-10-25, schema still 1.x). Declared, never guessed from the image. All nodes of a lab must agree (Docker Desktop serves one kind at a time); decides the network driver (`bridge`/`nat`), the start-time engine check and how the status note is read |
| `shell` | `"bash" \| "sh" \| "powershell" \| "cmd" \| null` | default `null` = the OS default (bash→sh on Linux, PowerShell on Windows); must fit the `os`. What the desktop's Open shell / Open PowerShell launches |

## `ResourceRequirements`

| Field | Type | Rules |
|---|---|---|
| `cpu` | float? | > 0 → `--cpus` |
| `memory_mb` | int? | > 0 → `--memory {n}m` |
| `shm_size_mb` | int? | > 0 → `--shm-size {n}m` (rejected on `os: windows` nodes) |
| `exposed_ports` | `list[int]` | each 1–65535, unique; each → `-p p:p` (tcp, host == container) |
| `port_mappings` | `list[PortMapping]` | `{host, container, protocol="tcp"\|"udp"}`; `(host, protocol)` unique; may not overlap an exposed port (as tcp) |
| `sysctls` | `dict[str, str]` | keys must be namespaced `net.*` / `kernel.*` / `fs.*` → `--sysctl k=v` (e.g. `net.ipv4.ip_forward: "1"` for the designer's Router preset; added 2026-10-24, schema still 1.x); rejected on `os: windows` nodes |

## `ManualSection` addendum (2026-10-25)

`requires_screenshot: bool = false` — the instructor asks for a screenshot of this step; the
desktop's flyout offers capture/upload, the step counts as complete only with one attached, and
the exported results carry the image. Old specs validate unchanged.

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
| `windows-quickstart.json` | The Windows quick start export: one `mcr.microsoft.com/windows/servercore:ltsc2022` node, `os: windows`, `shell: powershell` | `command` = PowerShell `-EncodedCommand` init (the desktop's `WINDOWS_INIT_SCRIPT`), env `PRACTICUM_PACKAGES="git 7zip"` + `PRACTICUM_PACKAGE_SOURCE=chocolatey`, cpu 2 / 2048 MB, network `10.92.0.0/24`, 2 manual steps. Needs Docker Desktop in Windows-container mode (2026-10-25) |

## Subnet conventions in use

`10.0.x.0/24` examples · `10.10.1.0/24` webtop · `10.50.0.0/24` quick start sample ·
`10.92.0.0/24` windows quick start sample · `10.90.0.0/16` pool for auto-picked quick-start
subnets (in use since 2026-10-24).
Two labs with the same subnet cannot run simultaneously (Docker "pool overlaps").

## Ideas not yet in the schema (seen in mockups / stories — do not assume they exist)

- Lab "origin" (imported / quick start / custom) and "last run" timestamps (dashboard cards).
- Per-image local/size info (pre-start gate).
- `.zip` lab exports (import story mentions `.json` or `.zip`; only JSON exists).
- Quick-start package list / OS template (mockup `screen-quickstart`).
- Per-node start progress state (image pull story).
