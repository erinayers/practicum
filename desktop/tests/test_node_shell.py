from __future__ import annotations

import subprocess

from practicum_desktop import node_shell
from practicum_desktop.node_shell import (
    POWERSHELL_COMMAND,
    SHELL_SELECTOR,
    container_state,
    open_node_shell,
    shell_command,
    shell_label,
)


def test_shell_command_prefers_bash_and_falls_back_to_sh() -> None:
    command = shell_command("practicum-abc-host-a")

    assert command[:4] == ["docker", "exec", "-it", "practicum-abc-host-a"]
    assert command[4:6] == ["sh", "-c"]
    assert "exec bash" in SHELL_SELECTOR and "exec sh" in SHELL_SELECTOR


def test_shell_command_honours_a_declared_linux_shell() -> None:
    assert shell_command("c", "linux", "bash")[4:] == ["bash", "-l"]
    assert shell_command("c", "linux", "sh")[4:] == ["sh", "-l"]
    assert shell_label("linux") == "bash or sh"
    assert shell_label("linux", "sh") == "sh"


def test_shell_command_uses_powershell_for_windows_nodes() -> None:
    command = shell_command("practicum-abc-host", "windows")

    assert command[:4] == ["docker", "exec", "-it", "practicum-abc-host"]
    assert command[4:] == POWERSHELL_COMMAND
    assert command[4] == "powershell.exe"
    assert "-ExecutionPolicy" in command and "Bypass" in command  # the profile prints the status
    assert not any(" " in part or '"' in part for part in command)  # survives cmd /k quoting
    assert shell_label("windows") == "PowerShell"
    assert shell_command("c", "windows", "cmd")[4:] == ["cmd.exe"]
    assert shell_label("windows", "cmd") == "Command Prompt"


def test_open_node_shell_on_windows_uses_a_new_console_kept_open(monkeypatch) -> None:
    calls: list[tuple[list[str], dict]] = []
    monkeypatch.setattr(node_shell, "container_state", lambda name: "running")
    monkeypatch.setattr(node_shell.sys, "platform", "win32")
    monkeypatch.setattr(subprocess, "CREATE_NEW_CONSOLE", 16, raising=False)
    monkeypatch.setattr(subprocess, "Popen", lambda args, **kw: calls.append((args, kw)))

    result = open_node_shell("practicum-abc-host-a", "host-a")

    assert result.success is True
    assert result.detail == "Opened bash or sh on 'host-a' in a new window."
    args, kwargs = calls[0]
    assert args[:2] == ["cmd.exe", "/k"]
    assert args[2:6] == ["docker", "exec", "-it", "practicum-abc-host-a"]
    assert kwargs["creationflags"] == 16


def test_open_node_shell_on_a_windows_node_launches_powershell(monkeypatch) -> None:
    calls: list[list[str]] = []
    monkeypatch.setattr(node_shell, "container_state", lambda name: "running")
    monkeypatch.setattr(node_shell.sys, "platform", "win32")
    monkeypatch.setattr(subprocess, "Popen", lambda args, **kw: calls.append(args))

    result = open_node_shell("practicum-abc-host", "host", "windows", "powershell")

    assert result.success is True
    assert result.detail == "Opened PowerShell on 'host' in a new window."
    assert calls[0][:2] == ["cmd.exe", "/k"]
    assert calls[0][2:] == ["docker", "exec", "-it", "practicum-abc-host", *POWERSHELL_COMMAND]


def test_open_node_shell_on_linux_uses_first_available_terminal(monkeypatch) -> None:
    calls: list[list[str]] = []
    monkeypatch.setattr(node_shell, "container_state", lambda name: None)  # Docker unknown
    monkeypatch.setattr(node_shell.sys, "platform", "linux")
    monkeypatch.setattr(node_shell.shutil, "which", lambda name: name == "xterm" or None)
    monkeypatch.setattr(subprocess, "Popen", lambda args, **kw: calls.append(args))

    result = open_node_shell("practicum-abc-host-a", "host-a")

    assert result.success is True
    assert calls[0][:2] == ["xterm", "-e"]
    assert calls[0][2:5] == ["docker", "exec", "-it"]


def test_open_node_shell_without_terminal_returns_command_to_copy(monkeypatch) -> None:
    monkeypatch.setattr(node_shell, "container_state", lambda name: "running")
    monkeypatch.setattr(node_shell.sys, "platform", "linux")
    monkeypatch.setattr(node_shell.shutil, "which", lambda name: None)

    result = open_node_shell("practicum-abc-host-a", "host-a")

    assert result.success is False
    assert "No terminal emulator" in result.detail
    assert result.command == shell_command("practicum-abc-host-a")


def test_open_node_shell_reports_launch_errors(monkeypatch) -> None:
    def failing_popen(args, **kwargs):
        raise OSError("docker.exe not found")

    monkeypatch.setattr(node_shell, "container_state", lambda name: "running")
    monkeypatch.setattr(node_shell.sys, "platform", "win32")
    monkeypatch.setattr(subprocess, "Popen", failing_popen)

    result = open_node_shell("practicum-abc-host-a", "host-a", "windows")

    assert result.success is False
    assert "PowerShell window" in result.detail
    assert "docker.exe not found" in result.detail
    assert result.command is not None


def test_open_node_shell_refuses_a_stopped_or_missing_container(monkeypatch) -> None:
    popen_calls: list[list[str]] = []
    monkeypatch.setattr(subprocess, "Popen", lambda args, **kw: popen_calls.append(args))
    monkeypatch.setattr(node_shell.sys, "platform", "win32")

    monkeypatch.setattr(node_shell, "container_state", lambda name: "exited")
    stopped = open_node_shell("practicum-abc-host", "host", "windows")
    assert stopped.success is False
    assert "Cannot open PowerShell on 'host'" in stopped.detail
    assert "not running (state: exited)" in stopped.detail
    assert "Start the lab" in stopped.detail

    monkeypatch.setattr(node_shell, "container_state", lambda name: "missing")
    missing = open_node_shell("practicum-abc-host", "host", "windows")
    assert missing.success is False
    assert "does not exist" in missing.detail
    assert missing.command == shell_command("practicum-abc-host", "windows")

    assert popen_calls == []  # no console window flashed open for either


def test_container_state_reads_docker_inspect(monkeypatch) -> None:
    def fake_run(command, **kwargs):
        assert command[:3] == ["docker", "inspect", "--format"]
        return subprocess.CompletedProcess(command, 0, "running\n", "")

    monkeypatch.setattr(subprocess, "run", fake_run)
    assert container_state("practicum-abc-host") == "running"

    monkeypatch.setattr(
        subprocess,
        "run",
        lambda command, **kw: subprocess.CompletedProcess(
            command, 1, "", "Error: No such object: practicum-abc-host"
        ),
    )
    assert container_state("practicum-abc-host") == "missing"

    monkeypatch.setattr(
        subprocess,
        "run",
        lambda command, **kw: subprocess.CompletedProcess(
            command, 1, "", "Cannot connect to the Docker daemon"
        ),
    )
    assert container_state("practicum-abc-host") is None

    def failing_run(*args, **kwargs):
        raise FileNotFoundError("docker")

    monkeypatch.setattr(subprocess, "run", failing_run)
    assert container_state("practicum-abc-host") is None
