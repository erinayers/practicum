# Open a PowerShell Shell on a Windows Lab Node

## User Story

As a student working in a Windows Quick Start lab,
I want **Open shell** to launch PowerShell inside the Windows container,
so that I can follow the lab instructions using native Windows commands.

## Why This Matters

The existing shell action enters Linux containers with `sh`. A Windows container has no POSIX
shell, so reusing that command would open a terminal that immediately fails.

## Functional Requirements

- Identify the node's declared container OS/shell instead of guessing from arbitrary image text.
- Launch `docker exec` with PowerShell for Windows nodes and preserve the current bash/sh behavior
  for Linux nodes.
- Keep the shell in a separate interactive host terminal and leave the existing error/copy-command
  behavior available if launch fails.
- Show the node name and shell type in the action and its success/error message.

## Acceptance Criteria

- **Open shell** on a running Windows Quick Start node opens an interactive PowerShell prompt in
  that container.
- **Open shell** on Linux nodes continues to prefer bash and falls back to sh.
- A stopped or missing Windows container produces a visible, actionable error rather than a
  silent terminal flash.
- The shell selection is preserved when a lab is exported and imported.

## Dependencies

- Enables `designer-windows-quick-start.md`.
- The lab spec must carry an explicit supported OS/shell hint if the image alone cannot determine
  the correct shell.

## Implementation Status

**Done 2026-10-25** (Session 6).

- `node_shell.shell_command(container, os, shell)` builds the `docker exec -it` argv from the
  node's *declared* `os`/`shell` (carried by `GET /labs/{id}/preview` → `TopologyNodeInfo`):
  Linux keeps `sh -c 'bash -l || sh -l'` (or `bash -l` / `sh -l` when declared); Windows runs
  `powershell.exe -NoLogo -ExecutionPolicy Bypass` (or `cmd.exe`). No argument has a space or a
  quote, so `cmd /k` on the host cannot mangle it. The all-users PowerShell profile written by the
  Windows quick start's init prints the tool-install status and refreshes PATH on entry.
- `open_node_shell()` first asks `docker inspect` for the container state: a stopped or missing
  container returns an in-app error ("Cannot open PowerShell on 'host': its container is not
  running (state: exited). Start the lab…") with the command to copy, instead of a console
  window that flashes and closes. When Docker cannot be asked the launch proceeds and `cmd /k`
  keeps Docker's own error visible, as before.
- Running view: the button says **Open PowerShell** (terminal icon) on Windows nodes, **Open
  shell** on Linux ones; tooltip, accessible name and the status line name the node and shell
  ("Opened PowerShell on 'host' in a new window."). Buttons are re-labelled once the preview
  arrives.
- The shell hint is a spec field, so it survives export and import (core `test_api.py`).
- Tests: `test_node_shell.py` (commands per OS/shell, pre-check refusal, launch errors),
  `test_running_view.py` (Windows button/tooltip/disabled state), `test_api_client.py`.
- Tigre/06 #14 (Windows console launch never run on Windows) still applies to both shells.

### Acceptance criteria → tests

| Criterion | Tests |
|---|---|
| Open shell on a running Windows node opens an interactive PowerShell prompt | desktop `test_node_shell.py::test_shell_command_uses_powershell_for_windows_nodes` (`docker exec -it … powershell.exe -NoLogo -ExecutionPolicy Bypass`, quoting-safe), `::test_open_node_shell_on_a_windows_node_launches_powershell` (`cmd /k` console), `test_running_view.py::test_windows_node_offers_open_powershell` (button → `open_node_shell(name, id, "windows", "powershell")`). The prompt itself needs the Windows run. |
| Linux nodes keep bash → sh | `test_node_shell.py::test_shell_command_prefers_bash_and_falls_back_to_sh`, `::test_shell_command_honours_a_declared_linux_shell`, `::test_open_node_shell_on_windows_uses_a_new_console_kept_open`; `test_running_view.py::test_nodes_table_and_open_shell` |
| Stopped or missing Windows container → actionable error, no silent flash | `test_node_shell.py::test_open_node_shell_refuses_a_stopped_or_missing_container` (no `Popen`), `::test_container_state_reads_docker_inspect`; `test_running_view.py::test_shell_launch_failure_is_shown_with_the_command_to_copy`, `::test_windows_node_offers_open_powershell` (disabled button + tooltip while stopped) |
| Shell hint survives export and import | core `test_api.py::test_windows_lab_os_and_shell_survive_export_and_import`, `test_models.py::test_windows_node_declares_its_os_and_defaults_to_powershell`; desktop `test_api_client.py::test_get_preview_carries_container_os_and_node_shells`, `::test_import_lab_reads_the_container_os_of_the_imported_lab`, `test_designer.py::test_editing_a_windows_lab_keeps_os_and_shell` |

## Scope note 2026-10-25

Windows containers require Windows 10/11 Pro, Enterprise or Education (Hyper-V and the
Containers features); Windows Home — the common student laptop — cannot run them. This feature
is therefore planned to move behind the paid tier; the implementation above stays as built and
the gating, eligibility check and hosted alternative are described in the roadmap epic
[Premium Lab Platforms](../../future-roadmap/premium-lab-platforms/README.md).
