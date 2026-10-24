from __future__ import annotations

from dataclasses import dataclass, field

import httpx

DEFAULT_BASE_URL = "http://127.0.0.1:8000"
DEFAULT_TIMEOUT_SECONDS = 3.0
# Lifecycle calls (start today; stop/reset/restart later) block on the server for the whole
# Docker sequence, including image pulls that can take minutes on first run. They must not
# share the short timeout used for quick lookups, or the desktop reports a failure while the
# server is still (successfully) working. See Tigre/06 #3.
LIFECYCLE_TIMEOUT_SECONDS = 900.0


@dataclass
class HealthStatus:
    reachable: bool
    healthy: bool
    detail: str


@dataclass
class LabSummary:
    id: str
    name: str
    status: str


@dataclass
class LabsResult:
    success: bool
    labs: list[LabSummary] = field(default_factory=list)
    detail: str = ""


@dataclass
class PortConflict:
    node_id: str
    host_port: int
    container_port: int
    protocol: str
    reason: str
    recommended_port: int | None


PORT_CONFLICT_REASONS = {
    "duplicate_in_spec": "Duplicate port in this lab",
    "reserved_by_practicum_api": "Reserved by the Practicum API",
    "in_use_on_host": "Already in use on this machine",
}


@dataclass
class PortCheckResult:
    success: bool
    has_conflicts: bool = False
    conflicts: list[PortConflict] = field(default_factory=list)
    detail: str = ""


@dataclass
class StartResult:
    """Outcome of a lifecycle call (start/reset): success plus a human-readable detail."""

    success: bool
    detail: str = ""


@dataclass
class ResourceStatusInfo:
    kind: str  # "container" | "network"
    id: str  # node id or network id from the spec
    name: str  # Docker container / network name
    exists: bool
    status: str | None = None  # e.g. "running", "exited", "present"
    error: str | None = None


@dataclass
class StatusResult:
    """Outcome of GET /labs/{id}/status: the lab's status plus one entry per Docker resource."""

    success: bool
    lab_status: str = ""
    resources: list[ResourceStatusInfo] = field(default_factory=list)
    detail: str = ""

    @property
    def containers(self) -> list[ResourceStatusInfo]:
        return [r for r in self.resources if r.kind == "container"]


@dataclass
class SubnetConflict:
    network_id: str
    subnet: str
    reason: str
    owner_network_name: str
    owner_subnet: str
    owner_lab_id: str | None = None
    owner_lab_name: str | None = None
    owner_lab_status: str | None = None
    owner_container_count: int = 0
    recommended_subnet: str | None = None


SUBNET_CONFLICT_REASONS = {
    "overlaps_other_lab": "Used by another lab in your list",
    "overlaps_leftover": "Left over from an earlier Practicum session",
    "overlaps_docker_network": "Used by another Docker network on this machine",
}


@dataclass
class NetworkCheckResult:
    """Outcome of GET /labs/{id}/networks. `success` is False when the API could not be
    reached *or* when the API could not query Docker (its `error`), because in both cases
    the conflicts are unknown and starting would be a blind guess."""

    success: bool
    has_conflicts: bool = False
    conflicts: list[SubnetConflict] = field(default_factory=list)
    detail: str = ""


@dataclass
class FieldIssue:
    location: list[str]
    message: str
    issue_type: str


@dataclass
class ValidateLabResult:
    success: bool
    valid: bool = False
    errors: list[FieldIssue] = field(default_factory=list)
    detail: str = ""


@dataclass
class CreateLabResult:
    success: bool
    lab_id: str | None = None
    errors: list[FieldIssue] = field(default_factory=list)
    detail: str = ""


@dataclass
class ImportLabResult:
    """Outcome of POST /labs/import.

    `success` is True only when the API accepted and stored the lab. A validation
    rejection comes back as success=False with `errors` populated; a transport or
    unexpected-response problem comes back as success=False with `errors` empty and a
    human-readable `detail`.
    """

    success: bool
    lab_id: str | None = None
    lab_name: str = ""
    errors: list[FieldIssue] = field(default_factory=list)
    detail: str = ""


@dataclass
class ManualTaskInfo:
    id: str
    text: str


@dataclass
class ManualSectionInfo:
    id: str
    title: str
    content_markdown: str
    tasks: list[ManualTaskInfo] = field(default_factory=list)


