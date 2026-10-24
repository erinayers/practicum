import subprocess
from ipaddress import IPv4Network

import pytest

from practicum.models import DockerNetworkInfo, Lab, LabDefinition
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
        assert "Reset whichever other lab owns it" in exc.message
        assert "Stop is not enough" in exc.message
        assert "docker network ls --filter label=practicum.lab_id" in exc.message
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


def test_docker_runtime_reports_unrunnable_docker_cli_as_structured_failure(
    monkeypatch, lab_definition: dict
) -> None:
    """A docker binary that exists but cannot be executed (PermissionError, or any other
    OSError from subprocess) must surface as a RuntimeFailure, never as an HTTP 500."""

    def fake_run(*args, **kwargs) -> subprocess.CompletedProcess:
        raise PermissionError(13, "Permission denied", "docker")

    monkeypatch.setattr(subprocess, "run", fake_run)
    definition = LabDefinition.model_validate(lab_definition)
    lab = Lab(id="12345678-1234-1234-1234-123456789abc", **definition.model_dump())

    try:
        DockerRuntime().start(lab)
    except RuntimeFailure as exc:
        assert exc.message.startswith("Docker CLI could not be run:")
        assert "Permission denied" in exc.message
    else:
        raise AssertionError("Expected runtime failure")

    statuses = DockerRuntime().status(lab)
    assert all(not resource.exists for resource in statuses)
    assert all(resource.error.startswith("Docker CLI could not be run") for resource in statuses)


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


INSPECT_OUTPUT = (
    '[{"Name":"bridge","IPAM":{"Config":[{"Subnet":"172.17.0.0/16"}]},"Containers":{},'
    '"Labels":{}},'
    '{"Name":"practicum-deadbeef-lab-net","IPAM":{"Config":[{"Subnet":"10.50.0.0/24",'
    '"Gateway":"10.50.0.254"}]},'
    '"Containers":{"abc123":{"Name":"practicum-deadbeef-ubuntu"}},'
    '"Labels":{"practicum.lab_id":"deadbeef-0000-0000-0000-000000000000",'
    '"practicum.network_id":"lab-net"}},'
    '{"Name":"v6only","IPAM":{"Config":[{"Subnet":"fd00::/64"}]},"Containers":{},"Labels":{}}]'
)


def test_docker_runtime_lists_networks_with_subnets_labels_and_containers(monkeypatch) -> None:
    commands: list[list[str]] = []

    def fake_run(
        command: list[str], capture_output: bool, check: bool, text: bool
    ) -> subprocess.CompletedProcess:
        commands.append(command)
        if command[:3] == ["docker", "network", "ls"]:
            return subprocess.CompletedProcess(
                command, 0, "bridge\npracticum-deadbeef-lab-net\nv6only\n", ""
            )
        if command[:3] == ["docker", "network", "inspect"]:
            return subprocess.CompletedProcess(command, 0, INSPECT_OUTPUT, "")
        raise AssertionError(f"unexpected command {command}")

    monkeypatch.setattr(subprocess, "run", fake_run)

    networks = DockerRuntime().list_networks()

    assert commands[0] == ["docker", "network", "ls", "--format", "{{.Name}}"]
    assert commands[1] == [
        "docker", "network", "inspect", "bridge", "practicum-deadbeef-lab-net", "v6only"
    ]
    by_name = {network.name: network for network in networks}
    assert str(by_name["bridge"].subnets[0]) == "172.17.0.0/16"
    assert by_name["bridge"].lab_id is None
    leftover = by_name["practicum-deadbeef-lab-net"]
    assert str(leftover.subnets[0]) == "10.50.0.0/24"
    assert leftover.lab_id == "deadbeef-0000-0000-0000-000000000000"
    assert leftover.container_names == ["practicum-deadbeef-ubuntu"]
    assert by_name["v6only"].subnets == []  # IPv6 pools are ignored


def test_docker_runtime_list_networks_is_empty_when_docker_has_none(monkeypatch) -> None:
    def fake_run(command, capture_output, check, text) -> subprocess.CompletedProcess:
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(subprocess, "run", fake_run)

    assert DockerRuntime().list_networks() == []


def test_docker_runtime_list_networks_raises_when_docker_unavailable(monkeypatch) -> None:
    def fake_run(command, capture_output, check, text) -> subprocess.CompletedProcess:
        return subprocess.CompletedProcess(
            command, 1, "", "error during connect: Docker Desktop is not running"
        )

    monkeypatch.setattr(subprocess, "run", fake_run)

    with pytest.raises(RuntimeFailure) as exc_info:
        DockerRuntime().list_networks()

    assert "Docker Desktop is not running" in exc_info.value.message


def test_docker_runtime_remove_network_removes_containers_then_network(monkeypatch) -> None:
    commands: list[list[str]] = []

    def fake_run(command, capture_output, check, text) -> subprocess.CompletedProcess:
        commands.append(command)
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(subprocess, "run", fake_run)
    network = DockerNetworkInfo(
        name="practicum-deadbeef-lab-net",
        subnets=[IPv4Network("10.50.0.0/24")],
        lab_id="deadbeef-0000-0000-0000-000000000000",
        container_names=["practicum-deadbeef-ubuntu", "practicum-deadbeef-router"],
    )

    DockerRuntime().remove_network(network)

    assert commands == [
        ["docker", "rm", "-f", "practicum-deadbeef-ubuntu"],
        ["docker", "rm", "-f", "practicum-deadbeef-router"],
        ["docker", "network", "rm", "practicum-deadbeef-lab-net"],
    ]


def test_docker_runtime_remove_network_tolerates_already_gone_resources(monkeypatch) -> None:
    def fake_run(command, capture_output, check, text) -> subprocess.CompletedProcess:
        if command[:2] == ["docker", "rm"]:
            return subprocess.CompletedProcess(command, 1, "", "Error: No such container: x")
        return subprocess.CompletedProcess(command, 1, "", "Error: No such network: y")

    monkeypatch.setattr(subprocess, "run", fake_run)
    network = DockerNetworkInfo(name="y", container_names=["x"])

    DockerRuntime().remove_network(network)  # must not raise
