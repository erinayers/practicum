from __future__ import annotations

from PySide6.QtCore import Signal

from practicum_desktop.api_client import ApiClient, HealthStatus, LabsResult
from practicum_desktop.app_status import AppStatus, evaluate_app_status
from practicum_desktop.docker_status import check_docker
from practicum_desktop.workers import ManagedThread

# A cold or loaded machine (Docker Desktop booting at the same time) can make the API miss
# a single 3 s probe while it is perfectly healthy (Tigre/06 #11). Retry with longer
# timeouts before declaring the app Blocked; a refused connection is not retried.
HEALTH_TIMEOUTS: tuple[float, ...] = (3.0, 6.0, 10.0)


class StartupWorker(ManagedThread):
    """Runs API and Docker checks off the UI thread and reports back via a signal."""

    finished_check = Signal(object, object)

    def __init__(self, api_client: ApiClient, parent=None) -> None:
        super().__init__(parent)
        self.api_client = api_client

    def run(self) -> None:
        health = check_health_with_retries(self.api_client)
        docker = check_docker()
        status: AppStatus = evaluate_app_status(health, docker)

        labs_result: LabsResult | None = None
        if status.readiness in ("ready", "degraded"):
            labs_result = self.api_client.list_labs()

        self.finished_check.emit(status, labs_result)


def check_health_with_retries(
    api_client: ApiClient, timeouts: tuple[float, ...] = HEALTH_TIMEOUTS
) -> HealthStatus:
    """Probes /health, retrying only timeouts (slow API) with progressively longer waits."""
    health = api_client.check_health(timeout=timeouts[0])
    for timeout in timeouts[1:]:
        if not health.timed_out:
            break
        health = api_client.check_health(timeout=timeout)
    return health
