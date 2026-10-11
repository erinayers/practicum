from __future__ import annotations

from PySide6.QtCore import QThread, Signal

from practicum_desktop.api_client import ApiClient, LabsResult
from practicum_desktop.app_status import AppStatus, evaluate_app_status
from practicum_desktop.docker_status import check_docker


class StartupWorker(QThread):
    """Runs API and Docker checks off the UI thread and reports back via a signal."""

    finished_check = Signal(object, object)

    def __init__(self, api_client: ApiClient, parent=None) -> None:
        super().__init__(parent)
        self.api_client = api_client

    def run(self) -> None:
        health = self.api_client.check_health()
        docker = check_docker()
        status: AppStatus = evaluate_app_status(health, docker)

        labs_result: LabsResult | None = None
        if status.readiness in ("ready", "degraded"):
            labs_result = self.api_client.list_labs()

        self.finished_check.emit(status, labs_result)
