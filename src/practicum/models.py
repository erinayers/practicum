from ipaddress import IPv4Address, IPv4Interface, IPv4Network
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

# Major schema versions this build can read. Bump when the spec changes incompatibly;
# minor versions within a supported major are accepted as-is.
SUPPORTED_SCHEMA_MAJOR_VERSIONS = (1,)


PortNumber = Annotated[int, Field(ge=1, le=65535)]
EnvironmentName = Annotated[str, Field(pattern=r"^[A-Za-z_][A-Za-z0-9_]*$")]


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


class Lab(LabDefinition):
    id: str
    status: str = "defined"


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


class RuntimeResourceStatus(BaseModel):
    kind: str
    id: str
    name: str
    exists: bool
    status: str | None = None
    error: str | None = None


class RuntimeStatusResult(BaseModel):
    lab: Lab
    resources: list[RuntimeResourceStatus] = Field(default_factory=list)
    errors: list[RuntimeIssue] = Field(default_factory=list)


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

