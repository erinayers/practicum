from __future__ import annotations

import threading
from datetime import UTC, datetime
from uuid import uuid4

from practicum.models import (
    LAB_RUNTIME_FIELDS,
    DockerEngineInfo,
    Lab,
    LabDefinition,
    LabOrigin,
    LabPreview,
    LeftoverSweepResult,
    NetworkCheckResult,
    NodeStartProgress,
    PortCheckResult,
    PortMapping,
    ResourceEstimate,
    RuntimeActionResult,
    RuntimeIssue,
    RuntimeStatusResult,
    TopologyPreview,
)
from practicum.networks import find_subnet_conflicts, move_subnet
from practicum.ports import check_lab_ports, describe_conflict, port_unavailable_reason
from practicum.runtime import DockerRuntime, LabRuntime, RuntimeFailure

# Lab statuses during which no other lifecycle action may begin (action lock).
BUSY_STATUSES = frozenset({"starting", "stopping"})


class LabNotFoundError(Exception):
    pass


class LabBusyError(Exception):
    """A lifecycle action was requested while another one is still in flight for that lab."""


class LabDeleteError(Exception):
    """The lab's Docker resources could not be removed, so the lab was kept."""


class LabRunningError(Exception):
    """The lab must be stopped before its definition can be replaced."""


class PortRecommendationUnavailableError(Exception):
    pass


class PortUnavailableError(PortRecommendationUnavailableError):
    """The port the user chose cannot be used (reserved, taken in the lab, or bound on the host)."""


class SubnetRecommendationUnavailableError(Exception):
    pass


class LeftoverNetworkNotRemovableError(Exception):
    pass


