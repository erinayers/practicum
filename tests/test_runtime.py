import subprocess

from practicum.models import Lab, LabDefinition
from practicum.runtime import DockerRuntime, RuntimeFailure


def test_docker_runtime_creates_networks_and_containers(
    monkeypatch, lab_definition: dict
) -> None:
    commands: list[list[str]] = []

    def fake_run(
        command: list[str], capture_output: bool, check: bool, text: bool
    ) -> subprocess.CompletedProcess:
        commands.append(command)
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(subprocess, "run", fake_run)
    definition = LabDefinition.model_validate(lab_definition)
    lab = Lab(id="12345678-1234-1234-1234-123456789abc", **definition.model_dump())

    DockerRuntime().start(lab)

    network_commands = [command for command in commands if command[:3] == ["docker", "network", "create"]]
    run_commands = [command for command in commands if command[:2] == ["docker", "run"]]
    connect_commands = [
        command for command in commands if command[:3] == ["docker", "network", "connect"]
    ]

    assert len(network_commands) == 2
    assert "practicum-12345678-left" in network_commands[0]
    assert "practicum-12345678-right" in network_commands[1]
    assert ["--gateway", "10.0.1.254"] in [
        network_commands[0][index : index + 2] for index in range(len(network_commands[0]) - 1)
    ]
    assert ["--gateway", "10.0.2.254"] in [
        network_commands[1][index : index + 2] for index in range(len(network_commands[1]) - 1)
    ]
    assert len(run_commands) == 3
    assert "--cpus" in run_commands[0]
    assert "--memory" in run_commands[0]
    assert ["-p", "22:22"] in [
        run_commands[1][index : index + 2] for index in range(len(run_commands[1]) - 1)
    ]
    assert ["-p", "2222:22/tcp"] in [
        run_commands[1][index : index + 2] for index in range(len(run_commands[1]) - 1)
    ]
    assert len(connect_commands) == 1
    assert connect_commands[0][-2:] == ["practicum-12345678-right", "practicum-12345678-router"]


def test_docker_runtime_supports_browser_desktop_options(
    monkeypatch, lab_definition: dict
) -> None:
    commands: list[list[str]] = []

    def fake_run(
        command: list[str], capture_output: bool, check: bool, text: bool
    ) -> subprocess.CompletedProcess:
        commands.append(command)
        return subprocess.CompletedProcess(command, 0, "", "")

    lab_definition["nodes"] = [
        {
            "id": "ubuntu-desktop",
            "image": "lscr.io/linuxserver/webtop:ubuntu-xfce",
            "command": None,
            "environment": {"TITLE": "Practicum Ubuntu"},
            "resources": {
                "cpu": 2,
                "memory_mb": 2048,
                "shm_size_mb": 1024,
                "port_mappings": [
                    {"host": 3000, "container": 3000},
                    {"host": 3001, "container": 3001},
                ],
            },
        }
    ]
    lab_definition["networks"] = [{"id": "desktop", "subnet": "10.10.1.0/24"}]
    lab_definition["interfaces"] = [
        {"node": "ubuntu-desktop", "network": "desktop", "address": "10.10.1.10/24"}
    ]
    monkeypatch.setattr(subprocess, "run", fake_run)
    definition = LabDefinition.model_validate(lab_definition)
    lab = Lab(id="12345678-1234-1234-1234-123456789abc", **definition.model_dump())

    DockerRuntime().start(lab)

    run_command = next(command for command in commands if command[:2] == ["docker", "run"])
    assert ["--shm-size", "1024m"] in [
        run_command[index : index + 2] for index in range(len(run_command) - 1)
    ]
    assert ["-p", "3000:3000/tcp"] in [
        run_command[index : index + 2] for index in range(len(run_command) - 1)
    ]
    assert ["-p", "3001:3001/tcp"] in [
        run_command[index : index + 2] for index in range(len(run_command) - 1)
    ]
    assert ["-e", "TITLE=Practicum Ubuntu"] in [
        run_command[index : index + 2] for index in range(len(run_command) - 1)
    ]
    assert run_command[-1] == "lscr.io/linuxserver/webtop:ubuntu-xfce"


def test_docker_runtime_stops_containers(monkeypatch, lab_definition: dict) -> None:
    commands: list[list[str]] = []

    def fake_run(
        command: list[str], capture_output: bool, check: bool, text: bool
    ) -> subprocess.CompletedProcess:
        commands.append(command)
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(subprocess, "run", fake_run)
    definition = LabDefinition.model_validate(lab_definition)
    lab = Lab(id="12345678-1234-1234-1234-123456789abc", **definition.model_dump())

    DockerRuntime().stop(lab)

    assert commands == [
        ["docker", "stop", "practicum-12345678-host-a"],
        ["docker", "stop", "practicum-12345678-router"],
        ["docker", "stop", "practicum-12345678-host-b"],
    ]


