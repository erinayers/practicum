from practicum_desktop.api_client import HealthStatus
from practicum_desktop.app_status import evaluate_app_status
from practicum_desktop.docker_status import DockerStatus


def test_status_is_blocked_when_api_unhealthy() -> None:
    api = HealthStatus(reachable=False, healthy=False, detail="unreachable")
    docker = DockerStatus(available=True, detail="ok")

    status = evaluate_app_status(api, docker)

    assert status.readiness == "blocked"
    assert "uvicorn" in status.next_action
    assert "start-practicum.bat" in status.next_action


def test_timed_out_api_is_worded_as_slow_not_missing() -> None:
    api = HealthStatus(reachable=False, healthy=False, detail="slow", timed_out=True)
    docker = DockerStatus(available=True, detail="ok")

    status = evaluate_app_status(api, docker)

    assert status.readiness == "blocked"
    assert "not answering in time" in status.next_action
    assert "uvicorn" not in status.next_action


def test_status_is_degraded_when_docker_unavailable() -> None:
    api = HealthStatus(reachable=True, healthy=True, detail="ok")
    docker = DockerStatus(available=False, detail="not running")

    status = evaluate_app_status(api, docker)

    assert status.readiness == "degraded"
    assert "Docker Desktop" in status.next_action


def test_status_is_ready_when_both_available() -> None:
    api = HealthStatus(reachable=True, healthy=True, detail="ok")
    docker = DockerStatus(available=True, detail="ok")

    status = evaluate_app_status(api, docker)

    assert status.readiness == "ready"
    assert status.next_action == ""


def test_docker_takes_priority_only_when_api_is_healthy() -> None:
    api = HealthStatus(reachable=False, healthy=False, detail="unreachable")
    docker = DockerStatus(available=False, detail="not running")

    status = evaluate_app_status(api, docker)

    assert status.readiness == "blocked"


def test_windows_engine_is_ready_but_explains_that_linux_labs_cannot_run() -> None:
    api = HealthStatus(reachable=True, healthy=True, detail="ok")
    docker = DockerStatus(available=True, detail="ok", os_type="windows", host_build=22631)

    status = evaluate_app_status(api, docker)

    assert status.readiness == "ready"
    assert "Windows-container mode" in status.next_action
    assert "Switch to Linux containers" in status.next_action
    assert status.windows_containers.ready is True


def test_linux_engine_reports_windows_quick_start_as_not_ready() -> None:
    api = HealthStatus(reachable=True, healthy=True, detail="ok")
    docker = DockerStatus(available=True, detail="ok", os_type="linux")

    status = evaluate_app_status(api, docker)

    assert status.readiness == "ready" and status.next_action == ""
    assert status.windows_containers.state == "linux_engine"
