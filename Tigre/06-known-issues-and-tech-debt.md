# 06 — Known Issues and Tech Debt

Found during the 2026-10-23 source review. Status legend: **open** / fixed (date) / wontfix.
Items marked *suspected* were reasoned from the code and Docker semantics but not reproduced
against a live Docker daemon.

## Bugs

| # | Severity | Where | Issue | Status |
|---|---|---|---|---|
| 1 | Low (dead code) | `desktop/.../quickstart.py:86-97` | `create_ubuntu_quick_start_lab()` reads `preview.network_subnets`, which does not exist on `PreviewResult` → `AttributeError` if ever called. Nothing calls it; `MainWindow._on_quick_start_clicked` posts `UBUNTU_QUICK_START_LAB` directly. Consequence: every Quick Start lab uses `10.50.0.0/24`, so two quick-start labs cannot run at once ("pool overlaps"). Fix: add `network_subnets` (from `topology.networks`) to `PreviewResult` or compute from `topology.networks[].subnet`, and wire MainWindow to `create_ubuntu_quick_start_lab`. | open |
| 2 | **High** (*suspected*) | `src/practicum/runtime.py` `start()`/`stop()` | `stop` runs `docker stop` (container stays, exited). A later `start` calls `docker run --name <same>` → Docker "Conflict: container name already in use" → `_cleanup_after_failed_start` → `reset` removes everything → status `error`. A second Start then succeeds. So **stop → start always fails once**. Fix options: in `_run_container`, if container exists use `docker start <name>`; or have `stop` remove containers (`docker rm -f`) — but "stopped" is supposed to preserve state; `docker start` is the better match. The upcoming Restart control would hit this immediately. | open |
| 3 | ~~High~~ | `desktop/.../api_client.py` `DEFAULT_TIMEOUT_SECONDS = 3.0` used for **all** calls incl. `start_lab` | `POST /start` blocks for the entire docker sequence (image pull can take minutes). httpx raises `ReadTimeout` after 3 s → desktop shows "Could not start the lab: …" while the server actually continues and (probably) succeeds. Fix short-term: long/none timeout for start/stop/reset; long-term: story `runtime-image-pull-progress` makes start async + polled. | **fixed 2026-10-23** — `LIFECYCLE_TIMEOUT_SECONDS = 900` (`ApiClient.lifecycle_timeout`) used by `start_lab`, with a specific "did not finish starting in time" message. Stop/reset/restart must use the same timeout when wrapped. Async start (`runtime-image-pull-progress`) is still the real fix. |
| 4 | Medium | `src/practicum/ports.py` | UDP mappings are probed with a TCP `bind()`; `in_use_on_host` for UDP is meaningless and a UDP port in use by another app is not detected. Use `SOCK_DGRAM` when `protocol == "udp"`. | open |
| 5 | Medium | `src/practicum/ports.py` `is_local_port_free` | Binds only `127.0.0.1`; a service bound to `0.0.0.0` on Windows can still collide / Docker publishes on `0.0.0.0`. Consider probing `0.0.0.0` too. Also the probe is a bind, not a connect — fine for "already bound" but on Windows some ports are in the Hyper-V excluded range and bind fails → reported as in use (acceptable). | open |
| 6 | Medium | `main_window.py`, `prestart_gate.py` | Worker attributes (`self._port_worker` etc.) are reassigned while a previous `QThread` may still be running → Qt warning/crash "QThread: Destroyed while thread is still running" on rapid clicks or row changes. Mitigate: keep a list of in-flight workers, disable buttons while busy, or `deleteLater` on finish. | open |
| 7 | Low | `main_window.py` `_on_status_checked` | Selecting the placeholder row "No labs defined yet." or an error row is harmless (guarded by `row >= len(self._lab_ids)`), but `labs_list` mixes message rows and lab rows — fragile for the dashboard rewrite. | open (will be replaced by dashboard) |
| 8 | Low | `service.py` `apply_port_recommendation` | Rewrites the stored `Lab` via `self._labs[lab_id] = Lab(...)`, so any caller holding the old object (none today) sees stale data; also the recommended port is validated free at check time only. Fine for now. | note |
| 9 | Low | `runtime.py` `_network_exists` | Filter `name=^{name}$` — Docker's name filter is a regex match, so `^…$` works, but the code additionally compares exact names; OK. Status "present" for networks is hard-coded rather than inspected. | note |
| 11 | **High** (observed on Windows 2026-10-23, screenshot) | `desktop/.../api_client.py` `check_health` (3 s timeout) + `startup.py` (single attempt) + `app_status.py` next-action text | On a cold/loaded machine (Docker Desktop failing to start at the same time) the desktop's one-shot health check timed out → banner **"Status: Blocked — The Practicum API did not respond in time"** and next action "Start the Practicum API with `uvicorn …`" **while the API was actually healthy** (launcher probe had just received 200 at the same URL). Second launch was fine. Fix: retry health with backoff (e.g. 5 × up to ~10 s) before declaring Blocked; use a longer timeout for the very first check; word the next action differently for timeout vs connection refused ("the API is slow to respond — retrying…" vs "not running"); consider auto-retry timer while Blocked. Related to #3. | open |
| 14 | Low (unverified) | `desktop/.../node_shell.py` `open_node_shell` on Windows | `cmd.exe /k docker exec -it … sh -c "…"` launched with `CREATE_NEW_CONSOLE`. Built and unit-tested with `Popen` mocked only; never run on Windows. Possible issues: quoting of the `sh -c` script through `cmd`, `docker.exe` not on PATH in the new console, `-it` needing a real TTY (should be fine in conhost). If it misbehaves, alternative is `start "Practicum - <node>" cmd /k …` via `shell=True`, or Windows Terminal `wt.exe`. | open — needs Windows run |
| 12 | Medium | `src/practicum/runtime.py` (`_run`, `_network_exists`, `_inspect_resource`, network inspect/ls), `desktop/.../docker_status.py` | Only `FileNotFoundError` was caught around `subprocess.run(["docker", …])`. Any other `OSError` (observed: `PermissionError` on a non-executable `docker` binary) escaped: `POST /labs/{id}/start` returned **HTTP 500** (violates D-15) and the desktop's `StartupWorker` thread died, leaving the window on "Checking Practicum status…" with Retry disabled. | **fixed 2026-10-23** — both catch `OSError`; message "Docker CLI could not be run: …" / "Docker could not be run: …". Tests added. |
| 13 | Medium (observed on Windows 2026-10-23) | `runtime.py` `_create_network` + `quickstart.py` / `samples/ubuntu-quickstart.json` + in-memory store | User imported the bundled `ubuntu-quickstart.json` and Start failed: "network 'lab-net' (10.50.0.0/24) overlaps with another Docker network". Root cause: the Quick Start button and the bundled sample share `10.50.0.0/24`, each lab gets a differently-named network, and Docker rejects the overlapping subnet. The owner is either a still-listed lab (Stop does **not** free the network — only Reset does) or an orphan left by an earlier API session (D-10: labs vanish on restart, Docker resources don't). The error text said "Stop or reset" — wrong; now says Reset and gives the `docker network ls --filter label=practicum.lab_id` recipe. Real fixes: S-16 subnet-overlap check in the gate (+ "pick a free subnet"), S-1 persistence/reconciliation, D-17 quick-start subnets from `10.90.0.0/16` (#1). | **fixed 2026-10-23** — story `runtime-subnet-conflicts`: `GET /labs/{id}/networks` + gate fixes (remove leftover / reset owner / use free subnet); import hands over to the gate. Root causes (S-1 persistence, #1 quick-start subnet) still open but no longer block a student. |
| 10 | Low | `models.py` `Interface` | No validation that `address` prefix length matches the network's prefix (e.g. `10.0.1.10/16` on a `/24` net is accepted; only `.ip` membership is checked). Harmless for Docker (`--ip` ignores prefix) but misleading in the UI. | open |

## Stale / inconsistent documentation

| # | Item | Detail | Status |
|---|---|---|---|
| D1 | `HANDOFF.md` | Says "all 6 phases done, last_updated 2026-08-15", `next_recommended_story` = runtime-host-port-availability. Does not mention Phase 7, `dialogs.py`, `prestart_gate.py`, `design/practicum-mockups.html`, `desktop/tests/conftest.py`, `test_dialogs.py`, `test_prestart_gate.py`, or that `PreviewResult` now carries topology/resources. Section 2 tree lacks `design/`. Section 5 claims "no widget tests" — now false. | open — update or point to Tigre |
| D2 | `user-story-status.json` | `latest_checkpoint` prose says `windows-desktop-in-app-dialogs` is "done", but the story's own `status` is `in_progress` with 3 open ACs. The story status is the more accurate one. | open |
| D3 | `README.md` | "Development" covers only the core. No desktop README; desktop run instructions only in HANDOFF §10. | open |
| D4 | `windows-desktop-prestart-lab-gate.md` | Functional requirement "Images already present locally are visually distinguished from images that will be pulled" and "manual preview accessible" are not met by the implementation (only a step count; no local/pull flag — no API support). Story is marked done; treat these as carried-over scope for `runtime-image-pull-progress` / a follow-up. | note |
| D5 | `src/user-stories.md` | "Suggested MVP Backlog" list is the original pre-phase ordering and is now superseded by "Recommended Story Order"; harmless but confusing. | note |

## Repo hygiene

| # | Item | Detail | Status |
|---|---|---|---|
| H1 | `__pycache__` noise | Hundreds of `*.cpython-314 (# Name clash 2026-06-16 xxxxxx #).pyc` files under `src/practicum/__pycache__` and `tests/__pycache__` — artefacts of a file-sync tool resolving conflicts (the project lives in a synced folder). Gitignored, but they bloat zips. Safe to delete all `__pycache__` and `.pytest_cache` dirs. | open |
| H7 | `.ruff_cache/` | Created when running ruff; not in `.gitignore` (which lists `__pycache__`, `.pytest_cache`, `.venv`, `dist`, `build`, egg-info). Add `.ruff_cache/` to `.gitignore` if ruff becomes part of the workflow. | note |
| H2 | `desktop/src/practicum_desktop/eduLabs.code-workspace` | VS Code workspace file inside the package with personal relative paths (`../../../../../Interview Prep`, `.../Qwen`). Will be shipped in the wheel (`packages = ["src/practicum_desktop"]`). Move to repo root or delete. | open |
| H3 | Folder name | Workspace is `eduLabs - Copy` while everything inside is "Practicum". Decide on one name (Tigre/09). | open |
| H4 | No CI | No GitHub Actions / pre-commit. Tests must be run manually (core: `pytest` at root; desktop: `pytest` in `desktop/`). | open |
| H5 | No lock file / pinned versions | Only ranges in pyproject. Environment drift risk (author on Python 3.14, pyproject says ≥3.12). | note |
| H6 | `LabPreview.topology.nodes` | Exposes full `Node` including `environment` values — if env vars ever carry secrets, preview/export leak them (they're in the spec anyway). | note |

## Design debts that Phase 7 will force

- MainWindow is one tall `QVBoxLayout` (480×420). Dashboard / running view / designer need a
  screen stack (`QStackedWidget`) and a toolbar. Plan the restructure once, not per story.
- `ApiClient` is synchronous httpx + QThread per call; fine, but consider a single
  `httpx.Client` for connection reuse and a per-call timeout parameter.
- There's no notion of "current running lab" in the app state; the running view will need it.
  The import flow's `MainWindow._apply_pending_selection(lab_id, message, show_manual)` is the
  current "land on this lab" hook — re-point it at the running view when that exists.
- Mixed line endings per file (CRLF: most of `desktop/`, `ports.py`, `test_ports.py`,
  `test_service.py`, story markdown; LF: the rest). No `.gitattributes`. Preserve each file's
  existing ending when editing (new desktop modules were created CRLF to match their siblings).
- Status polling (`GET /status`) isn't used by the desktop at all yet.
