import subprocess

from practicum_desktop.docker_status import check_docker


def test_check_docker_reports_available_when_info_succeeds(monkeypatch) -> None:
    def fake_run(command, capture_output, check, text, timeout):
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(subprocess, "run", fake_run)

    status = check_docker()

    assert status.available is True


def test_check_docker_reports_unavailable_when_cli_cannot_run(monkeypatch) -> None:
    def fake_run(*args, **kwargs):
        raise PermissionError(13, "Permission denied", "docker")

    monkeypatch.setattr(subprocess, "run", fake_run)

    status = check_docker()

    assert status.available is False
    assert status.detail.startswith("Docker could not be run:")
    assert "Permission denied" in status.detail


def test_check_docker_reports_unavailable_when_cli_missing(monkeypatch) -> None:
    def fake_run(*args, **kwargs):
        raise FileNotFoundError("docker not found")

    monkeypatch.setattr(subprocess, "run", fake_run)

    status = check_docker()

    assert status.available is False
    assert "not installed" in status.detail


def test_check_docker_reports_unavailable_when_daemon_not_running(monkeypatch) -> None:
    def fake_run(command, capture_output, check, text, timeout):
        return subprocess.CompletedProcess(
            command, 1, "", "Cannot connect to the Docker daemon"
        )

    monkeypatch.setattr(subprocess, "run", fake_run)

    status = check_docker()

    assert status.available is False
    assert "Cannot connect" in status.detail


def test_check_docker_reports_unavailable_on_timeout(monkeypatch) -> None:
    def fake_run(command, capture_output, check, text, timeout):
        raise subprocess.TimeoutExpired(command, timeout)

    monkeypatch.setattr(subprocess, "run", fake_run)

    status = check_docker()

    assert status.available is False
