from __future__ import annotations

import json
import re
import subprocess
from collections.abc import Callable, Iterator
from ipaddress import IPv4Address, IPv4Interface, IPv4Network
from typing import Protocol

from practicum.models import (
    DockerNetworkInfo,
    Interface,
    Lab,
    Network,
    Node,
    NodeStartProgress,
    PracticumContainerInfo,
    RuntimeResourceStatus,
)

# Called by the runtime every time a node's start progress changes (runtime-image-pull-progress).
ProgressCallback = Callable[[NodeStartProgress], None]

# One `docker pull` output line per layer status change, e.g.
#   "f18232174bc9: Downloading [=====>      ]  12.3MB/45.6MB"   (TTY-style, with a bar)
#   "f18232174bc9: Download complete"                            (non-TTY: status only)
_PULL_LAYER_LINE = re.compile(
    r"^(?P<layer>[0-9a-f]{6,}): (?P<status>[A-Za-z ]+?)\s*"
    r"(?:\[.*?\]\s*(?P<done>[\d.]+\s*[kMG]?B)/(?P<total>[\d.]+\s*[kMG]?B))?\s*$"
)
_LAYER_FINISHED = {"Pull complete", "Already exists"}
# A running container may keep a one-line status marker here (written by the desktop's
# quick-start install script); GET /status surfaces it as the container's `note`.
CONTAINER_NOTE_FILE = "/run/practicum-packages.status"
_SIZE_UNITS = {"B": 1, "kB": 1e3, "MB": 1e6, "GB": 1e9}


def _docker_cli_error(exc: OSError) -> str:
    """Human-readable reason the `docker` CLI could not even be launched."""
    if isinstance(exc, FileNotFoundError):
        return "Docker CLI was not found"
    return f"Docker CLI could not be run: {exc}"


_MISSING_RESOURCE = re.compile(
    r"no such (container|network|object)|(container|network) \S+ not found"
)


def _is_missing_error(message: str) -> bool:
    """True when a docker error only says the resource is already gone. Docker words it
    differently per command: "No such container: x", "network x not found",
    "No such network: x", "Error: No such object: x". (A missing docker *CLI* - "Docker CLI
    was not found" - is deliberately not matched.)"""
    return _MISSING_RESOURCE.search(message.lower()) is not None


def _parse_size(text: str) -> float:
    """'12.3MB' -> 12300000.0; tolerant of spaces and unknown units."""
    match = re.match(r"([\d.]+)\s*([kMG]?B)", text.strip())
    if match is None:
        return 0.0
    return float(match.group(1)) * _SIZE_UNITS.get(match.group(2), 1)


