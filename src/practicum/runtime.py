from __future__ import annotations

import json
import subprocess
from ipaddress import IPv4Address, IPv4Interface, IPv4Network
from collections.abc import Iterator
from typing import Protocol

from practicum.models import Interface, Lab, Network, Node, RuntimeResourceStatus


class RuntimeFailure(Exception):
    def __init__(self, message: str, command: list[str] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.command = command


class LabRuntime(Protocol):
    def start(self, lab: Lab) -> None:
        pass

    def stop(self, lab: Lab) -> None:
        pass

    def reset(self, lab: Lab) -> None:
        pass

    def status(self, lab: Lab) -> list[RuntimeResourceStatus]:
        pass


class DockerRuntime:
    def start(self, lab: Lab) -> None:
        try:
            for network in lab.networks:
                self._create_network(lab, network)

            for node in lab.nodes:
                interfaces = [interface for interface in lab.interfaces if interface.node == node.id]
                if not interfaces:
                    raise RuntimeFailure(f"node '{node.id}' has no interfaces")

                first_interface = interfaces[0]
                self._run_container(lab, node, first_interface)

                for interface in interfaces[1:]:
                    self._connect_network(lab, node, interface)
        except RuntimeFailure:
            self._cleanup_after_failed_start(lab)
            raise

    def stop(self, lab: Lab) -> None:
        for node in lab.nodes:
            command = ["docker", "stop", self._container_name(lab, node.id)]
            try:
                self._run(command)
            except RuntimeFailure as exc:
                message = exc.message.lower()
                if "no such container" not in message:
                    raise

    def reset(self, lab: Lab) -> None:
        for node in lab.nodes:
            command = ["docker", "rm", "-f", self._container_name(lab, node.id)]
            try:
                self._run(command)
            except RuntimeFailure as exc:
                message = exc.message.lower()
                if "no such container" not in message:
                    raise

        for network in lab.networks:
            command = ["docker", "network", "rm", self._network_name(lab, network.id)]
            try:
                self._run(command)
            except RuntimeFailure as exc:
                message = exc.message.lower()
                if "no such network" not in message:
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
            resources.append(
                self._inspect_resource(
                    kind="container",
                    resource_id=node.id,
                    name=name,
                    command=["docker", "inspect", "--format", "{{.State.Status}}", name],
                )
            )

        return resources

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
                    "another Docker network that is already using that address space. Stop or "
                    "reset whichever other lab owns it, or change this lab's subnet, then try "
                    f"again. (Docker said: {exc.message})",
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
        except FileNotFoundError as exc:
            raise RuntimeFailure("Docker CLI was not found", ["docker", "network", "ls"]) from exc

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
        except FileNotFoundError as exc:
            raise RuntimeFailure("Docker CLI was not found", command) from exc

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
        except FileNotFoundError:
            return RuntimeResourceStatus(
                kind=kind,
                id=resource_id,
                name=name,
                exists=False,
                error="Docker CLI was not found",
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
        except FileNotFoundError as exc:
            raise RuntimeFailure("Docker CLI was not found", ["docker", "network", "inspect"]) from exc

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
        except FileNotFoundError as exc:
            raise RuntimeFailure("Docker CLI was not found", ["docker", "network", "ls"]) from exc

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
