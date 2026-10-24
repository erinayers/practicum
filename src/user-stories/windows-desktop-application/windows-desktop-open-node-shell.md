# Open a Shell on a Lab Node

## User Story

As a student in a networking lab,
I want to open a terminal inside a lab node from the Practicum window,
so that I can run `ping`, configure routes, and follow the manual without knowing any Docker commands.

## Why This Matters

Most lab nodes are plain Linux containers with no web interface and no SSH server, and Docker Desktop keeps lab networks inside its VM — a student on Windows cannot reach `10.93.1.10` at all, let alone log in. The only way into such a node is `docker exec`, which contradicts the product promise that students never type Docker commands. The first Windows smoke run of the import flow hit exactly this: the lab started fine and the student had no way to use it (they tried `ssh 10.93.1.0`). Tigre/11 had flagged the gap as P0 (#2); this story closes it in its MVP form.

## User Flow

1. The user selects a lab in the main window. A **Lab Nodes** table lists every node with its container name and state (`running`, `exited`, `not created`, …).
2. Next to each *running* node there is an **Open shell** button (disabled otherwise, with a tooltip saying to start the lab first).
3. Clicking it opens a new terminal window on the host attached to that node's container — `bash` when the image has it, otherwise `sh` — with no Docker command typed by the user.
4. The window stays open if the attach fails (e.g. the container stopped meanwhile) so the reason is visible; the student closes it like any terminal.
5. The table refreshes whenever the lab is selected or after a Start, so buttons follow the real container state.

## Functional Requirements

- Container names and states come from `GET /labs/{lab_id}/status` (the desktop never derives Docker names itself).
- On Windows the shell opens in a new console window (`cmd /k docker exec -it <container> sh -c "…bash or sh…"`); on other platforms the first available terminal emulator is used.
- When no terminal can be opened, the app shows the exact `docker exec` command as copyable text instead of failing silently.
- The status line explains that node addresses are only reachable from inside the lab, not from the host.

## Acceptance Criteria

- A running lab's nodes are listed with their container state, each running node offering **Open shell**.
- **Open shell** opens a terminal inside that node without the user typing a Docker command.
- Nodes that are not running show a disabled button and a hint to start the lab.
- A launch failure is reported with the command the user could run manually.

## Edge Cases

- The container exited between the status refresh and the click — the console shows Docker's "is not running" message and stays open.
- Images without `bash` (alpine, busybox) — `sh` is used automatically.
- No terminal emulator on a non-Windows host — the command is shown for copying.
- Many nodes — the table scrolls; the rest of the window is unchanged.

## Implementation Notes

- Implemented 2026-10-23 (MVP via an external console, as proposed in Tigre/11 S-11): `desktop/src/practicum_desktop/node_shell.py` (`shell_command`, `open_node_shell` → `ShellLaunchResult`), `ApiClient.get_status` → `StatusResult{lab_status, resources, containers}`, and the **Lab Nodes** table in `main_window.py` (`_refresh_nodes`, `_on_status_loaded`, `_on_open_shell_clicked`).
- An in-app terminal widget (instead of a separate console window) and the running view's node picker from `windows-desktop-embedded-lab-view.md` should share this "node" concept later; the embedded-lab-view / lifecycle-controls stories own that screen.
- Not yet manually verified on Windows: the exact behaviour of `CREATE_NEW_CONSOLE` + `cmd /k` with Docker Desktop's `docker.exe`.
