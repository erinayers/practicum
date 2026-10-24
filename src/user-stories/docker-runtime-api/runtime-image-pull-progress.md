# Image Pull and Start Progress

## User Story

As a student starting a lab for the first time,
I want to see real progress while images download and containers come up,
so that a slow first start doesn't look like the app has frozen.

## Why This Matters

`runtime-api-start-lab.md` and `runtime-api-status.md` already give the desktop app a way to start a lab and poll its status, but today that's all-or-nothing: `DockerRuntime.start()` shells out to `docker run` per container via `subprocess` and blocks until each one finishes or fails, with no incremental state exposed in between. For a lab whose image isn't cached locally yet (for example `linuxserver/webtop:ubuntu-xfce` in `examples/ubuntu-webtop.json`, which is a large multi-hundred-megabyte pull), that can mean a multi-minute wait with zero feedback. The desktop-facing mockups (`windows-desktop-prestart-lab-gate.md`, `windows-desktop-import-lab-file.md`) show a progress sequence like "pulling image 2 of 3… 64%," but that is currently a fixed-duration animation with no real data behind it — this story is what would make it real.

## User Flow

1. The desktop app calls `POST /labs/{lab_id}/start` as it does today.
2. Instead of blocking until every container is up, the API accepts the request and begins starting the lab in the background, immediately returning a status the desktop app can poll (reusing the existing status mechanism from `runtime-api-status.md`).
3. While starting, each node's status reflects its current step: for example "pulling image" (with a percentage, when Docker reports one), "creating network," "starting container," or "ready."
4. The desktop app polls status and updates its progress UI with the real current step and percentage instead of a scripted animation.
5. If a specific node's image pull or container start fails, the status reflects which node and why, rather than only a generic "start failed."

## Functional Requirements

- Starting a lab whose images are already present locally proceeds quickly, without claiming a pull is happening.
- Starting a lab whose images need to be pulled surfaces per-node progress that updates over time rather than appearing frozen.
- Progress is per-node, not a single blended percentage, since different nodes may be pulling simultaneously or may already have their image cached.
- A failure during pull or container creation is attributed to the specific node/image involved.

## Acceptance Criteria

- Lab status exposes a distinguishable "in progress" state per node while starting, separate from `running`, `stopped`, and `error`.
- When a node's image must be pulled, its status includes enough information for the desktop app to show real percentage-style progress, not a fixed timer.
- When a node's image is already local, its status does not show pull progress, moving directly to container startup.
- A failed pull or container start is reported against the specific node, with a message distinct from a generic failure.
- Existing start/status/stop/reset behavior and endpoints are otherwise unchanged.

## Edge Cases

- The image does not exist or the tag is wrong — this should surface as a clear per-node error, not a timeout.
- The network connection drops mid-pull — the status should reflect a stalled/failed pull rather than continuing to claim progress.
- Several nodes pull large images at the same time — status must stay per-node so the desktop app doesn't average unrelated progress together.
- A very large image reports progress updates slowly — the desktop app should treat "no update yet" differently from "stalled," so the UI doesn't look broken between updates.

## Implementation Notes

- This is backend/runtime work, unlike the rest of the mockup-driven backlog in `windows-desktop-application` and `designer-mode`, which is desktop UI only. This story is the one exception.
- `DockerRuntime.start()` (`src/practicum/runtime.py`) currently relies on `docker run`'s implicit pull-if-missing behavior and only reads the command's final exit code, not its streamed output. Getting real progress likely means explicitly issuing `docker pull <image>` as a separate step per node before `docker run`, and parsing Docker's own streamed JSON progress output (`docker pull` and the Docker Engine API both emit structured per-layer progress) rather than inventing a new progress format.
- Prefer extending the existing polling-based status mechanism (`GET /labs/{lab_id}/status`) with richer per-node state rather than introducing a new transport (e.g., SSE/WebSockets); the rest of this API is plain REST/polling, and polling is sufficient for progress that updates on the order of seconds.
- Once this lands, the desktop app's loading sequences in `windows-desktop-prestart-lab-gate.md` and `windows-desktop-import-lab-file.md` should be updated to poll and render this real progress instead of their current fixed-duration animation.

## Implementation Status

Done 2026-10-24 (Session 5).

- Runtime (`src/practicum/runtime.py`): `DockerRuntime.start(lab, on_progress)` now checks each image with `docker image inspect` and, only when it is missing, runs an explicit `docker pull` through `Popen`, parsing Docker's per-layer status lines ("Downloading", "Download complete", "Extracting", "Pull complete", "Already exists", and the byte counts when a TTY-style bar is present) into a 0–100 % figure ("3 of 7 layers"). Steps per node: `waiting → checking_image → pulling_image → creating_container → connecting_networks → ready`, or `failed` with the message; a failure is attributed to the node (`node 'router' (frr): could not pull image …`).
- Service/API: `GET /labs/{lab_id}/status` gained `progress: [NodeStartProgress]` (live while `starting`, then the final per-node outcome) and the lab's `last_error`. `POST /labs/{lab_id}/start?wait=false` returns 202 with `pending=true` and starts in a background thread; the default `wait=true` keeps the synchronous contract, so existing behaviour and endpoints are otherwise unchanged (last AC). Lifecycle calls are locked while `starting`/`stopping` (`runtime-lab-restart.md`).
- Desktop: the pre-start gate and the import dialog start with `wait=false` and poll the status every second, showing `StartProgressPanel` / a real stage line and percentage instead of the fixed timers; the running view shows the same panel while a lab is `starting` (`windows-desktop-status-polling.md`).
- Non-TTY `docker pull` output omits byte counts on most Docker versions, so progress is then measured in layers (still real, coarser). The image does not exist → the per-node error is Docker's manifest message, not a timeout.
- Tests: `tests/test_runtime.py` (image check, layer progress, failure attribution, Docker down), `tests/test_api.py` (progress in status, async 202 + completion, async failure), `desktop/tests/test_progress_panel.py`, `test_prestart_gate.py`, `test_import_lab.py`, `test_running_view.py`. Verified end-to-end with a fake `docker` CLI that streams pull output (progress visible in the gate at 18 %…100 %).
