from datetime import datetime
from ipaddress import IPv4Address, IPv4Interface, IPv4Network
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

# Major schema versions this build can read. Bump when the spec changes incompatibly;
# minor versions within a supported major are accepted as-is.
SUPPORTED_SCHEMA_MAJOR_VERSIONS = (1,)


PortNumber = Annotated[int, Field(ge=1, le=65535)]
EnvironmentName = Annotated[str, Field(pattern=r"^[A-Za-z_][A-Za-z0-9_]*$")]
# Kernel parameters Docker lets an unprivileged container set (`docker run --sysctl`), e.g.
# net.ipv4.ip_forward=1 for a router node.
SysctlName = Annotated[str, Field(pattern=r"^(net|kernel|fs)\.[A-Za-z0-9_.\-]+$")]


class PortMapping(BaseModel):
    model_config = ConfigDict(extra="forbid")

    host: PortNumber
    container: PortNumber
    protocol: Literal["tcp", "udp"] = "tcp"


class ResourceRequirements(BaseModel):
    model_config = ConfigDict(extra="forbid")

    cpu: float | None = Field(default=None, gt=0)
    memory_mb: int | None = Field(default=None, gt=0)
    shm_size_mb: int | None = Field(default=None, gt=0)
    exposed_ports: list[PortNumber] = Field(default_factory=list)
    port_mappings: list[PortMapping] = Field(default_factory=list)
    sysctls: dict[SysctlName, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_ports(self) -> "ResourceRequirements":
        if len(self.exposed_ports) != len(set(self.exposed_ports)):
            raise ValueError("exposed ports must be unique")

        mapped_hosts = [(mapping.host, mapping.protocol) for mapping in self.port_mappings]
        if len(mapped_hosts) != len(set(mapped_hosts)):
            raise ValueError("host port mappings must be unique per protocol")

        exposed_hosts = [(port, "tcp") for port in self.exposed_ports]
        overlaps = set(exposed_hosts) & set(mapped_hosts)
        if overlaps:
            raise ValueError("exposed ports cannot overlap port mappings")

        return self


class ManualTask(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(pattern=r"^[a-z][a-z0-9-]*$")
    text: str = Field(min_length=1, max_length=500)


class ManualSection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(pattern=r"^[a-z][a-z0-9-]*$")
    title: str = Field(min_length=1, max_length=120)
    content_markdown: str = Field(min_length=1, max_length=10000)
    tasks: list[ManualTask] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_tasks(self) -> "ManualSection":
        task_ids = [task.id for task in self.tasks]

        if len(task_ids) != len(set(task_ids)):
            raise ValueError("manual task ids must be unique within a section")

        return self


class LabManual(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sections: list[ManualSection] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_sections(self) -> "LabManual":
        section_ids = [section.id for section in self.sections]

        if len(section_ids) != len(set(section_ids)):
            raise ValueError("manual section ids must be unique")

        return self


class Node(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(pattern=r"^[a-z][a-z0-9-]*$")
    image: str = Field(min_length=1)
    command: list[str] | None = Field(default_factory=lambda: ["sleep", "infinity"])
    environment: dict[EnvironmentName, str] = Field(default_factory=dict)
    resources: ResourceRequirements | None = None


class Network(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(pattern=r"^[a-z][a-z0-9-]*$")
    subnet: IPv4Network


class Interface(BaseModel):
    model_config = ConfigDict(extra="forbid")

    node: str
    network: str
    address: IPv4Interface


class LabDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = Field(default="1.0", pattern=r"^\d+\.\d+$")
    name: str = Field(min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=2000)
    author: str | None = Field(default=None, min_length=1, max_length=120)
    version: str | None = Field(default=None, min_length=1, max_length=40)
    manual: LabManual | None = None
    nodes: list[Node] = Field(min_length=1)
    networks: list[Network] = Field(min_length=1)
    interfaces: list[Interface] = Field(min_length=1)

    @field_validator("schema_version")
    @classmethod
    def validate_schema_version_supported(cls, value: str) -> str:
        major = int(value.split(".", 1)[0])
        if major not in SUPPORTED_SCHEMA_MAJOR_VERSIONS:
            supported = ", ".join(f"{m}.x" for m in SUPPORTED_SCHEMA_MAJOR_VERSIONS)
            raise ValueError(
                f"schema_version '{value}' is not supported by this version of Practicum "
                f"(supported: {supported})"
            )
        return value

    @model_validator(mode="after")
    def validate_topology(self) -> "LabDefinition":
        node_ids = [node.id for node in self.nodes]
        network_ids = [network.id for network in self.networks]

        if len(node_ids) != len(set(node_ids)):
            raise ValueError("node ids must be unique")
        if len(network_ids) != len(set(network_ids)):
            raise ValueError("network ids must be unique")

        for index, network in enumerate(self.networks):
            for other in self.networks[index + 1 :]:
                if network.subnet.overlaps(other.subnet):
                    raise ValueError(
                        f"network '{network.id}' ({network.subnet}) overlaps network "
                        f"'{other.id}' ({other.subnet})"
                    )

        networks = {network.id: network.subnet for network in self.networks}
        attachment_keys: set[tuple[str, str]] = set()
        addresses: set[IPv4Address] = set()

        for interface in self.interfaces:
            if interface.node not in node_ids:
                raise ValueError(f"interface references unknown node '{interface.node}'")
            if interface.network not in networks:
                raise ValueError(f"interface references unknown network '{interface.network}'")
            if interface.address.ip not in networks[interface.network]:
                raise ValueError(
                    f"address '{interface.address}' is outside network '{interface.network}'"
                )

            attachment = (interface.node, interface.network)
            if attachment in attachment_keys:
                raise ValueError(
                    f"node '{interface.node}' has multiple interfaces on '{interface.network}'"
                )
            if interface.address.ip in addresses:
                raise ValueError(f"address '{interface.address}' is assigned more than once")

            attachment_keys.add(attachment)
            addresses.add(interface.address.ip)

        return self


# How a stored lab came to exist on this machine. Bookkeeping only: it is never part of the
# portable spec (see LAB_RUNTIME_FIELDS / LabService.export).
LabOrigin = Literal["designer", "imported", "quick_start"]

# Fields of `Lab` that describe local state rather than the lab itself. Excluded from export
# and preserved when the definition is rewritten (port/subnet recommendations).
LAB_RUNTIME_FIELDS = frozenset(
    {"id", "status", "origin", "source_file", "created_at", "last_started_at", "last_error"}
)


class Lab(LabDefinition):
    id: str
    status: str = "defined"
    origin: LabOrigin = "designer"
    source_file: str | None = None  # file name the lab was imported from, when known
    created_at: datetime | None = None
    last_started_at: datetime | None = None
    # Message of the most recent failed lifecycle action (start/stop/reset); cleared by the
    # next successful one. Lets a UI explain an `error` status without replaying the call.
    last_error: str | None = None


class ResourceEstimate(BaseModel):
    total_cpu: float | None = None
    total_memory_mb: int | None = None
    exposed_ports: list[int] = Field(default_factory=list)
    port_mappings: list[PortMapping] = Field(default_factory=list)


class TopologyPreview(BaseModel):
    nodes: list[Node]
    networks: list[Network]
    interfaces: list[Interface]


class LabPreview(BaseModel):
    id: str
    status: str
    schema_version: str
    name: str
    description: str | None = None
    author: str | None = None
    version: str | None = None
    required_images: list[str]
    estimated_resources: ResourceEstimate
    topology: TopologyPreview
    manual: LabManual | None = None


class ValidationIssue(BaseModel):
    location: list[str]
    message: str
    issue_type: str


class ValidationResult(BaseModel):
    valid: bool
    lab: LabDefinition | None = None
    errors: list[ValidationIssue] = Field(default_factory=list)


class ImportResult(BaseModel):
    imported: bool
    lab: Lab | None = None
    errors: list[ValidationIssue] = Field(default_factory=list)


class RuntimeIssue(BaseModel):
    message: str
    command: list[str] | None = None


class RuntimeActionResult(BaseModel):
    success: bool
    lab: Lab
    errors: list[RuntimeIssue] = Field(default_factory=list)
    # True when the action was accepted and continues in the background (POST /start with
    # wait=false): `success` then only means "started working"; poll GET /status for the end.
    pending: bool = False


class RuntimeResourceStatus(BaseModel):
    kind: str
    id: str
    name: str
    exists: bool
    status: str | None = None
    error: str | None = None
    # Free-text progress a running container reports about itself, e.g. the quick start's
    # "Practicum: installing packages (git curl) …" marker (see desktop quickstart.py).
    note: str | None = None


NodeStartStep = Literal[
    "waiting",  # start requested, this node's turn has not come yet
    "checking_image",  # `docker image inspect`
    "pulling_image",  # `docker pull`, percent/detail updated as layers complete
    "creating_container",  # `docker run` / `docker start`
    "connecting_networks",  # extra `docker network connect`s
    "ready",
    "failed",
]


class NodeStartProgress(BaseModel):
    """Where one node is in the start sequence. `percent` is only meaningful while pulling
    (share of image layers already pulled, 0-100); `detail` is a short human-readable line
    (e.g. "3 of 7 layers", or the failure message)."""

    node_id: str
    image: str
    step: NodeStartStep = "waiting"
    percent: int | None = None
    detail: str | None = None


class RuntimeStatusResult(BaseModel):
    lab: Lab
    resources: list[RuntimeResourceStatus] = Field(default_factory=list)
    errors: list[RuntimeIssue] = Field(default_factory=list)
    # Per-node start progress for the most recent start of this lab (empty until a start
    # has been requested). While `lab.status` is "starting" this is live; afterwards it holds
    # the final per-node outcome so a failure can be attributed to its node.
    progress: list[NodeStartProgress] = Field(default_factory=list)


class PortConflict(BaseModel):
    node_id: str
    host_port: int
    container_port: int
    protocol: Literal["tcp", "udp"]
    reason: Literal["duplicate_in_spec", "reserved_by_practicum_api", "in_use_on_host"]
    recommended_port: int | None = None


class PortCheckResult(BaseModel):
    lab_id: str
    has_conflicts: bool
    conflicts: list[PortConflict] = Field(default_factory=list)


class DockerNetworkInfo(BaseModel):
    """A network as seen on the Docker host (any driver, Practicum-owned or not)."""

    name: str
    subnets: list[IPv4Network] = Field(default_factory=list)
    lab_id: str | None = None  # value of the practicum.lab_id label, if any
    container_names: list[str] = Field(default_factory=list)


class SubnetConflict(BaseModel):
    network_id: str
    subnet: IPv4Network
    reason: Literal["overlaps_other_lab", "overlaps_leftover", "overlaps_docker_network"]
    owner_network_name: str
    owner_subnet: IPv4Network
    owner_lab_id: str | None = None
    owner_lab_name: str | None = None
    owner_lab_status: str | None = None
    owner_container_count: int = 0
    recommended_subnet: IPv4Network | None = None


class NetworkCheckResult(BaseModel):
    lab_id: str
    has_conflicts: bool
    conflicts: list[SubnetConflict] = Field(default_factory=list)
    error: str | None = None  # set when Docker could not be queried; conflicts unknown


class PracticumContainerInfo(BaseModel):
    """A container on the Docker host carrying Practicum's labels."""

    name: str
    lab_id: str | None = None
    status: str | None = None


class LeftoverSweepResult(BaseModel):
    """Outcome of removing Practicum resources whose lab this API no longer knows."""

    removed_containers: list[str] = Field(default_factory=list)
    removed_networks: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    error: str | None = None  # Docker could not be queried at all


class ApplySubnetRecommendationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    network_id: str


class RemoveLeftoverNetworkRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    network_name: str


class ApplyPortRecommendationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    node_id: str
    host_port: PortNumber
    protocol: Literal["tcp", "udp"] = "tcp"