def test_docker_runtime_resets_containers_and_networks(monkeypatch, lab_definition: dict) -> None:
    commands: list[list[str]] = []

    def fake_run(
        command: list[str], capture_output: bool, check: bool, text: bool
    ) -> subprocess.CompletedProcess:
        commands.append(command)
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(subprocess, "run", fake_run)
    definition = LabDefinition.model_validate(lab_definition)
    lab = Lab(id="12345678-1234-1234-1234-123456789abc", **definition.model_dump())

    DockerRuntime().reset(lab)

    assert commands == [
        ["docker", "rm", "-f", "practicum-12345678-host-a"],
        ["docker", "rm", "-f", "practicum-12345678-router"],
        ["docker", "rm", "-f", "practicum-12345678-host-b"],
        ["docker", "network", "rm", "practicum-12345678-left"],
        ["docker", "network", "rm", "practicum-12345678-right"],
    ]


def test_docker_runtime_reports_resource_status(monkeypatch, lab_definition: dict) -> None:
    def fake_run(
        command: list[str], capture_output: bool, check: bool, text: bool
    ) -> subprocess.CompletedProcess:
        if command[:3] == ["docker", "network", "inspect"]:
            return subprocess.CompletedProcess(command, 0, "", "")
        if command[:2] == ["docker", "inspect"]:
            return subprocess.CompletedProcess(command, 0, "running\n", "")
        raise AssertionError(f"Unexpected command: {command}")

    monkeypatch.setattr(subprocess, "run", fake_run)
    definition = LabDefinition.model_validate(lab_definition)
    lab = Lab(id="12345678-1234-1234-1234-123456789abc", **definition.model_dump())

    statuses = DockerRuntime().status(lab)

    assert statuses[0].model_dump() == {
        "kind": "network",
        "id": "left",
        "name": "practicum-12345678-left",
        "exists": True,
        "status": "present",
        "error": None,
    }
    assert statuses[2].model_dump() == {
        "kind": "container",
        "id": "host-a",
        "name": "practicum-12345678-host-a",
        "exists": True,
        "status": "running",
        "error": None,
    }


def test_docker_runtime_cleans_up_partial_start(monkeypatch, lab_definition: dict) -> None:
    commands: list[list[str]] = []

    def fake_run(
        command: list[str], capture_output: bool, check: bool, text: bool
    ) -> subprocess.CompletedProcess:
        commands.append(command)
        if command[:2] == ["docker", "run"] and "practicum-12345678-router" in command:
            return subprocess.CompletedProcess(
                command,
                1,
                "",
                "failed to set up container networking: Address already in use",
            )
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(subprocess, "run", fake_run)
    definition = LabDefinition.model_validate(lab_definition)
    lab = Lab(id="12345678-1234-1234-1234-123456789abc", **definition.model_dump())

    try:
        DockerRuntime().start(lab)
    except RuntimeFailure:
        pass
    else:
        raise AssertionError("Expected runtime failure")

    assert ["docker", "rm", "-f", "practicum-12345678-host-a"] in commands
    assert ["docker", "rm", "-f", "practicum-12345678-router"] in commands
    assert ["docker", "rm", "-f", "practicum-12345678-host-b"] in commands
    assert ["docker", "network", "rm", "practicum-12345678-left"] in commands
    assert ["docker", "network", "rm", "practicum-12345678-right"] in commands


def test_docker_runtime_removes_empty_practicum_network_with_same_subnet(
    monkeypatch, lab_definition: dict
) -> None:
    commands: list[list[str]] = []

    def fake_run(
        command: list[str], capture_output: bool, check: bool, text: bool
    ) -> subprocess.CompletedProcess:
        commands.append(command)
        if command[:3] == ["docker", "network", "ls"]:
            return subprocess.CompletedProcess(command, 0, "practicum-stale-left\n", "")
        if command[:3] == ["docker", "network", "inspect"]:
            return subprocess.CompletedProcess(
                command,
                0,
                '[{"Name":"practicum-stale-left","IPAM":{"Config":[{"Subnet":"10.0.1.0/24"}]},"Containers":{}}]',
                "",
            )
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(subprocess, "run", fake_run)
    definition = LabDefinition.model_validate(lab_definition)
    lab = Lab(id="12345678-1234-1234-1234-123456789abc", **definition.model_dump())

    DockerRuntime().start(lab)

    assert ["docker", "network", "rm", "practicum-stale-left"] in commands
    assert any(command[:3] == ["docker", "network", "create"] for command in commands)


def test_docker_runtime_reuses_existing_network_for_same_lab(
    monkeypatch, lab_definition: dict
) -> None:
    commands: list[list[str]] = []

    def fake_run(
        command: list[str], capture_output: bool, check: bool, text: bool
    ) -> subprocess.CompletedProcess:
        commands.append(command)
        if command[:3] == ["docker", "network", "ls"] and "name=^practicum-12345678-left$" in command:
            return subprocess.CompletedProcess(command, 0, "practicum-12345678-left\n", "")
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(subprocess, "run", fake_run)
    definition = LabDefinition.model_validate(lab_definition)
    lab = Lab(id="12345678-1234-1234-1234-123456789abc", **definition.model_dump())

    DockerRuntime().start(lab)

    create_commands = [command for command in commands if command[:3] == ["docker", "network", "create"]]
    assert len(create_commands) == 1
    assert "practicum-12345678-right" in create_commands[0]
    assert not any("practicum-12345678-left" in command for command in create_commands)


