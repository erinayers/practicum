import pytest
from pydantic import ValidationError

from practicum.models import (
    Lab,
    LabDefinition,
    LabManual,
    ManualSection,
    ManualTask,
    Network,
    Node,
    PortMapping,
    ResourceRequirements,
)


def test_lab_definition_defaults_schema_version_and_optional_fields(
    lab_definition: dict,
) -> None:
    lab_definition.pop("schema_version")
    lab_definition.pop("description")
    lab_definition.pop("author")
    lab_definition.pop("version")
    lab_definition.pop("manual")

    definition = LabDefinition.model_validate(lab_definition)

    assert definition.schema_version == "1.0"
    assert definition.description is None
    assert definition.author is None
    assert definition.version is None
    assert definition.manual is None


def test_lab_defaults_status_to_defined(lab_definition: dict) -> None:
    definition = LabDefinition.model_validate(lab_definition)

    lab = Lab(id="test-id", **definition.model_dump())

    assert lab.status == "defined"


def test_rejects_duplicate_node_ids(lab_definition: dict) -> None:
    lab_definition["nodes"][2]["id"] = lab_definition["nodes"][0]["id"]

    with pytest.raises(ValidationError, match="node ids must be unique"):
        LabDefinition.model_validate(lab_definition)


def test_rejects_duplicate_network_ids(lab_definition: dict) -> None:
    lab_definition["networks"][1]["id"] = lab_definition["networks"][0]["id"]

    with pytest.raises(ValidationError, match="network ids must be unique"):
        LabDefinition.model_validate(lab_definition)


def test_rejects_interface_referencing_unknown_node(lab_definition: dict) -> None:
    lab_definition["interfaces"][0]["node"] = "unknown-node"

    with pytest.raises(ValidationError, match="references unknown node"):
        LabDefinition.model_validate(lab_definition)


def test_rejects_interface_referencing_unknown_network(lab_definition: dict) -> None:
    lab_definition["interfaces"][0]["network"] = "unknown-network"

    with pytest.raises(ValidationError, match="references unknown network"):
        LabDefinition.model_validate(lab_definition)


def test_rejects_duplicate_attachment_on_same_network(lab_definition: dict) -> None:
    lab_definition["interfaces"].append(
        {"node": "host-a", "network": "left", "address": "10.0.1.11/24"}
    )

    with pytest.raises(ValidationError, match="multiple interfaces on"):
        LabDefinition.model_validate(lab_definition)


def test_rejects_duplicate_ip_assignment_across_networks(lab_definition: dict) -> None:
    lab_definition["networks"].append({"id": "left2", "subnet": "10.0.1.0/24"})
    lab_definition["interfaces"].append(
        {"node": "host-b", "network": "left2", "address": "10.0.1.10/24"}
    )

    with pytest.raises(ValidationError, match="assigned more than once"):
        LabDefinition.model_validate(lab_definition)


def test_node_defaults_command_to_sleep_infinity() -> None:
    node = Node(id="node-a", image="alpine:3.21")

    assert node.command == ["sleep", "infinity"]
    assert node.environment == {}
    assert node.resources is None


def test_node_rejects_invalid_id_pattern() -> None:
    with pytest.raises(ValidationError):
        Node(id="Node1", image="alpine:3.21")


def test_network_rejects_invalid_subnet() -> None:
    with pytest.raises(ValidationError):
        Network(id="left", subnet="not-a-subnet")


def test_port_mapping_defaults_protocol_to_tcp() -> None:
    mapping = PortMapping(host=8080, container=80)

    assert mapping.protocol == "tcp"


def test_resource_requirements_rejects_duplicate_port_mappings_same_protocol() -> None:
    with pytest.raises(ValidationError, match="host port mappings must be unique per protocol"):
        ResourceRequirements(
            port_mappings=[
                {"host": 8080, "container": 80},
                {"host": 8080, "container": 81},
            ]
        )


def test_resource_requirements_allows_same_host_port_with_different_protocol() -> None:
    requirements = ResourceRequirements(
        port_mappings=[
            {"host": 8080, "container": 80, "protocol": "tcp"},
            {"host": 8080, "container": 80, "protocol": "udp"},
        ]
    )

    assert len(requirements.port_mappings) == 2


def test_manual_rejects_duplicate_section_ids() -> None:
    section = {
        "id": "overview",
        "title": "Overview",
        "content_markdown": "content",
        "tasks": [],
    }

    with pytest.raises(ValidationError, match="manual section ids must be unique"):
        LabManual(sections=[section, section])


def test_manual_section_rejects_duplicate_task_ids() -> None:
    task = {"id": "task-a", "text": "Do something"}

    with pytest.raises(ValidationError, match="manual task ids must be unique within a section"):
        ManualSection(
            id="overview",
            title="Overview",
            content_markdown="content",
            tasks=[task, task],
        )


def test_manual_task_rejects_invalid_id_pattern() -> None:
    with pytest.raises(ValidationError):
        ManualTask(id="Task1", text="Do something")
