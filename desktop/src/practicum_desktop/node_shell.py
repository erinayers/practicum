"""Open an interactive shell inside a running lab node (windows-desktop-open-node-shell).

MVP: the shell runs in a new console window on the host (Windows: a fresh conhost/Terminal
window; elsewhere: the first terminal emulator found) using `docker exec`. Practicum never
asks the student to type the docker command themselves; when no console can be opened the
command is handed back so it can at least be copied.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from dataclasses import dataclass

# Prefer bash when the image has it (ubuntu, debian…), fall back to sh (alpine, busybox).
SHELL_SELECTOR = "command -v bash >/dev/null 2>&1 && exec bash || exec sh"

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


def shell_command(container_name: str) -> list[str]:
    return ["docker", "exec", "-it", container_name, "sh", "-c", SHELL_SELECTOR]


def open_node_shell(container_name: str, node_id: str) -> ShellLaunchResult:
    """Launches a console window attached to `container_name`. Returns immediately."""
    docker_command = shell_command(container_name)

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
                        f"No terminal emulator was found to open a shell on '{node_id}'. "
                        "Run this command in a terminal instead:"
                    ),
                    command=docker_command,
                )
            subprocess.Popen([*terminal, *docker_command])
    except OSError as exc:
        return ShellLaunchResult(
            success=False,
            detail=f"Could not open a shell window for '{node_id}': {exc}",
            command=docker_command,
        )

    return ShellLaunchResult(success=True, detail=f"Opened a shell on '{node_id}' in a new window.")
