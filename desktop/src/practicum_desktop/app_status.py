from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from practicum_desktop.api_client import HealthStatus
from practicum_desktop.docker_status import (
    SWITCH_TO_LINUX_HINT,
    DockerStatus,
    WindowsContainerReadiness,
    windows_container_readiness,
)

Readiness = Literal["ready", "degraded", "blocked"]


@dataclass
class AppStatus:
    readiness: Readiness
    api: HealthStatus
    docker: DockerStatus
    next_action: str

    @property
    def windows_containers(self) -> WindowsContainerReadiness:
        """Whether Windows Quick Start can be used with the Docker state this status saw."""
        return windows_container_readiness(self.docker)


def evaluate_app_status(api: HealthStatus, docker: DockerStatus) -> AppStatus:
    """Combine API and Docker checks into one readiness state with an actionable next step."""
    if not api.healthy:
        if api.timed_out:
            next_action = (
                "The Practicum API is not answering in time. It may still be starting on a "
                "busy machine; wait a moment and select Retry."
            )
        else:
            next_action = (
                "Start the Practicum API (run start-practicum.bat, or "
                "`uvicorn practicum.main:app --reload`), then select Retry."
            )
        return AppStatus(readiness="blocked", api=api, docker=docker, next_action=next_action)

    if not docker.available:
        return AppStatus(
            readiness="degraded",
            api=api,
            docker=docker,
            next_action="Start Docker Desktop, then select Retry to run labs.",
        )

    if docker.os_type == "windows":
        # Fully usable - for Windows labs. Say so, because every Linux lab (the Ubuntu
        # templates, imported samples) will refuse to start until the mode is switched back.
        return AppStatus(
            readiness="ready",
            api=api,
            docker=docker,
            next_action=(
                "Docker Desktop is in Windows-container mode: Windows labs can run; Linux labs "
                f"(Ubuntu templates, most imported labs) cannot until you {SWITCH_TO_LINUX_HINT}."
            ),
        )

    return AppStatus(readiness="ready", api=api, docker=docker, next_action="")