@dataclass
class PortMappingInfo:
    host: int
    container: int
    protocol: str


@dataclass
class TopologyNodeInfo:
    id: str
    image: str


@dataclass
class TopologyNetworkInfo:
    id: str
    subnet: str


@dataclass
class TopologyInterfaceInfo:
    node: str
    network: str
    address: str


@dataclass
class TopologyInfo:
    nodes: list[TopologyNodeInfo] = field(default_factory=list)
    networks: list[TopologyNetworkInfo] = field(default_factory=list)
    interfaces: list[TopologyInterfaceInfo] = field(default_factory=list)


@dataclass
class EstimatedResourcesInfo:
    total_cpu: float | None = None
    total_memory_mb: int | None = None


@dataclass
class PreviewResult:
    success: bool
    name: str = ""
    description: str = ""
    author: str = ""
    version: str = ""
    required_images: list[str] = field(default_factory=list)
    estimated_resources: EstimatedResourcesInfo = field(default_factory=EstimatedResourcesInfo)
    topology: TopologyInfo = field(default_factory=TopologyInfo)
    manual_sections: list[ManualSectionInfo] = field(default_factory=list)
    port_mappings: list[PortMappingInfo] = field(default_factory=list)
    detail: str = ""


class ApiClient:
    """Thin HTTP client for the local Practicum API. Holds no lab logic of its own."""

    def __init__(
        self,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
        lifecycle_timeout: float = LIFECYCLE_TIMEOUT_SECONDS,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.lifecycle_timeout = lifecycle_timeout

    def check_health(self) -> HealthStatus:
        try:
            response = httpx.get(f"{self.base_url}/health", timeout=self.timeout)
        except httpx.ConnectError:
            return HealthStatus(
                reachable=False, healthy=False, detail="Could not connect to the Practicum API."
            )
        except httpx.TimeoutException:
            return HealthStatus(
                reachable=False, healthy=False, detail="The Practicum API did not respond in time."
            )
        except httpx.HTTPError as exc:
            return HealthStatus(
                reachable=False,
                healthy=False,
                detail=f"Unexpected error contacting the Practicum API: {exc}",
            )

        if response.status_code != 200:
            return HealthStatus(
                reachable=True,
                healthy=False,
                detail=f"The Practicum API responded with status {response.status_code}.",
            )

        try:
            body = response.json()
        except ValueError:
            return HealthStatus(
                reachable=True, healthy=False, detail="The Practicum API returned an unexpected response."
            )

        if not isinstance(body, dict) or body.get("status") != "ok":
            return HealthStatus(
                reachable=True, healthy=False, detail="The Practicum API reported an unhealthy status."
            )

        return HealthStatus(reachable=True, healthy=True, detail="The Practicum API is healthy.")

    def list_labs(self) -> LabsResult:
        try:
            response = httpx.get(f"{self.base_url}/labs", timeout=self.timeout)
        except httpx.HTTPError as exc:
            return LabsResult(success=False, detail=f"Could not load labs: {exc}")

        if response.status_code != 200:
            return LabsResult(
                success=False, detail=f"Could not load labs (status {response.status_code})."
            )

        try:
            body = response.json()
        except ValueError:
            return LabsResult(success=False, detail="The Practicum API returned an unexpected labs response.")

        if not isinstance(body, list):
            return LabsResult(success=False, detail="The Practicum API returned an unexpected labs response.")

        labs = [
            LabSummary(id=item.get("id", ""), name=item.get("name", ""), status=item.get("status", ""))
            for item in body
        ]
        return LabsResult(success=True, labs=labs)

    def check_ports(self, lab_id: str) -> PortCheckResult:
        try:
            response = httpx.get(f"{self.base_url}/labs/{lab_id}/ports", timeout=self.timeout)
        except httpx.HTTPError as exc:
            return PortCheckResult(success=False, detail=f"Could not check ports: {exc}")

        if response.status_code != 200:
            return PortCheckResult(
                success=False, detail=f"Could not check ports (status {response.status_code})."
            )

        try:
            body = response.json()
        except ValueError:
            return PortCheckResult(success=False, detail="The Practicum API returned an unexpected response.")

        conflicts = [
            PortConflict(
                node_id=item["node_id"],
                host_port=item["host_port"],
                container_port=item["container_port"],
                protocol=item["protocol"],
                reason=item["reason"],
                recommended_port=item.get("recommended_port"),
            )
            for item in body.get("conflicts", [])
        ]
        return PortCheckResult(success=True, has_conflicts=body.get("has_conflicts", False), conflicts=conflicts)

    def apply_port_recommendation(
        self, lab_id: str, node_id: str, host_port: int, protocol: str
    ) -> PortCheckResult:
        try:
            response = httpx.post(
                f"{self.base_url}/labs/{lab_id}/ports/apply-recommendation",
                json={"node_id": node_id, "host_port": host_port, "protocol": protocol},
                timeout=self.timeout,
            )
        except httpx.HTTPError as exc:
            return PortCheckResult(success=False, detail=f"Could not apply the recommended port: {exc}")

        if response.status_code != 200:
            detail = None
            if response.headers.get("content-type", "").startswith("application/json"):
                detail = response.json().get("detail")
            return PortCheckResult(
                success=False,
                detail=detail or f"Could not apply the recommended port (status {response.status_code}).",
            )

        body = response.json()
        conflicts = [
            PortConflict(
                node_id=item["node_id"],
                host_port=item["host_port"],
                container_port=item["container_port"],
                protocol=item["protocol"],
                reason=item["reason"],
                recommended_port=item.get("recommended_port"),
            )
            for item in body.get("conflicts", [])
        ]
        return PortCheckResult(success=True, has_conflicts=body.get("has_conflicts", False), conflicts=conflicts)

    def validate_lab(self, definition: dict[str, object]) -> ValidateLabResult:
        try:
            response = httpx.post(
                f"{self.base_url}/labs/validate", json=definition, timeout=self.timeout
            )
        except httpx.HTTPError as exc:
            return ValidateLabResult(success=False, detail=f"Could not validate the lab: {exc}")

        if response.status_code != 200:
            return ValidateLabResult(
                success=False, detail=f"Could not validate the lab (status {response.status_code})."
            )

        body = response.json()
        errors = [
            FieldIssue(
                location=[str(part) for part in item.get("location", [])],
                message=item.get("message", ""),
                issue_type=item.get("issue_type", ""),
            )
            for item in body.get("errors", [])
        ]
        return ValidateLabResult(success=True, valid=body.get("valid", False), errors=errors)

    def create_lab(self, definition: dict[str, object]) -> CreateLabResult:
        try:
            response = httpx.post(f"{self.base_url}/labs", json=definition, timeout=self.timeout)
        except httpx.HTTPError as exc:
            return CreateLabResult(success=False, detail=f"Could not save the lab: {exc}")

        if response.status_code == 201:
            body = response.json()
            return CreateLabResult(success=True, lab_id=body.get("id"))

        if response.status_code == 422:
            body = response.json()
            errors = [
                FieldIssue(
                    location=[str(part) for part in item.get("loc", [])],
                    message=item.get("msg", ""),
                    issue_type=item.get("type", ""),
                )
                for item in body.get("detail", [])
            ]
            return CreateLabResult(success=False, errors=errors, detail="The lab is invalid.")

        return CreateLabResult(
            success=False, detail=f"Could not save the lab (status {response.status_code})."
        )

    def import_lab(self, definition: dict[str, object]) -> ImportLabResult:
        try:
            response = httpx.post(
                f"{self.base_url}/labs/import", json=definition, timeout=self.timeout
            )
        except httpx.ConnectError:
            return ImportLabResult(
                success=False, detail="Could not connect to the Practicum API to import the lab."
            )
        except httpx.TimeoutException:
            return ImportLabResult(
                success=False, detail="The Practicum API did not respond in time while importing."
            )
        except httpx.HTTPError as exc:
            return ImportLabResult(success=False, detail=f"Could not import the lab: {exc}")

        if response.status_code == 422:
            # Only reachable when the body is not a JSON object at all; the desktop checks
            # that before sending, but a stale/odd server build could still answer this way.
            return ImportLabResult(
                success=False, detail="The file does not contain a lab definition object."
            )
        if response.status_code != 200:
            return ImportLabResult(
                success=False, detail=f"Could not import the lab (status {response.status_code})."
            )

        try:
            body = response.json()
        except ValueError:
            return ImportLabResult(
                success=False, detail="The Practicum API returned an unexpected import response."
            )
        if not isinstance(body, dict):
            return ImportLabResult(
                success=False, detail="The Practicum API returned an unexpected import response."
            )

        if body.get("imported") and isinstance(body.get("lab"), dict):
            lab = body["lab"]
            return ImportLabResult(
                success=True, lab_id=lab.get("id"), lab_name=lab.get("name") or ""
            )

        errors = [
            FieldIssue(
                location=[str(part) for part in item.get("location", [])],
                message=item.get("message", ""),
                issue_type=item.get("issue_type", ""),
            )
            for item in body.get("errors", [])
        ]
        return ImportLabResult(
            success=False,
            errors=errors,
            detail="The lab file is not a valid Practicum lab." if errors else "The import was rejected.",
        )

    def start_lab(self, lab_id: str) -> StartResult:
        try:
            response = httpx.post(
                f"{self.base_url}/labs/{lab_id}/start", timeout=self.lifecycle_timeout
            )
        except httpx.TimeoutException:
            return StartResult(
                success=False,
                detail=(
                    "The Practicum API did not finish starting the lab in time. It may still "
                    "be pulling images; check the lab's status before trying again."
                ),
            )
        except httpx.HTTPError as exc:
            return StartResult(success=False, detail=f"Could not start the lab: {exc}")

        if response.status_code != 200:
            return StartResult(success=False, detail=f"Could not start the lab (status {response.status_code}).")

        body = response.json()
        if body.get("success"):
            return StartResult(success=True, detail="Lab started.")

        errors = body.get("errors") or []
        detail = errors[0]["message"] if errors else "The lab failed to start."
        return StartResult(success=False, detail=detail)

    def reset_lab(self, lab_id: str) -> StartResult:
        try:
            response = httpx.post(
                f"{self.base_url}/labs/{lab_id}/reset", timeout=self.lifecycle_timeout
            )
        except httpx.HTTPError as exc:
            return StartResult(success=False, detail=f"Could not reset the lab: {exc}")

        if response.status_code != 200:
            return StartResult(
                success=False, detail=f"Could not reset the lab (status {response.status_code})."
            )

        body = response.json()
        if body.get("success"):
            return StartResult(success=True, detail="Lab reset.")
        errors = body.get("errors") or []
        detail = errors[0]["message"] if errors else "The lab failed to reset."
        return StartResult(success=False, detail=detail)

    def get_status(self, lab_id: str) -> StatusResult:
        try:
            response = httpx.get(f"{self.base_url}/labs/{lab_id}/status", timeout=self.timeout)
        except httpx.HTTPError as exc:
            return StatusResult(success=False, detail=f"Could not load the lab status: {exc}")

        if response.status_code != 200:
            return StatusResult(
                success=False,
                detail=f"Could not load the lab status (status {response.status_code}).",
            )

        try:
            body = response.json()
        except ValueError:
            return StatusResult(
                success=False, detail="The Practicum API returned an unexpected status response."
            )

        resources = [
            ResourceStatusInfo(
                kind=item.get("kind", ""),
                id=item.get("id", ""),
                name=item.get("name", ""),
                exists=bool(item.get("exists")),
                status=item.get("status"),
                error=item.get("error"),
            )
            for item in body.get("resources", [])
        ]
        errors = body.get("errors") or []
        return StatusResult(
            success=True,
            lab_status=(body.get("lab") or {}).get("status", ""),
            resources=resources,
            detail=errors[0]["message"] if errors else "",
        )

    def check_networks(self, lab_id: str) -> NetworkCheckResult:
        try:
            response = httpx.get(f"{self.base_url}/labs/{lab_id}/networks", timeout=self.timeout)
        except httpx.HTTPError as exc:
            return NetworkCheckResult(success=False, detail=f"Could not check networks: {exc}")
        return self._parse_network_check(response, "Could not check networks")

    def apply_subnet_recommendation(self, lab_id: str, network_id: str) -> NetworkCheckResult:
        try:
            response = httpx.post(
                f"{self.base_url}/labs/{lab_id}/networks/apply-recommendation",
                json={"network_id": network_id},
                timeout=self.timeout,
            )
        except httpx.HTTPError as exc:
            return NetworkCheckResult(
                success=False, detail=f"Could not apply the recommended subnet: {exc}"
            )
        return self._parse_network_check(response, "Could not apply the recommended subnet")

    def remove_leftover_network(self, lab_id: str, network_name: str) -> NetworkCheckResult:
        try:
            response = httpx.post(
                f"{self.base_url}/labs/{lab_id}/networks/remove-leftover",
                json={"network_name": network_name},
                timeout=self.lifecycle_timeout,
            )
        except httpx.HTTPError as exc:
            return NetworkCheckResult(
                success=False, detail=f"Could not remove the leftover network: {exc}"
            )
        return self._parse_network_check(response, "Could not remove the leftover network")

    @staticmethod
    def _parse_network_check(response: httpx.Response, failure_prefix: str) -> NetworkCheckResult:
        if response.status_code != 200:
            detail = None
            if response.headers.get("content-type", "").startswith("application/json"):
                try:
                    detail = response.json().get("detail")
                except ValueError:
                    detail = None
            return NetworkCheckResult(
                success=False,
                detail=detail or f"{failure_prefix} (status {response.status_code}).",
            )

        try:
            body = response.json()
        except ValueError:
            return NetworkCheckResult(
                success=False, detail="The Practicum API returned an unexpected response."
            )

        if body.get("error"):
            return NetworkCheckResult(success=False, detail=body["error"])

        conflicts = [
            SubnetConflict(
                network_id=item["network_id"],
                subnet=item["subnet"],
                reason=item["reason"],
                owner_network_name=item["owner_network_name"],
                owner_subnet=item["owner_subnet"],
                owner_lab_id=item.get("owner_lab_id"),
                owner_lab_name=item.get("owner_lab_name"),
                owner_lab_status=item.get("owner_lab_status"),
                owner_container_count=item.get("owner_container_count", 0),
                recommended_subnet=item.get("recommended_subnet"),
            )
            for item in body.get("conflicts", [])
        ]
        return NetworkCheckResult(
            success=True, has_conflicts=body.get("has_conflicts", False), conflicts=conflicts
        )

    def get_preview(self, lab_id: str) -> PreviewResult:
        try:
            response = httpx.get(f"{self.base_url}/labs/{lab_id}/preview", timeout=self.timeout)
        except httpx.HTTPError as exc:
            return PreviewResult(success=False, detail=f"Could not load the lab preview: {exc}")

        if response.status_code != 200:
            return PreviewResult(
                success=False, detail=f"Could not load the lab preview (status {response.status_code})."
            )

        body = response.json()
        manual = body.get("manual") or {}
        sections = [
            ManualSectionInfo(
                id=section["id"],
                title=section["title"],
                content_markdown=section["content_markdown"],
                tasks=[
                    ManualTaskInfo(id=task["id"], text=task["text"])
                    for task in section.get("tasks", [])
                ],
            )
            for section in manual.get("sections", [])
        ]
        estimated = body.get("estimated_resources") or {}
        port_mappings = [
            PortMappingInfo(
                host=mapping["host"], container=mapping["container"], protocol=mapping["protocol"]
            )
            for mapping in estimated.get("port_mappings", [])
        ]
        topology_body = body.get("topology") or {}
        topology = TopologyInfo(
            nodes=[
                TopologyNodeInfo(id=node["id"], image=node["image"])
                for node in topology_body.get("nodes", [])
            ],
            networks=[
                TopologyNetworkInfo(id=network["id"], subnet=network["subnet"])
                for network in topology_body.get("networks", [])
            ],
            interfaces=[
                TopologyInterfaceInfo(
                    node=interface["node"],
                    network=interface["network"],
                    address=interface["address"],
                )
                for interface in topology_body.get("interfaces", [])
            ],
        )
        return PreviewResult(
            success=True,
            name=body.get("name", ""),
            description=body.get("description") or "",
            author=body.get("author") or "",
            version=body.get("version") or "",
            required_images=list(body.get("required_images", [])),
            estimated_resources=EstimatedResourcesInfo(
                total_cpu=estimated.get("total_cpu"),
                total_memory_mb=estimated.get("total_memory_mb"),
            ),
            topology=topology,
            manual_sections=sections,
            port_mappings=port_mappings,
        )
