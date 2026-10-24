from __future__ import annotations

import subprocess
from dataclasses import dataclass

DOCKER_CHECK_TIMEOUT_SECONDS = 5.0
_NO_CONSOLE_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


@dataclass
class DockerStatus:
    available: bool
    detail: str


def check_docker() -> DockerStatus:
    try:
        completed = subprocess.run(
            ["docker", "info"],
            capture_output=True,
            check=False,
            text=True,
            timeout=DOCKER_CHECK_TIMEOUT_SECONDS,
            creationflags=_NO_CONSOLE_WINDOW,
        )
    except FileNotFoundError:
        return DockerStatus(available=False, detail="Docker is not installed or not on PATH.")
    except OSError as exc:
        # e.g. PermissionError: the binary exists but cannot be executed. Must not escape,
        # or the startup worker thread dies and the window stays on "checking" forever.
        return DockerStatus(available=False, detail=f"Docker could not be run: {exc}")
    except subprocess.TimeoutExpired:
        return DockerStatus(
            available=False,
            detail="Docker did not respond in time. Is Docker Desktop starting up?",
        )

    if completed.returncode != 0:
        message = completed.stderr.strip() or completed.stdout.strip() or "Docker is installed but not running."
        return DockerStatus(available=False, detail=message)

    return DockerStatus(available=True, detail="Docker is available.")
