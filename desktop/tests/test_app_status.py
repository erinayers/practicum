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
