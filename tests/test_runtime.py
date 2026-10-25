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
        command: list[str], capture_output: bool, check: bool, text: bool, **kwargs
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
        command: list[str], capture_output: bool, check: bool, text: bool, **kwargs
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
        command: list[str], capture_output: bool, check: bool, text: bool, **kwargs
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
        command: list[str], capture_output: bool, check: bool, text: bool, **kwargs
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
        command: list[str], capture_output: bool, check: bool, text: bool, timeout=None, **kwargs
    ) -> subprocess.CompletedProcess:
        if command[:3] == ["docker", "network", "inspect"]:
            return subprocess.CompletedProcess(command, 0, "", "")
        if command[:2] == ["docker", "inspect"]:
            return subprocess.CompletedProcess(command, 0, "running\n", "")
        if command[:2] == ["docker", "exec"]:  # the self-reported status marker
            if "host-a" in command[2]:
                return subprocess.CompletedProcess(
                    command, 0, "Practicum: installing packages (git) - wait\nmore\n", ""
                )
            return subprocess.CompletedProcess(command, 1, "", "cat: no such file")
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
        "note": None,
    }
    assert statuses[2].model_dump() == {
        "kind": "container",
        "id": "host-a",
        "name": "practicum-12345678-host-a",
        "exists": True,
        "status": "running",
        "error": None,
        "note": "Practicum: installing packages (git) - wait",
    }
    assert statuses[3].note is None  # no marker file in that container