def test_docker_runtime_raises_actionable_error_on_pool_overlap(
    monkeypatch, lab_definition: dict
) -> None:
    def fake_run(
        command: list[str], capture_output: bool, check: bool, text: bool
    ) -> subprocess.CompletedProcess:
        if command[:3] == ["docker", "network", "create"]:
            return subprocess.CompletedProcess(
                command,
                1,
                "",
                "Error response from daemon: invalid pool request: "
                "pool overlaps with other one on this address space",
            )
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(subprocess, "run", fake_run)
    definition = LabDefinition.model_validate(lab_definition)
    lab = Lab(id="12345678-1234-1234-1234-123456789abc", **definition.model_dump())

    try:
        DockerRuntime().start(lab)
    except RuntimeFailure as exc:
        assert "overlaps with another Docker network" in exc.message
        assert "Stop or reset" in exc.message
        assert "pool overlaps with other one on this address space" in exc.message
    else:
        raise AssertionError("Expected runtime failure")


def test_docker_runtime_raises_when_docker_cli_missing(
    monkeypatch, lab_definition: dict
) -> None:
    def fake_run(*args, **kwargs) -> subprocess.CompletedProcess:
        raise FileNotFoundError("docker not found")

    monkeypatch.setattr(subprocess, "run", fake_run)
    definition = LabDefinition.model_validate(lab_definition)
    lab = Lab(id="12345678-1234-1234-1234-123456789abc", **definition.model_dump())

    try:
        DockerRuntime().stop(lab)
    except RuntimeFailure as exc:
        assert exc.message == "Docker CLI was not found"
    else:
        raise AssertionError("Expected runtime failure")


def test_docker_runtime_status_reports_missing_docker_cli(
    monkeypatch, lab_definition: dict
) -> None:
    def fake_run(*args, **kwargs) -> subprocess.CompletedProcess:
        raise FileNotFoundError("docker not found")

    monkeypatch.setattr(subprocess, "run", fake_run)
    definition = LabDefinition.model_validate(lab_definition)
    lab = Lab(id="12345678-1234-1234-1234-123456789abc", **definition.model_dump())

    statuses = DockerRuntime().status(lab)

    assert all(not resource.exists for resource in statuses)
    assert all(resource.error == "Docker CLI was not found" for resource in statuses)


def test_docker_runtime_stop_ignores_already_removed_containers(
    monkeypatch, lab_definition: dict
) -> None:
    commands: list[list[str]] = []

    def fake_run(
        command: list[str], capture_output: bool, check: bool, text: bool
    ) -> subprocess.CompletedProcess:
        commands.append(command)
        return subprocess.CompletedProcess(command, 1, "", "Error: No such container: missing")

    monkeypatch.setattr(subprocess, "run", fake_run)
    definition = LabDefinition.model_validate(lab_definition)
    lab = Lab(id="12345678-1234-1234-1234-123456789abc", **definition.model_dump())

    DockerRuntime().stop(lab)

    assert len(commands) == 3


def test_docker_runtime_reset_ignores_already_removed_resources(
    monkeypatch, lab_definition: dict
) -> None:
    commands: list[list[str]] = []

    def fake_run(
        command: list[str], capture_output: bool, check: bool, text: bool
    ) -> subprocess.CompletedProcess:
        commands.append(command)
        if command[:2] == ["docker", "rm"]:
            return subprocess.CompletedProcess(command, 1, "", "Error: No such container: missing")
        return subprocess.CompletedProcess(command, 1, "", "Error: No such network: missing")

    monkeypatch.setattr(subprocess, "run", fake_run)
    definition = LabDefinition.model_validate(lab_definition)
    lab = Lab(id="12345678-1234-1234-1234-123456789abc", **definition.model_dump())

    DockerRuntime().reset(lab)

    assert len(commands) == 5


def test_docker_runtime_raises_when_no_gateway_address_available(monkeypatch) -> None:
    commands: list[list[str]] = []

    def fake_run(
        command: list[str], capture_output: bool, check: bool, text: bool
    ) -> subprocess.CompletedProcess:
        commands.append(command)
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(subprocess, "run", fake_run)
    definition = LabDefinition.model_validate(
        {
            "name": "Tiny Network",
            "nodes": [
                {"id": "node-x", "image": "alpine:3.21"},
                {"id": "node-y", "image": "alpine:3.21"},
            ],
            "networks": [{"id": "tiny", "subnet": "10.0.9.0/30"}],
            "interfaces": [
                {"node": "node-x", "network": "tiny", "address": "10.0.9.1/30"},
                {"node": "node-y", "network": "tiny", "address": "10.0.9.2/30"},
            ],
        }
    )
    lab = Lab(id="12345678-1234-1234-1234-123456789abc", **definition.model_dump())

    try:
        DockerRuntime().start(lab)
    except RuntimeFailure as exc:
        assert "no available gateway address" in exc.message
    else:
        raise AssertionError("Expected runtime failure")

    assert not any(command[:3] == ["docker", "network", "create"] for command in commands)
