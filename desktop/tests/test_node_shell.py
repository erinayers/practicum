from __future__ import annotations

import subprocess

from practicum_desktop import node_shell
from practicum_desktop.node_shell import SHELL_SELECTOR, open_node_shell, shell_command


def test_shell_command_prefers_bash_and_falls_back_to_sh() -> None:
    command = shell_command("practicum-abc-host-a")

    assert command[:4] == ["docker", "exec", "-it", "practicum-abc-host-a"]
    assert command[4:6] == ["sh", "-c"]
    assert "exec bash" in SHELL_SELECTOR and "exec sh" in SHELL_SELECTOR


def test_open_node_shell_on_windows_uses_a_new_console_kept_open(monkeypatch) -> None:
    calls: list[tuple[list[str], dict]] = []
    monkeypatch.setattr(node_shell.sys, "platform", "win32")
    monkeypatch.setattr(subprocess, "CREATE_NEW_CONSOLE", 16, raising=False)
    monkeypatch.setattr(subprocess, "Popen", lambda args, **kw: calls.append((args, kw)))

    result = open_node_shell("practicum-abc-host-a", "host-a")

    assert result.success is True
    assert "host-a" in result.detail
    args, kwargs = calls[0]
    assert args[:2] == ["cmd.exe", "/k"]
    assert args[2:6] == ["docker", "exec", "-it", "practicum-abc-host-a"]
    assert kwargs["creationflags"] == 16


def test_open_node_shell_on_linux_uses_first_available_terminal(monkeypatch) -> None:
    calls: list[list[str]] = []
    monkeypatch.setattr(node_shell.sys, "platform", "linux")
    monkeypatch.setattr(node_shell.shutil, "which", lambda name: name == "xterm" or None)
    monkeypatch.setattr(subprocess, "Popen", lambda args, **kw: calls.append(args))

    result = open_node_shell("practicum-abc-host-a", "host-a")

    assert result.success is True
    assert calls[0][:2] == ["xterm", "-e"]
    assert calls[0][2:5] == ["docker", "exec", "-it"]


def test_open_node_shell_without_terminal_returns_command_to_copy(monkeypatch) -> None:
    monkeypatch.setattr(node_shell.sys, "platform", "linux")
    monkeypatch.setattr(node_shell.shutil, "which", lambda name: None)

    result = open_node_shell("practicum-abc-host-a", "host-a")

    assert result.success is False
    assert "No terminal emulator" in result.detail
    assert result.command == shell_command("practicum-abc-host-a")


def test_open_node_shell_reports_launch_errors(monkeypatch) -> None:
    def failing_popen(args, **kwargs):
        raise OSError("docker.exe not found")

    monkeypatch.setattr(node_shell.sys, "platform", "win32")
    monkeypatch.setattr(subprocess, "Popen", failing_popen)

    result = open_node_shell("practicum-abc-host-a", "host-a")

    assert result.success is False
    assert "docker.exe not found" in result.detail
    assert result.command is not None
