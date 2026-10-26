"""Open an interactive shell inside a running lab node (windows-desktop-open-node-shell,
windows-desktop-open-windows-shell).

MVP: the shell runs in a new console window on the host (Windows: a fresh conhost/Terminal
window; elsewhere: the first terminal emulator found) using `docker exec`. Practicum never
asks the student to type the docker command themselves; when no console can be opened the
command is handed back so it can at least be copied.

Which shell is launched follows the node's *declared* OS and shell (spec fields `os` and
`shell`, carried by the preview), never a guess from the image name:

    linux    (default)  `sh -c 'bash -l || sh -l'`  - bash when the image has it, else sh
    linux    shell=sh   `sh -l`
    linux    shell=bash `bash -l`
    windows  (default)  `powershell.exe -NoLogo -ExecutionPolicy Bypass`
    windows  shell=cmd  `cmd.exe`

Login shells / the PowerShell profile print the quick start's package-install status on
entry. Before launching, the container's state is checked: a stopped or missing container
gives an actionable in-app error instead of a console window that flashes and closes.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from dataclasses import dataclass

# Prefer bash when the image has it (ubuntu, debian…), fall back to sh (alpine, busybox).
# Login shells (-l) so /etc/profile.d runs: quick-start nodes print their package-install
# status there ("installing …" / "ready" / "FAILED").
SHELL_SELECTOR = "command -v bash >/dev/null 2>&1 && exec bash -l || exec sh -l"
# PowerShell: no banner, and let the all-users profile (written by the Windows quick start's
# init script, which prints the package status) run even under a Restricted policy. No
# spaces or quotes in any argument, so nothing can be mangled by `cmd /k` on the way.
POWERSHELL_COMMAND = ["powershell.exe", "-NoLogo", "-ExecutionPolicy", "Bypass"]
CMD_COMMAND = ["cmd.exe"]

SHELL_LABELS = {
    "bash": "bash",
    "sh": "sh",
    "powershell": "PowerShell",
    "cmd": "Command Prompt",
}
DEFAULT_SHELL_BY_OS = {"linux": "bash", "windows": "powershell"}
STATE_CHECK_TIMEOUT_SECONDS = 5.0
_NO_CONSOLE_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)

LINUX_TERMINALS: tuple[tuple[str, ...], ...] = (
    ("x-terminal-emulator", "-e"),
    ("gnome-terminal", "--"),
    ("konsole", "-e"),
    ("xterm", "-e"),
)


@dataclass
class ShellLaunchResult:
    success: bool
    detail: str = ""
    command: list[str] | None = None  # the docker command, for copying when launch fails


def effective_shell(os: str = "linux", shell: str | None = None) -> str:
    """The shell name that will run: the declared one, else the OS default."""
    return shell or DEFAULT_SHELL_BY_OS.get(os, "bash")


def shell_label(os: str = "linux", shell: str | None = None) -> str:
    """How the action names the shell: 'PowerShell', 'bash', 'sh', 'Command Prompt'; a Linux
    node without a declared shell says 'bash or sh' because that is what it will get."""
    if os == "linux" and shell is None:
        return "bash or sh"
    return SHELL_LABELS.get(effective_shell(os, shell), effective_shell(os, shell))


def shell_command(container_name: str, os: str = "linux", shell: str | None = None) -> list[str]:
    """The `docker exec -it …` argv for the node's declared OS and shell."""
    base = ["docker", "exec", "-it", container_name]
    if os == "windows":
        if effective_shell(os, shell) == "cmd":
            return [*base, *CMD_COMMAND]
        return [*base, *POWERSHELL_COMMAND]
    if shell == "bash":
        return [*base, "bash", "-l"]
    if shell == "sh":
        return [*base, "sh", "-l"]
    return [*base, "sh", "-c", SHELL_SELECTOR]


def container_state(container_name: str) -> str | None:
    """The container's Docker state ('running', 'exited', …), 'missing' when Docker says it
    does not exist, or None when Docker could not be asked (then the launch goes ahead and
    the console shows whatever Docker says)."""
    try:
        completed = subprocess.run(
            ["docker", "inspect", "--format", "{{.State.Status}}", container_name],
            capture_output=True,
            check=False,
            text=True,
            timeout=STATE_CHECK_TIMEOUT_SECONDS,
            creationflags=_NO_CONSOLE_WINDOW,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if completed.returncode != 0:
        message = (completed.stderr or completed.stdout or "").lower()
        if "no such" in message or "not found" in message:
            return "missing"
        return None
    return completed.stdout.strip() or None


def open_node_shell(
    container_name: str, node_id: str, os: str = "linux", shell: str | None = None
) -> ShellLaunchResult:
    """Launches a console window attached to `container_name`. Returns immediately."""
    docker_command = shell_command(container_name, os, shell)
    label = shell_label(os, shell)

    state = container_state(container_name)
    if state is not None and state != "running":
        what = "does not exist" if state == "missing" else f"is not running (state: {state})"
        return ShellLaunchResult(
            success=False,
            detail=(
                f"Cannot open {label} on '{node_id}': its container {what}. Start the lab "
                "(or Reset it if it is in an error state), wait until the node shows "
                "'running', then try again."
            ),
            command=docker_command,
        )

    try:
        if sys.platform == "win32":
            # `cmd /k` keeps the window open after docker exec exits, so an error such as
            # "container is not running" stays visible instead of flashing by.
            subprocess.Popen(
                ["cmd.exe", "/k", *docker_command],
                creationflags=getattr(subprocess, "CREATE_NEW_CONSOLE", 0),
            )
        else:
            terminal = next((t for t in LINUX_TERMINALS if shutil.which(t[0])), None)
            if terminal is None:
                return ShellLaunchResult(
                    success=False,
                    detail=(
                        f"No terminal emulator was found to open {label} on '{node_id}'. "
                        "Run this command in a terminal instead:"
                    ),
                    command=docker_command,
                )
            subprocess.Popen([*terminal, *docker_command])
    except OSError as exc:
        return ShellLaunchResult(
            success=False,
            detail=f"Could not open a {label} window for '{node_id}': {exc}",
            command=docker_command,
        )

    return ShellLaunchResult(success=True, detail=f"Opened {label} on '{node_id}' in a new window.")