class RuntimeFailure(Exception):
    def __init__(self, message: str, command: list[str] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.command = command


class LabRuntime(Protocol):
    def start(self, lab: Lab, on_progress: ProgressCallback | None = None) -> None:
        pass

    def stop(self, lab: Lab) -> None:
        pass

    def reset(self, lab: Lab) -> None:
        pass

    def status(self, lab: Lab) -> list[RuntimeResourceStatus]:
        pass

    def list_networks(self) -> list[DockerNetworkInfo]:
        pass

    def remove_network(self, network: DockerNetworkInfo) -> None:
        pass

    def list_practicum_containers(self) -> list[PracticumContainerInfo]:
        pass

    def remove_container(self, name: str) -> None:
        pass


class DockerRuntime:
    def start(self, lab: Lab, on_progress: ProgressCallback | None = None) -> None:
        """Creates the lab's networks, then brings up each node in spec order.

        Per node: make sure the image is local (explicit `docker pull` with streamed progress
        when it is not), then `docker start` a container left behind by an earlier Stop, or
        `docker run` a fresh one and connect its extra interfaces. Every step is reported
        through `on_progress` so a UI can show where a slow first start actually is.
        A failure is attributed to its node, and everything created so far is removed.
        """
        progress = {
            node.id: NodeStartProgress(node_id=node.id, image=node.image) for node in lab.nodes
        }

        def report(node: Node, step: str, percent: int | None = None, detail: str | None = None):
            entry = progress[node.id]
            entry.step = step
            entry.percent = percent
            entry.detail = detail
            if on_progress is not None:
                on_progress(entry.model_copy())

        current: Node | None = None
        try:
            for network in lab.networks:
                self._create_network(lab, network)

            for node in lab.nodes:
                current = node
                interfaces = [i for i in lab.interfaces if i.node == node.id]
                if not interfaces:
                    raise RuntimeFailure(f"node '{node.id}' has no interfaces")

                report(node, "checking_image")
                if not self._image_present(node.image):
                    report(node, "pulling_image", 0, "starting download")
                    self._pull_image(
                        node.image,
                        lambda percent, detail, n=node: report(n, "pulling_image", percent, detail),
                    )

                report(node, "creating_container")
                container_name = self._container_name(lab, node.id)
                if self._container_state(container_name) is not None:
                    # Left behind by Stop: restarting it keeps its filesystem and addresses.
                    self._run(["docker", "start", container_name])
                else:
                    self._run_container(lab, node, interfaces[0])
                    if len(interfaces) > 1:
                        report(node, "connecting_networks")
                    for interface in interfaces[1:]:
                        self._connect_network(lab, node, interface)
                report(node, "ready")
            current = None
        except RuntimeFailure as exc:
            if current is not None:
                report(current, "failed", None, exc.message)
                exc.message = f"node '{current.id}' ({current.image}): {exc.message}"
                exc.args = (exc.message,)
            self._cleanup_after_failed_start(lab)
            raise

    def _image_present(self, image: str) -> bool:
        """True when `image` is already in the local Docker image store."""
        command = ["docker", "image", "inspect", "--format", "{{.Id}}", image]
        try:
            completed = subprocess.run(command, capture_output=True, check=False, text=True)
        except OSError as exc:
            raise RuntimeFailure(_docker_cli_error(exc), command) from exc
        if completed.returncode == 0:
            return True
        message = (completed.stderr or completed.stdout or "").strip()
        if "no such image" in message.lower() or "no such object" in message.lower():
            return False
        raise RuntimeFailure(message or "Docker command failed", command)

    def _pull_image(self, image: str, report: Callable[[int, str], None]) -> None:
        """Runs `docker pull` and reports progress as layers complete.

        Docker's CLI prints one line per layer status change ("<layer>: Downloading",
        "<layer>: Pull complete", ...). Without a TTY the byte counts are usually omitted, so
        progress is measured in layers, refined with bytes when the bar is present.
        """
        command = ["docker", "pull", image]
        try:
            process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )
        except OSError as exc:
            raise RuntimeFailure(_docker_cli_error(exc), command) from exc

        layers: dict[str, float] = {}  # layer id -> fraction complete (0..1)
        last_lines: list[str] = []
        assert process.stdout is not None
        for raw_line in process.stdout:
            line = raw_line.strip()
            if not line:
                continue
            last_lines = (last_lines + [line])[-3:]
            match = _PULL_LAYER_LINE.match(line)
            if match is None:
                continue
            layer, status = match.group("layer"), match.group("status").strip()
            fraction = layers.get(layer, 0.0)
            if status in _LAYER_FINISHED:
                fraction = 1.0
            elif status == "Download complete":
                fraction = max(fraction, 0.7)
            elif status in ("Downloading", "Extracting") and match.group("total"):
                done = _parse_size(match.group("done"))
                total = _parse_size(match.group("total"))
                share = done / total if total else 0.0
                fraction = share * 0.7 if status == "Downloading" else 0.7 + share * 0.3
            elif status == "Extracting":
                fraction = max(fraction, 0.7)
            layers[layer] = max(layers.get(layer, 0.0), min(fraction, 1.0))

            finished = sum(1 for value in layers.values() if value >= 1.0)
            percent = round(100 * sum(layers.values()) / len(layers)) if layers else 0
            report(min(percent, 99), f"{finished} of {len(layers)} layers")

        returncode = process.wait()
        if returncode != 0:
            message = next(
                (line for line in reversed(last_lines) if "error" in line.lower()),
                last_lines[-1] if last_lines else "docker pull failed",
            )
            raise RuntimeFailure(f"could not pull image '{image}': {message}", command)
        report(100, "download complete")

    def _container_state(self, name: str) -> str | None:
        """The container's Docker state ("running", "exited", ...); None when it does not exist."""
        command = ["docker", "inspect", "--format", "{{.State.Status}}", name]
        try:
            completed = subprocess.run(command, capture_output=True, check=False, text=True)
        except OSError as exc:
            raise RuntimeFailure(_docker_cli_error(exc), command) from exc
        if completed.returncode != 0:
            return None
        state = completed.stdout.strip()
        return state or None

    def stop(self, lab: Lab) -> None:
        for node in lab.nodes:
            command = ["docker", "stop", self._container_name(lab, node.id)]
            try:
                self._run(command)
            except RuntimeFailure as exc:
                if not _is_missing_error(exc.message):
                    raise

    def reset(self, lab: Lab) -> None:
        for node in lab.nodes:
            command = ["docker", "rm", "-f", self._container_name(lab, node.id)]
            try:
                self._run(command)
            except RuntimeFailure as exc:
                if not _is_missing_error(exc.message):
                    raise

        for network in lab.networks:
            command = ["docker", "network", "rm", self._network_name(lab, network.id)]
            try:
                self._run(command)
            except RuntimeFailure as exc:
                if not _is_missing_error(exc.message):
                    raise

    def status(self, lab: Lab) -> list[RuntimeResourceStatus]:
        resources: list[RuntimeResourceStatus] = []

        for network in lab.networks:
            name = self._network_name(lab, network.id)
            resources.append(
                self._inspect_resource(
                    kind="network",
                    resource_id=network.id,
                    name=name,
                    command=["docker", "network", "inspect", name],
                    status="present",
                )
            )

        for node in lab.nodes:
            name = self._container_name(lab, node.id)
            resource = self._inspect_resource(
                kind="container",
                resource_id=node.id,
                name=name,
                command=["docker", "inspect", "--format", "{{.State.Status}}", name],
            )
            if resource.exists and resource.status == "running":
                resource.note = self._container_note(name)
            resources.append(resource)

        return resources

    def _container_note(self, name: str) -> str | None:
        """The first line of the container's self-reported status marker, if it keeps one."""
        command = ["docker", "exec", name, "cat", CONTAINER_NOTE_FILE]
        try:
            completed = subprocess.run(
                command, capture_output=True, check=False, text=True, timeout=5
            )
        except (OSError, subprocess.TimeoutExpired):
            return None
        if completed.returncode != 0:
            return None
        first_line = completed.stdout.strip().splitlines()
        return first_line[0][:200] if first_line else None

    def list_networks(self) -> list[DockerNetworkInfo]:
        """Every network on the Docker host with its subnets, Practicum label (if any) and
        attached containers. Raises RuntimeFailure when Docker cannot be queried."""
        ls_command = ["docker", "network", "ls", "--format", "{{.Name}}"]
        listed = self._query(ls_command)
        names = [name for name in listed.splitlines() if name]
        if not names:
            return []

        inspect_command = ["docker", "network", "inspect", *names]
        try:
            raw_networks = json.loads(self._query(inspect_command) or "[]")
        except json.JSONDecodeError as exc:
            raise RuntimeFailure(
                "Docker returned unreadable network details", inspect_command
            ) from exc

        networks: list[DockerNetworkInfo] = []
        for raw in raw_networks:
            subnets: list[IPv4Network] = []
            for config in (raw.get("IPAM") or {}).get("Config") or []:
                subnet = config.get("Subnet")
                if not subnet:
                    continue
                try:
                    subnets.append(IPv4Network(subnet, strict=False))
                except ValueError:
                    continue  # IPv6 or malformed; nothing a lab subnet can overlap
            containers = raw.get("Containers") or {}
            networks.append(
                DockerNetworkInfo(
                    name=raw.get("Name", ""),
                    subnets=subnets,
                    lab_id=(raw.get("Labels") or {}).get("practicum.lab_id"),
                    container_names=[
                        entry.get("Name") or container_id
                        for container_id, entry in containers.items()
                    ],
                )
            )
        return networks

    def list_practicum_containers(self) -> list[PracticumContainerInfo]:
        """Every container (running or not) created by Practicum, with its lab id label.
        Raises RuntimeFailure when Docker cannot be queried."""
        command = [
            "docker",
            "ps",
            "-a",
            "--filter",
            "label=practicum.lab_id",
            "--format",
            '{{.Names}}\t{{.Label "practicum.lab_id"}}\t{{.State}}',
        ]
        containers: list[PracticumContainerInfo] = []
        for line in self._query(command).splitlines():
            if not line.strip():
                continue
            parts = line.split("\t")
            containers.append(
                PracticumContainerInfo(
                    name=parts[0],
                    lab_id=parts[1] if len(parts) > 1 and parts[1] else None,
                    status=parts[2] if len(parts) > 2 and parts[2] else None,
                )
            )
        return containers

    def remove_container(self, name: str) -> None:
        try:
            self._run(["docker", "rm", "-f", name])
        except RuntimeFailure as exc:
            if not _is_missing_error(exc.message):
                raise

    def remove_network(self, network: DockerNetworkInfo) -> None:
        """Force-removes the containers attached to `network`, then the network itself.
        Meant for Practicum-labelled leftovers whose lab is no longer known to the API."""
        for container in network.container_names:
            try:
                self._run(["docker", "rm", "-f", container])
            except RuntimeFailure as exc:
                if not _is_missing_error(exc.message):
                    raise
        try:
            self._run(["docker", "network", "rm", network.name])
        except RuntimeFailure as exc:
            if not _is_missing_error(exc.message):
                raise

    def _query(self, command: list[str]) -> str:
        """Runs a read-only docker command and returns stdout; failures become RuntimeFailure."""
        try:
            completed = subprocess.run(command, capture_output=True, check=False, text=True)
        except OSError as exc:
            raise RuntimeFailure(_docker_cli_error(exc), command) from exc
        if completed.returncode != 0:
            message = completed.stderr.strip() or completed.stdout.strip() or "Docker command failed"
            raise RuntimeFailure(message, command)
        return completed.stdout

    def _create_network(self, lab: Lab, network: Network) -> None:
        name = self._network_name(lab, network.id)
        if self._network_exists(name):
            # Reuse a network already left over from an earlier start of this same lab.
            return

        self._remove_empty_practicum_networks_with_subnet(network.subnet)

        try:
            self._run(
                [
                    "docker",
                    "network",
                    "create",
                    "--driver",
                    "bridge",
                    "--subnet",
                    str(network.subnet),
                    "--gateway",
                    self._gateway_ip(lab, network),
                    "--label",
                    f"practicum.lab_id={lab.id}",
                    "--label",
                    f"practicum.network_id={network.id}",
                    name,
                ]
            )
        except RuntimeFailure as exc:
            if "pool overlaps" in exc.message.lower():
                raise RuntimeFailure(
                    f"Cannot start: network '{network.id}' ({network.subnet}) overlaps with "
                    "another Docker network that is already using that address space. Reset "
                    "whichever other lab owns it (Stop is not enough - networks are kept until "
                    "Reset), or change this lab's subnet, then try again. If the owning lab is no "
                    "longer listed, it is left over from an earlier session: run "
                    "`docker network ls --filter label=practicum.lab_id` and remove it with "
                    f"`docker network rm <name>`. (Docker said: {exc.message})",
                    exc.command,
                ) from exc
            raise

    def _network_exists(self, name: str) -> bool:
        try:
            completed = subprocess.run(
                ["docker", "network", "ls", "--filter", f"name=^{name}$", "--format", "{{.Name}}"],
                capture_output=True,
                check=False,
                text=True,
            )
        except OSError as exc:
            raise RuntimeFailure(_docker_cli_error(exc), ["docker", "network", "ls"]) from exc

        if completed.returncode != 0:
            return False

        return name in [line for line in completed.stdout.splitlines() if line]

    def _run_container(self, lab: Lab, node: Node, interface: Interface) -> None:
        command = [
            "docker",
            "run",
            "-d",
            "--name",
            self._container_name(lab, node.id),
            "--label",
            f"practicum.lab_id={lab.id}",
            "--label",
            f"practicum.node_id={node.id}",
            "--network",
            self._network_name(lab, interface.network),
            "--ip",
            self._ip(interface.address),
        ]

        if node.resources is not None:
            if node.resources.cpu is not None:
                command.extend(["--cpus", str(node.resources.cpu)])
            if node.resources.memory_mb is not None:
                command.extend(["--memory", f"{node.resources.memory_mb}m"])
            if node.resources.shm_size_mb is not None:
                command.extend(["--shm-size", f"{node.resources.shm_size_mb}m"])
            for port in node.resources.exposed_ports:
                command.extend(["-p", f"{port}:{port}"])
            for mapping in node.resources.port_mappings:
                command.extend(
                    [
                        "-p",
                        f"{mapping.host}:{mapping.container}/{mapping.protocol}",
                    ]
                )
            for name, value in node.resources.sysctls.items():
                command.extend(["--sysctl", f"{name}={value}"])

        for name, value in node.environment.items():
            command.extend(["-e", f"{name}={value}"])

        command.append(node.image)
        if node.command is not None:
            command.extend(node.command)
        self._run(command)

    def _connect_network(self, lab: Lab, node: Node, interface: Interface) -> None:
        self._run(
            [
                "docker",
                "network",
                "connect",
                "--ip",
                self._ip(interface.address),
                self._network_name(lab, interface.network),
                self._container_name(lab, node.id),
            ]
        )

    def _run(self, command: list[str]) -> None:
        try:
            completed = subprocess.run(command, capture_output=True, check=False, text=True)
        except OSError as exc:
            raise RuntimeFailure(_docker_cli_error(exc), command) from exc

        if completed.returncode != 0:
            message = completed.stderr.strip() or completed.stdout.strip() or "Docker command failed"
            raise RuntimeFailure(message, command)

    def _inspect_resource(
        self,
        kind: str,
        resource_id: str,
        name: str,
        command: list[str],
        status: str | None = None,
    ) -> RuntimeResourceStatus:
        try:
            completed = subprocess.run(command, capture_output=True, check=False, text=True)
        except OSError as exc:
            return RuntimeResourceStatus(
                kind=kind,
                id=resource_id,
                name=name,
                exists=False,
                error=_docker_cli_error(exc),
            )

        if completed.returncode != 0:
            return RuntimeResourceStatus(
                kind=kind,
                id=resource_id,
                name=name,
                exists=False,
                error=completed.stderr.strip() or completed.stdout.strip() or "Docker resource missing",
            )

        return RuntimeResourceStatus(
            kind=kind,
            id=resource_id,
            name=name,
            exists=True,
            status=status or completed.stdout.strip() or None,
            )

    def _remove_empty_practicum_networks_with_subnet(self, subnet: IPv4Network) -> None:
        names = self._practicum_network_names()
        if not names:
            return

        try:
            completed = subprocess.run(
                ["docker", "network", "inspect", *names],
                capture_output=True,
                check=False,
                text=True,
            )
        except OSError as exc:
            raise RuntimeFailure(_docker_cli_error(exc), ["docker", "network", "inspect"]) from exc

        if completed.returncode != 0:
            return

        for network in json.loads(completed.stdout):
            network_subnets = [
                config.get("Subnet")
                for config in network.get("IPAM", {}).get("Config", [])
                if config.get("Subnet")
            ]
            has_target_subnet = str(subnet) in network_subnets
            has_containers = bool(network.get("Containers"))

            if has_target_subnet and not has_containers:
                self._run(["docker", "network", "rm", network["Name"]])

    def _practicum_network_names(self) -> list[str]:
        try:
            completed = subprocess.run(
                [
                    "docker",
                    "network",
                    "ls",
                    "--filter",
                    "label=practicum.lab_id",
                    "--format",
                    "{{.Name}}",
                ],
                capture_output=True,
                check=False,
                text=True,
            )
        except OSError as exc:
            raise RuntimeFailure(_docker_cli_error(exc), ["docker", "network", "ls"]) from exc

        if completed.returncode != 0:
            return []

        return [name for name in completed.stdout.splitlines() if name]

    def _network_name(self, lab: Lab, network_id: str) -> str:
        return f"practicum-{lab.id[:8]}-{network_id}"

    def _container_name(self, lab: Lab, node_id: str) -> str:
        return f"practicum-{lab.id[:8]}-{node_id}"

    def _ip(self, address: IPv4Interface) -> str:
        return str(address.ip)

    def _gateway_ip(self, lab: Lab, network: Network) -> str:
        assigned_ips = {
            interface.address.ip for interface in lab.interfaces if interface.network == network.id
        }

        for address in self._usable_ips_descending(network.subnet):
            if address not in assigned_ips:
                return str(address)

        raise RuntimeFailure(f"network '{network.id}' has no available gateway address")

    def _usable_ips_descending(self, network: IPv4Network) -> Iterator[IPv4Address]:
        first_usable = int(network.network_address) + 1
        last_usable = int(network.broadcast_address) - 1

        if last_usable < first_usable:
            return

        for address in range(last_usable, first_usable - 1, -1):
            yield IPv4Address(address)

    def _cleanup_after_failed_start(self, lab: Lab) -> None:
        try:
            self.reset(lab)
        except RuntimeFailure:
            pass
