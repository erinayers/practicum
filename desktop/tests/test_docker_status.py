from __future__ import annotations

import subprocess

from practicum_desktop.docker_status import (
    DockerStatus,
    check_docker,
    check_windows_container_readiness,
    parse_docker_info,
    windows_container_readiness,
)

WINDOWS_INFO = (
    '{"ServerVersion":"27.3.1","OSType":"windows","OperatingSystem":"Windows 11 Pro Version '
    '23H2 (OS Build 22631.4460)","KernelVersion":"10.0 22631 (22621.1.amd64fre.ni_release'
    '.220506-1250)","Isolation":"hyperv","ServerErrors":null}'
)
LINUX_INFO = (
    '{"ServerVersion":"27.3.1","OSType":"linux","OperatingSystem":"Docker Desktop",'
    '"KernelVersion":"5.15.153.1-microsoft-standard-WSL2","ServerErrors":[]}'
)
DAEMON_DOWN_INFO = (
    '{"ServerVersion":"","OSType":"","ServerErrors":["error during connect: this error may '
    'indicate that the docker daemon is not running"]}'
)


def test_check_docker_runs_a_read_only_docker_info_and_reads_linux_mode(monkeypatch) -> None:
    commands: list[list[str]] = []

    def fake_run(command, **kwargs):
        commands.append(command)
        return subprocess.CompletedProcess(command, 0, LINUX_INFO, "")

    monkeypatch.setattr(subprocess, "run", fake_run)

    status = check_docker()

    assert commands == [["docker", "info", "--format", "{{json .}}"]]
    assert status.available is True
    assert status.os_type == "linux"
    assert status.server_version == "27.3.1"
    assert status.mode_label == "Linux containers"
    assert status.detail == "Docker is available (Linux containers, Docker 27.3.1)."


def test_check_docker_reads_windows_mode_with_host_build_and_isolation(monkeypatch) -> None:
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda command, **kw: subprocess.CompletedProcess(command, 0, WINDOWS_INFO, ""),
    )

    status = check_docker()

    assert status.available is True
    assert status.os_type == "windows"
    assert status.host_build == 22631
    assert status.isolation == "hyperv"
    assert status.operating_system.startswith("Windows 11 Pro")
    assert status.mode_label == "Windows containers"


def test_check_docker_reports_unavailable_when_cli_cannot_run(monkeypatch) -> None:
    def fake_run(*args, **kwargs):
        raise PermissionError(13, "Permission denied", "docker")

    monkeypatch.setattr(subprocess, "run", fake_run)

    status = check_docker()

    assert status.available is False
    assert status.detail.startswith("Docker could not be run:")
    assert "Permission denied" in status.detail
    assert status.os_type is None and status.mode_label == ""


def test_check_docker_reports_unavailable_when_cli_missing(monkeypatch) -> None:
    def fake_run(*args, **kwargs):
        raise FileNotFoundError("docker not found")

    monkeypatch.setattr(subprocess, "run", fake_run)

    status = check_docker()

    assert status.available is False
    assert "not installed" in status.detail


def test_check_docker_reports_unavailable_when_daemon_not_running(monkeypatch) -> None:
    def fake_run(command, **kwargs):
        return subprocess.CompletedProcess(command, 1, DAEMON_DOWN_INFO, "")

    monkeypatch.setattr(subprocess, "run", fake_run)

    status = check_docker()

    assert status.available is False
    assert "docker daemon is not running" in status.detail
    assert status.os_type is None


def test_check_docker_falls_back_to_stderr_without_json(monkeypatch) -> None:
    def fake_run(command, **kwargs):
        return subprocess.CompletedProcess(command, 1, "", "Cannot connect to the Docker daemon")

    monkeypatch.setattr(subprocess, "run", fake_run)

    status = check_docker()

    assert status.available is False
    assert "Cannot connect" in status.detail


def test_check_docker_reports_unavailable_on_timeout(monkeypatch) -> None:
    def fake_run(command, **kwargs):
        raise subprocess.TimeoutExpired(command, kwargs.get("timeout"))

    monkeypatch.setattr(subprocess, "run", fake_run)

    status = check_docker()

    assert status.available is False
    assert "did not respond in time" in status.detail


def test_parse_docker_info_treats_unknown_os_type_as_unavailable() -> None:
    status = parse_docker_info(0, '{"OSType":"plan9","ServerErrors":[]}', "")

    assert status.available is False


# ----- windows-container readiness (three states) ---------------------------------------------


def test_readiness_distinguishes_no_daemon_linux_engine_and_windows_engine() -> None:
    down = windows_container_readiness(DockerStatus(available=False, detail="not running"))
    assert down.state == "docker_unavailable"
    assert down.ready is False
    assert "not running" in down.detail
    assert "Start Docker Desktop" in down.next_action and "Retry" in down.next_action

    linux = windows_container_readiness(parse_docker_info(0, LINUX_INFO, ""))
    assert linux.state == "linux_engine"
    assert linux.ready is False
    assert "serving Linux containers" in linux.detail
    assert "Switch to Windows containers" in linux.next_action
    assert "never switches the mode" in linux.next_action  # Practicum does not do it itself

    windows = windows_container_readiness(parse_docker_info(0, WINDOWS_INFO, ""))
    assert windows.state == "ready"
    assert windows.ready is True
    assert "host build 22631" in windows.detail and "hyperv isolation" in windows.detail
    assert windows.next_action == ""


def test_check_windows_container_readiness_probes_once(monkeypatch) -> None:
    calls: list[list[str]] = []

    def fake_run(command, **kwargs):
        calls.append(command)
        return subprocess.CompletedProcess(command, 0, WINDOWS_INFO, "")

    monkeypatch.setattr(subprocess, "run", fake_run)

    readiness = check_windows_container_readiness()

    assert readiness.ready is True
    assert len(calls) == 1 and calls[0][:2] == ["docker", "info"]  # read-only; never a switch