class LabService:
    def __init__(self, runtime: LabRuntime | None = None) -> None:
        self._labs: dict[str, Lab] = {}
        self.runtime = runtime or DockerRuntime()
        # Per-node progress of each lab's most recent start (runtime-image-pull-progress).
        self._progress: dict[str, dict[str, NodeStartProgress]] = {}
        # Guards status transitions so two concurrent requests cannot both pass the busy check.
        self._transition_lock = threading.Lock()
        self._background_starts: dict[str, threading.Thread] = {}

    def create(
        self,
        definition: LabDefinition,
        origin: LabOrigin = "designer",
        source_file: str | None = None,
    ) -> Lab:
        lab = Lab(
            id=str(uuid4()),
            origin=origin,
            source_file=source_file,
            created_at=_now(),
            **definition.model_dump(),
        )
        self._labs[lab.id] = lab
        return lab

    def list(self) -> list[Lab]:
        return list(self._labs.values())

    def delete(self, lab_id: str) -> None:
        """Forgets the lab after removing any Docker resources it created. A lab that never
        started has nothing to clean up; otherwise a cleanup failure keeps the lab (and raises)
        so nothing is silently orphaned on the Docker host."""
        lab = self.get(lab_id)
        self._begin_transition(lab, lab.status)  # only checks that the lab is not busy
        try:
            # Always sweep the lab's Docker names, whatever the bookkeeping says: containers
            # must never outlive the lab card (user report, 2026-10-24).
            self.runtime.reset(lab)
        except RuntimeFailure as exc:
            if lab.status != "defined":
                lab.status = "error"
                lab.last_error = exc.message
                raise LabDeleteError(
                    f"Could not remove the lab's Docker resources: {exc.message}"
                ) from exc
            # Never started (nothing to clean) and Docker is unavailable: deleting the entry
            # is still the right thing to do.
        del self._labs[lab_id]
        self._progress.pop(lab_id, None)

    def sweep_leftovers(self) -> LeftoverSweepResult:
        """Removes Practicum-labelled containers and networks whose lab this API does not
        know. Labs live in memory only (D-10), so after an API restart every resource of the
        previous session is such a leftover: unreachable from the app, still using RAM and
        address space. Best effort: per-item failures are reported, not raised."""
        result = LeftoverSweepResult()
        known = set(self._labs)
        try:
            containers = self.runtime.list_practicum_containers()
            networks = self.runtime.list_networks()
        except RuntimeFailure as exc:
            result.error = exc.message
            return result
        for container in containers:
            if container.lab_id in known:
                continue
            try:
                self.runtime.remove_container(container.name)
                result.removed_containers.append(container.name)
            except RuntimeFailure as exc:
                result.errors.append(f"{container.name}: {exc.message}")
        for network in networks:
            if network.lab_id is None or network.lab_id in known:
                continue  # not Practicum's, or still in use by a listed lab
            try:
                self.runtime.remove_network(network)
                result.removed_networks.append(network.name)
            except RuntimeFailure as exc:
                result.errors.append(f"{network.name}: {exc.message}")
        return result

    def get(self, lab_id: str) -> Lab:
        try:
            return self._labs[lab_id]
        except KeyError as exc:
            raise LabNotFoundError(lab_id) from exc

    def docker_engine(self) -> DockerEngineInfo:
        """Read-only engine mode report (windows-desktop-windows-container-readiness): the
        desktop decides from it whether a Windows lab can be created/started. Never raises
        and never switches anything."""
        try:
            return self.runtime.engine_info()
        except RuntimeFailure as exc:
            return DockerEngineInfo(available=False, detail=exc.message)

    def replace(self, lab_id: str, definition: LabDefinition) -> Lab:
        """Replaces the lab's definition (edit), keeping id, origin and timestamps.

        A running lab cannot be edited (LabRunningError → 409): its containers would no
        longer match the spec. A stopped/error lab's leftover containers and networks are
        removed first so the next Start builds the new topology; the lab returns to `defined`.
        """
        lab = self.get(lab_id)
        if lab.status == "running":
            raise LabRunningError(f"Lab '{lab.name}' is running; stop it before editing")
        self._begin_transition(lab, lab.status)  # busy check only
        if lab.status != "defined":
            try:
                self.runtime.reset(lab)
            except RuntimeFailure as exc:
                lab.status = "error"
                lab.last_error = exc.message
                raise LabDeleteError(
                    f"Could not remove the lab's Docker resources: {exc.message}"
                ) from exc
        updated = self._with_definition(lab, definition)
        updated.status = "defined"
        updated.last_error = None
        self._labs[lab_id] = updated
        self._progress.pop(lab_id, None)
        return updated

    def export(self, lab_id: str) -> LabDefinition:
        lab = self.get(lab_id)
        return LabDefinition.model_validate(lab.model_dump(exclude=set(LAB_RUNTIME_FIELDS)))

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
            container_os=lab.container_os,
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

    def start(self, lab_id: str, wait: bool = True) -> RuntimeActionResult:
        """Starts the lab. With `wait=False` the Docker work runs on a background thread and
        the result carries status "starting"; poll `status()` for per-node progress and the
        final outcome. Raises LabBusyError while another lifecycle action is in flight."""
        lab = self.get(lab_id)
        if lab.status == "running":
            return RuntimeActionResult(success=True, lab=lab)

        self._begin_transition(lab, "starting")

        conflicts = check_lab_ports(lab)
        if conflicts:
            # Re-verified right before starting: conditions may have changed since the gate.
            lab.status = "error"
            lab.last_error = "; ".join(describe_conflict(c) for c in conflicts)
            return RuntimeActionResult(
                success=False,
                lab=lab,
                errors=[
                    RuntimeIssue(message=f"host port conflict: {describe_conflict(c)}")
                    for c in conflicts
                ],
            )

        self._progress[lab.id] = {
            node.id: NodeStartProgress(node_id=node.id, image=node.image) for node in lab.nodes
        }
        if not wait:
            thread = threading.Thread(
                target=self._run_start, args=(lab,), name=f"practicum-start-{lab.id[:8]}"
            )
            self._background_starts[lab.id] = thread
            thread.start()
            return RuntimeActionResult(success=True, lab=lab, pending=True)
        return self._run_start(lab)

    def _run_start(self, lab: Lab) -> RuntimeActionResult:
        def on_progress(entry: NodeStartProgress) -> None:
            progress = self._progress.get(lab.id)
            if progress is not None:
                progress[entry.node_id] = entry

        try:
            self.runtime.start(lab, on_progress)
        except RuntimeFailure as exc:
            lab.status = "error"
            lab.last_error = exc.message
            return RuntimeActionResult(
                success=False,
                lab=lab,
                errors=[RuntimeIssue(message=exc.message, command=exc.command)],
            )
        finally:
            self._background_starts.pop(lab.id, None)

        lab.status = "running"
        lab.last_error = None
        lab.last_started_at = _now()
        return RuntimeActionResult(success=True, lab=lab)

    def stop(self, lab_id: str) -> RuntimeActionResult:
        lab = self.get(lab_id)
        if lab.status == "stopped":
            return RuntimeActionResult(success=True, lab=lab)

        self._begin_transition(lab, "stopping")
        try:
            self.runtime.stop(lab)
        except RuntimeFailure as exc:
            lab.status = "error"
            lab.last_error = exc.message
            return RuntimeActionResult(
                success=False,
                lab=lab,
                errors=[RuntimeIssue(message=exc.message, command=exc.command)],
            )

        lab.status = "stopped"
        lab.last_error = None
        return RuntimeActionResult(success=True, lab=lab)

    def restart(self, lab_id: str) -> RuntimeActionResult:
        """Stop followed by Start as one action. A lab that is not running is simply started."""
        lab = self.get(lab_id)
        if lab.status == "running":
            stopped = self.stop(lab_id)
            if not stopped.success:
                return stopped
        return self.start(lab_id)

    def reset(self, lab_id: str) -> RuntimeActionResult:
        lab = self.get(lab_id)
        self._begin_transition(lab, lab.status)  # only checks that the lab is not busy
        try:
            self.runtime.reset(lab)
        except RuntimeFailure as exc:
            lab.status = "error"
            lab.last_error = exc.message
            return RuntimeActionResult(
                success=False,
                lab=lab,
                errors=[RuntimeIssue(message=exc.message, command=exc.command)],
            )

        lab.status = "defined"
        lab.last_error = None
        self._progress.pop(lab.id, None)
        return RuntimeActionResult(success=True, lab=lab)

    def _begin_transition(self, lab: Lab, new_status: str) -> None:
        """Atomically moves the lab into `new_status` unless it is already busy."""
        with self._transition_lock:
            if lab.status in BUSY_STATUSES:
                raise LabBusyError(
                    f"Lab '{lab.name}' is already {lab.status}; wait for that to finish"
                )
            lab.status = new_status

    def status(self, lab_id: str) -> RuntimeStatusResult:
        lab = self.get(lab_id)
        try:
            resources = self.runtime.status(lab)
        except RuntimeFailure as exc:
            return RuntimeStatusResult(
                lab=lab,
                errors=[RuntimeIssue(message=exc.message, command=exc.command)],
                progress=self._progress_snapshot(lab.id),
            )
        # Snapshot the progress *after* the (slow) Docker queries so it is never older than
        # the lab status serialised alongside it.
        return RuntimeStatusResult(
            lab=lab, resources=resources, progress=self._progress_snapshot(lab.id)
        )

    def _progress_snapshot(self, lab_id: str) -> list[NodeStartProgress]:
        return [entry.model_copy() for entry in self._progress.get(lab_id, {}).values()]

    def check_ports(self, lab_id: str) -> PortCheckResult:
        lab = self.get(lab_id)
        conflicts = check_lab_ports(lab)
        return PortCheckResult(lab_id=lab.id, has_conflicts=bool(conflicts), conflicts=conflicts)

    def apply_port_recommendation(
        self,
        lab_id: str,
        node_id: str,
        host_port: int,
        protocol: str,
        new_host_port: int | None = None,
    ) -> PortCheckResult:
        """Moves a conflicting host port to the server's recommendation or, with
        `new_host_port`, to a port the user picked (checked the same way the recommendation
        was: free on this host, not the API's port, not used elsewhere in the lab)."""
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
        if conflict is None:
            raise PortRecommendationUnavailableError(
                f"Node '{node_id}' port {host_port}/{protocol} has no conflict to resolve"
            )
        if new_host_port is not None:
            problem = port_unavailable_reason(lab, node_id, host_port, new_host_port, protocol)
            if problem is not None:
                raise PortUnavailableError(f"Port {new_host_port}/{protocol} {problem}")
            target_port = new_host_port
        elif conflict.recommended_port is not None:
            target_port = conflict.recommended_port
        else:
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
                PortMapping(host=target_port, container=container_port, protocol=protocol)
            )

            updated_resources = resources.model_copy(
                update={"exposed_ports": new_exposed, "port_mappings": new_mappings}
            )
            updated_nodes.append(node.model_copy(update={"resources": updated_resources}))

        updated_definition = LabDefinition.model_validate(
            {
                **lab.model_dump(exclude=set(LAB_RUNTIME_FIELDS)),
                "nodes": [n.model_dump() for n in updated_nodes],
            }
        )
        reset = self._store_rewritten_definition(lab, updated_definition)
        result = self.check_ports(lab_id)
        result.machines_reset = reset
        return result

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
        reset = self._store_rewritten_definition(lab, updated_definition)
        result = self.check_networks(lab_id)
        result.machines_reset = reset
        return result

    def _store_rewritten_definition(self, lab: Lab, definition: LabDefinition) -> bool:
        """Stores a definition rewritten by a port/subnet fix. A lab that has already run
        keeps containers between Stop and Start (`docker start` reuse), which would bring
        back the *old* mapping and the old session data - so its Docker resources are
        removed first and the lab returns to `defined` (D-48). Returns True when that
        happened. Busy labs are refused; a cleanup failure keeps the old definition."""
        self._begin_transition(lab, lab.status)  # busy check only (LabBusyError → 409)
        reset = False
        if lab.status != "defined":
            try:
                self.runtime.reset(lab)
            except RuntimeFailure as exc:
                lab.status = "error"
                lab.last_error = exc.message
                raise LabDeleteError(
                    "Could not remove the lab's existing machines before changing it: "
                    f"{exc.message}"
                ) from exc
            reset = True
        updated = self._with_definition(lab, definition)
        if reset:
            updated.status = "defined"
            updated.last_error = None
            self._progress.pop(lab.id, None)
        self._labs[lab.id] = updated
        return reset

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

    @staticmethod
    def _with_definition(lab: Lab, definition: LabDefinition) -> Lab:
        """A copy of `lab` with a new definition, keeping id/status/origin/timestamps."""
        runtime_fields = lab.model_dump(include=set(LAB_RUNTIME_FIELDS))
        return Lab(**runtime_fields, **definition.model_dump())

    def clear(self) -> None:
        self._labs.clear()
        self._progress.clear()


def _now() -> datetime:
    return datetime.now(UTC)
