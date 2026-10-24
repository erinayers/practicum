from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from practicum_desktop.api_client import HealthStatus
from practicum_desktop.docker_status import DockerStatus

Readiness = Literal["ready", "degraded", "blocked"]


@dataclass
class AppStatus:
    readiness: Readiness
    api: HealthStatus
    docker: DockerStatus
    next_action: str


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

    return AppStatus(readiness="ready", api=api, docker=docker, next_action="")
