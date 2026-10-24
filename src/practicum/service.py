from uuid import uuid4

from practicum.models import (
    Lab,
    LabDefinition,
    LabPreview,
    NetworkCheckResult,
    PortCheckResult,
    PortMapping,
    ResourceEstimate,
    RuntimeActionResult,
    RuntimeIssue,
    RuntimeStatusResult,
    TopologyPreview,
)
from practicum.networks import find_subnet_conflicts, move_subnet
from practicum.ports import check_lab_ports
from practicum.runtime import DockerRuntime, LabRuntime, RuntimeFailure


class LabNotFoundError(Exception):
    pass


class PortRecommendationUnavailableError(Exception):
    pass


class SubnetRecommendationUnavailableError(Exception):
    pass


class LeftoverNetworkNotRemovableError(Exception):
    pass


class LabService:
    def __init__(self, runtime: LabRuntime | None = None) -> None:
        self._labs: dict[str, Lab] = {}
        self.runtime = runtime or DockerRuntime()

    def create(self, definition: LabDefinition) -> Lab:
        lab = Lab(id=str(uuid4()), **definition.model_dump())
        self._labs[lab.id] = lab
        return lab

    def list(self) -> list[Lab]:
        return list(self._labs.values())

    def get(self, lab_id: str) -> Lab:
        try:
            return self._labs[lab_id]
        except KeyError as exc:
            raise LabNotFoundError(lab_id) from exc

    def export(self, lab_id: str) -> LabDefinition:
        lab = self.get(lab_id)
        return LabDefinition.model_validate(lab.model_dump(exclude={"id", "status"}))

    def preview(self, lab_id: str) -> LabPreview:
        lab = self.get(lab_id)
        images: list[str] = []
        cpu_values: list[float] = []
        memory_values: list[int] = []
        exposed_ports: set[int] = set()
        port_mappings = []

        for node in lab.nodes:
            if node.image not in images:
                images.append(node.image)
            if node.resources is None:
                continue
            if node.resources.cpu is not None:
                cpu_values.append(node.resources.cpu)
            if node.resources.memory_mb is not None:
                memory_values.append(node.resources.memory_mb)
            exposed_ports.update(node.resources.exposed_ports)
            port_mappings.extend(node.resources.port_mappings)

        return LabPreview(
            id=lab.id,
            status=lab.status,
            schema_version=lab.schema_version,
            name=lab.name,
            description=lab.description,
            author=lab.author,
            version=lab.version,
            required_images=images,
            estimated_resources=ResourceEstimate(
                total_cpu=sum(cpu_values) if cpu_values else None,
                total_memory_mb=sum(memory_values) if memory_values else None,
                exposed_ports=sorted(exposed_ports),
                port_mappings=port_mappings,
            ),
            topology=TopologyPreview(
                nodes=lab.nodes,
                networks=lab.networks,
                interfaces=lab.interfaces,
            ),
            manual=lab.manual,
        )

    def start(self, lab_id: str) -> RuntimeActionResult:
        lab = self.get(lab_id)
        if lab.status == "running":
            return RuntimeActionResult(success=True, lab=lab)

        lab.status = "starting"
        try:
            self.runtime.start(lab)
        except RuntimeFailure as exc:
            lab.status = "error"
            return RuntimeActionResult(
                success=False,
                lab=lab,
                errors=[RuntimeIssue(message=exc.message, command=exc.command)],
            )

        lab.status = "running"
        return RuntimeActionResult(success=True, lab=lab)

    def stop(self, lab_id: str) -> RuntimeActionResult:
        lab = self.get(lab_id)
        if lab.status == "stopped":
            return RuntimeActionResult(success=True, lab=lab)

        lab.status = "stopping"
        try:
            self.runtime.stop(lab)
        except RuntimeFailure as exc:
            lab.status = "error"
            return RuntimeActionResult(
                success=False,
                lab=lab,
                errors=[RuntimeIssue(message=exc.message, command=exc.command)],
            )

        lab.status = "stopped"
        return RuntimeActionResult(success=True, lab=lab)

    def reset(self, lab_id: str) -> RuntimeActionResult:
        lab = self.get(lab_id)
        try:
            self.runtime.reset(lab)
        except RuntimeFailure as exc:
            lab.status = "error"
            return RuntimeActionResult(
                success=False,
                lab=lab,
                errors=[RuntimeIssue(message=exc.message, command=exc.command)],
            )

        lab.status = "defined"
        return RuntimeActionResult(success=True, lab=lab)

    def status(self, lab_id: str) -> RuntimeStatusResult:
        lab = self.get(lab_id)
        try:
            resources = self.runtime.status(lab)
        except RuntimeFailure as exc:
            return RuntimeStatusResult(
                lab=lab,
                errors=[RuntimeIssue(message=exc.message, command=exc.command)],
            )

        return RuntimeStatusResult(lab=lab, resources=resources)

    def check_ports(self, lab_id: str) -> PortCheckResult:
        lab = self.get(lab_id)
        conflicts = check_lab_ports(lab)
        return PortCheckResult(lab_id=lab.id, has_conflicts=bool(conflicts), conflicts=conflicts)

    def apply_port_recommendation(
        self, lab_id: str, node_id: str, host_port: int, protocol: str
    ) -> PortCheckResult:
        lab = self.get(lab_id)
        conflicts = check_lab_ports(lab)
        conflict = next(
            (
                c
                for c in conflicts
                if c.node_id == node_id and c.host_port == host_port and c.protocol == protocol
            ),
            None,
        )
        if conflict is None or conflict.recommended_port is None:
            raise PortRecommendationUnavailableError(
                f"No recommended port is available for node '{node_id}' port {host_port}/{protocol}"
            )

        updated_nodes = []
        for node in lab.nodes:
            if node.id != node_id or node.resources is None:
                updated_nodes.append(node)
                continue

            resources = node.resources
            container_port = host_port
            new_exposed = []
            for port in resources.exposed_ports:
                if port == host_port and protocol == "tcp":
                    container_port = port
                else:
                    new_exposed.append(port)

            new_mappings = []
            for mapping in resources.port_mappings:
                if mapping.host == host_port and mapping.protocol == protocol:
                    container_port = mapping.container
                else:
                    new_mappings.append(mapping)

            new_mappings.append(
                PortMapping(
                    host=conflict.recommended_port,
                    container=container_port,
                    protocol=protocol,
                )
            )

            updated_resources = resources.model_copy(
                update={"exposed_ports": new_exposed, "port_mappings": new_mappings}
            )
            updated_nodes.append(node.model_copy(update={"resources": updated_resources}))

        updated_definition = LabDefinition.model_validate(
            {
                **lab.model_dump(exclude={"id", "status"}),
                "nodes": [n.model_dump() for n in updated_nodes],
            }
        )
        self._labs[lab_id] = Lab(id=lab.id, status=lab.status, **updated_definition.model_dump())

        return self.check_ports(lab_id)

    def check_networks(self, lab_id: str) -> NetworkCheckResult:
        """Subnet overlaps between this lab and networks already on the Docker host.
        A Docker query failure is reported in `error` (conflicts unknown), not raised."""
        lab = self.get(lab_id)
        try:
            docker_networks = self.runtime.list_networks()
        except RuntimeFailure as exc:
            return NetworkCheckResult(
                lab_id=lab.id, has_conflicts=False, error=exc.message
            )
        conflicts = find_subnet_conflicts(lab, docker_networks, self._labs)
        return NetworkCheckResult(
            lab_id=lab.id, has_conflicts=bool(conflicts), conflicts=conflicts
        )

    def apply_subnet_recommendation(self, lab_id: str, network_id: str) -> NetworkCheckResult:
        """Moves `network_id` (and its interfaces) to the recommended free subnet."""
        result = self.check_networks(lab_id)
        if result.error:
            raise SubnetRecommendationUnavailableError(result.error)
        conflict = next((c for c in result.conflicts if c.network_id == network_id), None)
        if conflict is None or conflict.recommended_subnet is None:
            raise SubnetRecommendationUnavailableError(
                f"No recommended subnet is available for network '{network_id}'"
            )

        lab = self.get(lab_id)
        updated_definition = LabDefinition.model_validate(
            move_subnet(lab, network_id, conflict.recommended_subnet)
        )
        self._labs[lab_id] = Lab(id=lab.id, status=lab.status, **updated_definition.model_dump())
        return self.check_networks(lab_id)

    def remove_leftover_network(self, lab_id: str, network_name: str) -> NetworkCheckResult:
        """Removes a Practicum-labelled Docker network (and its containers) whose lab is no
        longer known to this API - typically left behind by an earlier session - but only
        when it actually conflicts with `lab_id`."""
        result = self.check_networks(lab_id)
        if result.error:
            raise LeftoverNetworkNotRemovableError(result.error)
        conflict = next(
            (c for c in result.conflicts if c.owner_network_name == network_name), None
        )
        if conflict is None:
            raise LeftoverNetworkNotRemovableError(
                f"Network '{network_name}' does not conflict with this lab"
            )
        if conflict.reason != "overlaps_leftover":
            raise LeftoverNetworkNotRemovableError(
                f"Network '{network_name}' is not a Practicum leftover; "
                + (
                    f"it belongs to lab '{conflict.owner_lab_name}' - reset that lab instead"
                    if conflict.reason == "overlaps_other_lab"
                    else "it was not created by Practicum, so Practicum will not remove it"
                )
            )

        network = next(
            (n for n in self.runtime.list_networks() if n.name == network_name), None
        )
        if network is None:  # vanished between the check and now; nothing left to do
            return self.check_networks(lab_id)
        self.runtime.remove_network(network)
        return self.check_networks(lab_id)

    def clear(self) -> None:
        self._labs.clear()
