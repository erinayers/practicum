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


def test_lab_definition_accepts_minor_versions_of_supported_schema(
    lab_definition: dict,
) -> None:
    lab_definition["schema_version"] = "1.7"

    definition = LabDefinition.model_validate(lab_definition)

    assert definition.schema_version == "1.7"


def test_lab_definition_rejects_unsupported_schema_major_version(
    lab_definition: dict,
) -> None:
    lab_definition["schema_version"] = "2.0"

    with pytest.raises(ValidationError) as exc_info:
        LabDefinition.model_validate(lab_definition)

    error = exc_info.value.errors()[0]
    assert error["loc"] == ("schema_version",)
    assert "not supported by this version of Practicum" in error["msg"]
    assert "1.x" in error["msg"]


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


def test_rejects_duplicate_ip_assignment(lab_definition: dict) -> None:
    lab_definition["interfaces"].append(
        {"node": "host-b", "network": "left", "address": "10.0.1.10/24"}
    )

    with pytest.raises(ValidationError, match="assigned more than once"):
        LabDefinition.model_validate(lab_definition)


def test_rejects_overlapping_subnets_within_a_lab(lab_definition: dict) -> None:
    lab_definition["networks"].append({"id": "left-wide", "subnet": "10.0.0.0/16"})
    lab_definition["interfaces"].append(
        {"node": "host-b", "network": "left-wide", "address": "10.0.9.10/16"}
    )

    with pytest.raises(ValidationError, match="overlaps network 'left-wide'"):
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


def test_resource_requirements_accept_namespaced_sysctls_only() -> None:
    from practicum.models import ResourceRequirements

    ok = ResourceRequirements(sysctls={"net.ipv4.ip_forward": "1"})
    assert ok.sysctls == {"net.ipv4.ip_forward": "1"}
    with pytest.raises(ValidationError):
        ResourceRequirements(sysctls={"vm.swappiness": "1"})
    with pytest.raises(ValidationError):
        ResourceRequirements(sysctls={"net.ipv4.ip_forward=1": "1"})


# ----- node os / shell (windows quick start, phase 8) ------------------------------------------


def _one_node_lab(**node_extra) -> dict:
    node = {"id": "host", "image": "alpine:3.21", **node_extra}
    return {
        "name": "One host",
        "nodes": [node],
        "networks": [{"id": "lan", "subnet": "10.0.1.0/24"}],
        "interfaces": [{"node": "host", "network": "lan", "address": "10.0.1.10/24"}],
    }


def test_node_defaults_to_linux_with_the_os_default_shell() -> None:
    from practicum.models import LabDefinition

    lab = LabDefinition.model_validate(_one_node_lab())

    assert lab.nodes[0].os == "linux"
    assert lab.nodes[0].shell is None
    assert lab.nodes[0].effective_shell == "bash"
    assert lab.container_os == "linux"


def test_windows_node_declares_its_os_and_defaults_to_powershell() -> None:
    from practicum.models import LabDefinition

    lab = LabDefinition.model_validate(
        _one_node_lab(image="mcr.microsoft.com/windows/servercore:ltsc2022", os="windows")
    )

    assert lab.nodes[0].os == "windows"
    assert lab.nodes[0].effective_shell == "powershell"
    assert lab.container_os == "windows"
    # explicit cmd is allowed on Windows, and survives a dump/reload round trip
    lab_cmd = LabDefinition.model_validate(_one_node_lab(image="x", os="windows", shell="cmd"))
    assert LabDefinition.model_validate(lab_cmd.model_dump()).nodes[0].shell == "cmd"


def test_shell_must_match_the_node_os() -> None:
    from practicum.models import LabDefinition

    with pytest.raises(ValidationError, match="shell 'powershell' is not available on a linux"):
        LabDefinition.model_validate(_one_node_lab(shell="powershell"))
    with pytest.raises(ValidationError, match="shell 'bash' is not available on a windows"):
        LabDefinition.model_validate(_one_node_lab(os="windows", shell="bash"))
    with pytest.raises(ValidationError):
        LabDefinition.model_validate(_one_node_lab(os="freebsd"))


def test_windows_nodes_reject_linux_only_resources() -> None:
    from practicum.models import LabDefinition

    with pytest.raises(ValidationError, match="shm_size_mb is not supported on windows"):
        LabDefinition.model_validate(_one_node_lab(os="windows", resources={"shm_size_mb": 64}))
    with pytest.raises(ValidationError, match="sysctls are not supported on windows"):
        LabDefinition.model_validate(
            _one_node_lab(os="windows", resources={"sysctls": {"net.ipv4.ip_forward": "1"}})
        )


def test_lab_nodes_must_share_one_operating_system() -> None:
    from practicum.models import LabDefinition

    lab = _one_node_lab()
    lab["nodes"].append({"id": "win", "image": "servercore:ltsc2022", "os": "windows"})
    lab["interfaces"].append({"node": "win", "network": "lan", "address": "10.0.1.11/24"})

    with pytest.raises(ValidationError, match="all nodes must use the same operating system"):
        LabDefinition.model_validate(lab)


def test_manual_section_can_require_a_screenshot() -> None:
    plain = ManualSection(id="s", title="T", content_markdown="c")
    assert plain.requires_screenshot is False
    evidence = ManualSection(id="s", title="T", content_markdown="c", requires_screenshot=True)
    assert evidence.requires_screenshot is True
    assert ManualSection.model_validate(evidence.model_dump()).requires_screenshot is True
