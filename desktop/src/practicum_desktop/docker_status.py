"""Read-only Docker probe for the desktop's connection status and the Windows-container
readiness check (windows-desktop-windows-container-readiness).

`check_docker()` runs one `docker info` and reports whether the daemon answers and which
kind of container it serves - Docker Desktop runs *either* Linux or Windows containers,
switched by the user from the Docker whale menu. Practicum only reads that mode; it never
switches it (the switch is machine-wide, restarts the engine and may stop other people's
containers).
"""

from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass
from typing import Literal

DOCKER_CHECK_TIMEOUT_SECONDS = 5.0
_NO_CONSOLE_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
_KERNEL_BUILD = re.compile(r"^10\.0 (\d{4,6})\b")

OS_LABELS = {"linux": "Linux", "windows": "Windows"}

# Where Docker and Microsoft keep the current requirements; they change per release, so the
# app links to them instead of restating them.
DOCKER_WINDOWS_INSTALL_URL = "https://docs.docker.com/desktop/setup/install/windows-install/"
WINDOWS_CONTAINER_COMPATIBILITY_URL = (
    "https://learn.microsoft.com/en-us/virtualization/windowscontainers/deploy-containers/"
    "version-compatibility"
)
SWITCH_TO_WINDOWS_HINT = (
    "right-click the Docker whale icon in the notification area and choose "
    "'Switch to Windows containers...'"
)
SWITCH_TO_LINUX_HINT = (
    "right-click the Docker whale icon in the notification area and choose "
    "'Switch to Linux containers...'"
)


@dataclass
class DockerStatus:
    available: bool
    detail: str
    os_type: str | None = None  # "linux" | "windows" - what the daemon serves; None if unknown
    server_version: str | None = None
    operating_system: str | None = None
    host_build: int | None = None  # Windows build of the daemon host (Windows mode only)
    isolation: str | None = None  # Windows: "process" | "hyperv"

    @property
    def mode_label(self) -> str:
        """'Linux containers' / 'Windows containers' / '' when unknown."""
        return f"{OS_LABELS[self.os_type]} containers" if self.os_type in OS_LABELS else ""


WindowsReadinessState = Literal["docker_unavailable", "linux_engine", "ready"]


@dataclass
class WindowsContainerReadiness:
    """Whether a Windows Quick Start can be created/started right now, and what to do if
    not. Three states, as the story requires: no daemon, a Linux-container daemon, a
    Windows-container daemon."""

    state: WindowsReadinessState
    detail: str  # what was detected, in plain words
    next_action: str  # what the user must do (empty when ready)
    docker: DockerStatus

    @property
    def ready(self) -> bool:
        return self.state == "ready"


def parse_docker_info(returncode: int, stdout: str, stderr: str) -> DockerStatus:
    """Interprets `docker info --format '{{json .}}'`. With the daemon down the CLI still
    prints the client half (with `ServerErrors`) and exits 1; with no JSON at all the
    stderr text is the reason."""
    try:
        raw = json.loads(stdout or "")
    except json.JSONDecodeError:
        raw = None
    if not isinstance(raw, dict):
        message = (stderr or stdout or "").strip() or "Docker is installed but not running."
        return DockerStatus(available=False, detail=message)

    server_errors = [str(e) for e in raw.get("ServerErrors") or [] if e]
    os_type = str(raw.get("OSType") or "").lower() or None
    if server_errors or os_type not in OS_LABELS:
        message = "; ".join(server_errors) or (stderr or "").strip()
        return DockerStatus(
            available=False, detail=message or "Docker is installed but not running."
        )

    version = str(raw.get("ServerVersion") or "") or None
    host_build: int | None = None
    if os_type == "windows":
        match = _KERNEL_BUILD.match(str(raw.get("KernelVersion") or ""))
        if match:
            host_build = int(match.group(1))
    isolation = str(raw.get("Isolation") or "").lower() or None
    detail = f"Docker is available ({OS_LABELS[os_type]} containers"
    if version:
        detail += f", Docker {version}"
    detail += ")."
    return DockerStatus(
        available=True,
        detail=detail,
        os_type=os_type,
        server_version=version,
        operating_system=str(raw.get("OperatingSystem") or "") or None,
        host_build=host_build,
        isolation=isolation,
    )


def check_docker() -> DockerStatus:
    try:
        completed = subprocess.run(
            ["docker", "info", "--format", "{{json .}}"],
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

    return parse_docker_info(completed.returncode, completed.stdout, completed.stderr)


def windows_container_readiness(docker: DockerStatus) -> WindowsContainerReadiness:
    """Turns a Docker probe into the Windows Quick Start readiness verdict."""
    if not docker.available:
        return WindowsContainerReadiness(
            state="docker_unavailable",
            detail=f"Docker is not reachable: {docker.detail}",
            next_action=(
                "Start Docker Desktop (it must be installed in a mode that supports Windows "
                "containers - see Docker's Windows requirements), then select Retry."
            ),
            docker=docker,
        )
    if docker.os_type != "windows":
        return WindowsContainerReadiness(
            state="linux_engine",
            detail="Docker Desktop is currently serving Linux containers.",
            next_action=(
                "Windows Quick Start needs Docker Desktop in Windows-container mode: "
                f"{SWITCH_TO_WINDOWS_HINT}, wait for Docker to restart, then select Retry. "
                "Practicum never switches the mode for you - it affects every container on "
                "this computer and may require administrator approval."
            ),
            docker=docker,
        )
    detail = "Docker Desktop is serving Windows containers"
    extras = []
    if docker.host_build:
        extras.append(f"host build {docker.host_build}")
    if docker.isolation:
        extras.append(f"{docker.isolation} isolation")
    if extras:
        detail += f" ({', '.join(extras)})"
    return WindowsContainerReadiness(
        state="ready", detail=detail + ".", next_action="", docker=docker
    )


def check_windows_container_readiness() -> WindowsContainerReadiness:
    """One read-only probe + verdict; what Retry runs."""
    return windows_container_readiness(check_docker())