def test_docker_runtime_cleans_up_partial_start(monkeypatch, lab_definition: dict) -> None:
    commands: list[list[str]] = []

    def fake_run(
        command: list[str], capture_output: bool, check: bool, text: bool, **kwargs
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
        command: list[str], capture_output: bool, check: bool, text: bool, **kwargs
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
        command: list[str], capture_output: bool, check: bool, text: bool, **kwargs
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
        command: list[str], capture_output: bool, check: bool, text: bool, **kwargs
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
        command: list[str], capture_output: bool, check: bool, text: bool, **kwargs
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
        command: list[str], capture_output: bool, check: bool, text: bool, **kwargs
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
        command: list[str], capture_output: bool, check: bool, text: bool, **kwargs
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
        command: list[str], capture_output: bool, check: bool, text: bool, **kwargs
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
    def fake_run(command, capture_output, check, text, **kwargs) -> subprocess.CompletedProcess:
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(subprocess, "run", fake_run)

    assert DockerRuntime().list_networks() == []


def test_docker_runtime_list_networks_raises_when_docker_unavailable(monkeypatch) -> None:
    def fake_run(command, capture_output, check, text, **kwargs) -> subprocess.CompletedProcess:
        return subprocess.CompletedProcess(
            command, 1, "", "error during connect: Docker Desktop is not running"
        )

    monkeypatch.setattr(subprocess, "run", fake_run)

    with pytest.raises(RuntimeFailure) as exc_info:
        DockerRuntime().list_networks()

    assert "Docker Desktop is not running" in exc_info.value.message


def test_docker_runtime_remove_network_removes_containers_then_network(monkeypatch) -> None:
    commands: list[list[str]] = []

    def fake_run(command, capture_output, check, text, **kwargs) -> subprocess.CompletedProcess:
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
    def fake_run(command, capture_output, check, text, **kwargs) -> subprocess.CompletedProcess:
        if command[:2] == ["docker", "rm"]:
            return subprocess.CompletedProcess(command, 1, "", "Error: No such container: x")
        return subprocess.CompletedProcess(command, 1, "", "Error: No such network: y")

    monkeypatch.setattr(subprocess, "run", fake_run)
    network = DockerNetworkInfo(name="y", container_names=["x"])

    DockerRuntime().remove_network(network)  # must not raise


# ----- start after stop, image pull progress (runtime-image-pull-progress) ------------------


def _lab(lab_definition: dict) -> Lab:
    definition = LabDefinition.model_validate(lab_definition)
    return Lab(id="12345678-1234-1234-1234-123456789abc", **definition.model_dump())


def test_docker_runtime_restarts_existing_containers_instead_of_recreating(
    monkeypatch, lab_definition: dict
) -> None:
    commands: list[list[str]] = []

    def fake_run(command, capture_output, check, text, **kwargs) -> subprocess.CompletedProcess:
        commands.append(command)
        if command[:2] == ["docker", "inspect"]:
            return subprocess.CompletedProcess(command, 0, "exited\n", "")  # left by Stop
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(subprocess, "run", fake_run)

    DockerRuntime().start(_lab(lab_definition))

    assert [c for c in commands if c[:2] == ["docker", "run"]] == []
    assert [c for c in commands if c[:3] == ["docker", "network", "connect"]] == []
    assert [c for c in commands if c[:2] == ["docker", "start"]] == [
        ["docker", "start", "practicum-12345678-host-a"],
        ["docker", "start", "practicum-12345678-router"],
        ["docker", "start", "practicum-12345678-host-b"],
    ]


def test_docker_runtime_checks_image_locally_and_skips_pull_when_present(
    monkeypatch, lab_definition: dict
) -> None:
    commands: list[list[str]] = []
    popen_calls: list[list[str]] = []

    def fake_run(command, capture_output, check, text, **kwargs) -> subprocess.CompletedProcess:
        commands.append(command)
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(subprocess, "run", fake_run)
    monkeypatch.setattr(subprocess, "Popen", lambda *a, **k: popen_calls.append(a[0]))
    steps: list[tuple[str, str]] = []

    DockerRuntime().start(_lab(lab_definition), lambda p: steps.append((p.node_id, p.step)))

    assert ["docker", "image", "inspect", "--format", "{{.Id}}", "alpine:3.21"] in commands
    assert popen_calls == []  # no `docker pull`
    assert steps == [
        ("host-a", "checking_image"),
        ("host-a", "creating_container"),
        ("host-a", "ready"),
        ("router", "checking_image"),
        ("router", "creating_container"),
        ("router", "connecting_networks"),
        ("router", "ready"),
        ("host-b", "checking_image"),
        ("host-b", "creating_container"),
        ("host-b", "ready"),
    ]


class FakePullProcess:
    def __init__(self, lines: list[str], returncode: int = 0) -> None:
        self.stdout = iter(line + "\n" for line in lines)
        self.returncode = returncode

    def wait(self) -> int:
        return self.returncode


def test_docker_runtime_pulls_missing_image_and_reports_layer_progress(
    monkeypatch, lab_definition: dict
) -> None:
    lab_definition["nodes"] = [lab_definition["nodes"][0]]
    lab_definition["networks"] = [lab_definition["networks"][0]]
    lab_definition["interfaces"] = [lab_definition["interfaces"][0]]
    pull_output = [
        "3.21: Pulling from library/alpine",
        "aaaaaaaaaaaa: Pulling fs layer",
        "bbbbbbbbbbbb: Pulling fs layer",
        "aaaaaaaaaaaa: Downloading [=====>                                             ]  1MB/2MB",
        "aaaaaaaaaaaa: Download complete",
        "aaaaaaaaaaaa: Pull complete",
        "bbbbbbbbbbbb: Already exists",
        "Digest: sha256:abc",
        "Status: Downloaded newer image for alpine:3.21",
    ]
    popen_calls: list[list[str]] = []

    def fake_run(command, capture_output, check, text, **kwargs) -> subprocess.CompletedProcess:
        if command[:3] == ["docker", "image", "inspect"]:
            return subprocess.CompletedProcess(command, 1, "", "Error: No such image: alpine:3.21")
        return subprocess.CompletedProcess(command, 0, "", "")

    def fake_popen(command, **kwargs):
        popen_calls.append(command)
        return FakePullProcess(pull_output)

    monkeypatch.setattr(subprocess, "run", fake_run)
    monkeypatch.setattr(subprocess, "Popen", fake_popen)
    reports = []

    DockerRuntime().start(_lab(lab_definition), lambda p: reports.append(p.model_copy()))

    assert popen_calls == [["docker", "pull", "alpine:3.21"]]
    pulling = [(r.percent, r.detail) for r in reports if r.step == "pulling_image"]
    assert pulling[0] == (0, "starting download")
    assert pulling[-1] == (100, "download complete")
    percents = [p for p, _ in pulling]
    assert percents == sorted(percents)  # never goes backwards
    assert (18, "0 of 2 layers") in pulling  # 1MB/2MB of one of two layers, downloading = 70 %
    assert (50, "1 of 2 layers") in pulling
    assert reports[-1].step == "ready"


def test_docker_runtime_attributes_pull_failure_to_the_node(
    monkeypatch, lab_definition: dict
) -> None:
    commands: list[list[str]] = []

    def fake_run(command, capture_output, check, text, **kwargs) -> subprocess.CompletedProcess:
        commands.append(command)
        if command[:3] == ["docker", "image", "inspect"]:
            return subprocess.CompletedProcess(command, 1, "", "Error: No such image")
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(subprocess, "run", fake_run)
    monkeypatch.setattr(
        subprocess,
        "Popen",
        lambda command, **kwargs: FakePullProcess(
            ["Error response from daemon: manifest for alpine:3.21 not found"], returncode=1
        ),
    )
    reports = []

    with pytest.raises(RuntimeFailure) as excinfo:
        DockerRuntime().start(_lab(lab_definition), lambda p: reports.append(p.model_copy()))

    assert excinfo.value.message == (
        "node 'host-a' (alpine:3.21): could not pull image 'alpine:3.21': "
        "Error response from daemon: manifest for alpine:3.21 not found"
    )
    assert excinfo.value.command == ["docker", "pull", "alpine:3.21"]
    failed = [r for r in reports if r.step == "failed"]
    assert [r.node_id for r in failed] == ["host-a"]
    assert failed[0].detail.startswith("could not pull image")
    # Cleanup still happens after an attributed failure.
    assert ["docker", "network", "rm", "practicum-12345678-left"] in commands


def test_docker_runtime_image_check_raises_when_docker_is_down(
    monkeypatch, lab_definition: dict
) -> None:
    def fake_run(command, capture_output, check, text, **kwargs) -> subprocess.CompletedProcess:
        if command[:3] == ["docker", "image", "inspect"]:
            return subprocess.CompletedProcess(
                command, 1, "", "Cannot connect to the Docker daemon at npipe:////./pipe/docker_engine"
            )
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(subprocess, "run", fake_run)

    with pytest.raises(RuntimeFailure) as excinfo:
        DockerRuntime().start(_lab(lab_definition))

    assert "Cannot connect to the Docker daemon" in excinfo.value.message
    assert excinfo.value.message.startswith("node 'host-a' (alpine:3.21): ")


def test_docker_runtime_reset_tolerates_dockers_network_not_found_wording(
    monkeypatch, lab_definition: dict
) -> None:
    """`docker network rm` says "network X not found" (not "No such network"); a reset of a
    lab whose networks are already gone must still succeed."""

    def fake_run(command, capture_output, check, text, **kwargs) -> subprocess.CompletedProcess:
        if command[:3] == ["docker", "network", "rm"]:
            return subprocess.CompletedProcess(
                command, 1, "", f"Error response from daemon: network {command[-1]} not found"
            )
        if command[:2] == ["docker", "rm"]:
            return subprocess.CompletedProcess(
                command, 1, "", f"Error response from daemon: No such container: {command[-1]}"
            )
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(subprocess, "run", fake_run)

    DockerRuntime().reset(_lab(lab_definition))  # must not raise


def test_docker_runtime_passes_sysctls_for_router_nodes(monkeypatch, lab_definition: dict) -> None:
    commands: list[list[str]] = []

    def fake_run(command, capture_output, check, text, **kwargs) -> subprocess.CompletedProcess:
        commands.append(command)
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(subprocess, "run", fake_run)
    lab_definition["nodes"][1]["resources"]["sysctls"] = {"net.ipv4.ip_forward": "1"}

    DockerRuntime().start(_lab(lab_definition))

    router_run = next(c for c in commands if c[:2] == ["docker", "run"] and "practicum-12345678-router" in c)
    assert ["--sysctl", "net.ipv4.ip_forward=1"] in [
        router_run[i : i + 2] for i in range(len(router_run) - 1)
    ]
    host_run = next(c for c in commands if c[:2] == ["docker", "run"] and "practicum-12345678-host-a" in c)
    assert "--sysctl" not in host_run


def test_docker_runtime_lists_practicum_containers_with_lab_ids(monkeypatch) -> None:
    def fake_run(command, capture_output, check, text, **kwargs) -> subprocess.CompletedProcess:
        assert command[:4] == ["docker", "ps", "-a", "--filter"]
        return subprocess.CompletedProcess(
            command, 0, "practicum-aaaa-host\taaaa-1111\trunning\npracticum-bbbb-web\tbbbb-2222\texited\n", ""
        )

    monkeypatch.setattr(subprocess, "run", fake_run)

    containers = DockerRuntime().list_practicum_containers()

    assert [(c.name, c.lab_id, c.status) for c in containers] == [
        ("practicum-aaaa-host", "aaaa-1111", "running"),
        ("practicum-bbbb-web", "bbbb-2222", "exited"),
    ]


def test_docker_runtime_remove_container_tolerates_missing(monkeypatch) -> None:
    commands: list[list[str]] = []

    def fake_run(command, capture_output, check, text, **kwargs) -> subprocess.CompletedProcess:
        commands.append(command)
        return subprocess.CompletedProcess(command, 1, "", "Error: No such container: gone")

    monkeypatch.setattr(subprocess, "run", fake_run)

    DockerRuntime().remove_container("gone")  # must not raise

    assert commands == [["docker", "rm", "-f", "gone"]]
