from fastapi.testclient import TestClient

from practicum import ports
from practicum.main import app, service
from practicum.models import (
    LAB_RUNTIME_FIELDS,
    DockerEngineInfo,
    DockerNetworkInfo,
    Lab,
    NodeStartProgress,
    PracticumContainerInfo,
    RuntimeResourceStatus,
)
from practicum.runtime import RuntimeFailure


class RecordingRuntime:
    def __init__(self) -> None:
        self.started_labs: list[Lab] = []
        self.stopped_labs: list[Lab] = []
        self.reset_labs: list[Lab] = []
        self.containers: list[PracticumContainerInfo] = []
        self.networks: list[DockerNetworkInfo] = []
        self.removed_containers: list[str] = []
        self.removed_networks: list[str] = []
        self.engine = DockerEngineInfo(
            available=True, os_type="linux", server_version="27.3.1", detail="Linux containers"
        )

    def engine_info(self) -> DockerEngineInfo:
        return self.engine

    def list_practicum_containers(self) -> list[PracticumContainerInfo]:
        return list(self.containers)

    def remove_container(self, name: str) -> None:
        self.removed_containers.append(name)

    def list_networks(self) -> list[DockerNetworkInfo]:
        return list(self.networks)

    def remove_network(self, network: DockerNetworkInfo) -> None:
        self.removed_networks.append(network.name)

    def start(self, lab: Lab, on_progress=None) -> None:
        self.started_labs.append(lab.model_copy(deep=True))
        if on_progress is not None:
            for node in lab.nodes:
                on_progress(
                    NodeStartProgress(node_id=node.id, image=node.image, step="ready")
                )

    def stop(self, lab: Lab) -> None:
        self.stopped_labs.append(lab.model_copy(deep=True))

    def reset(self, lab: Lab) -> None:
        self.reset_labs.append(lab.model_copy(deep=True))

    def status(self, lab: Lab) -> list[RuntimeResourceStatus]:
        return [
            RuntimeResourceStatus(
                kind="network",
                id=lab.networks[0].id,
                name=f"practicum-test-{lab.networks[0].id}",
                exists=True,
                status="present",
            ),
            RuntimeResourceStatus(
                kind="container",
                id=lab.nodes[0].id,
                name=f"practicum-test-{lab.nodes[0].id}",
                exists=True,
                status="running",
            ),
        ]


class FailingRuntime:
    def engine_info(self) -> DockerEngineInfo:
        raise RuntimeFailure("Docker is unavailable", ["docker", "info"])

    def start(self, lab: Lab, on_progress=None) -> None:
        raise RuntimeFailure("Docker is unavailable", ["docker", "ps"])

    def list_practicum_containers(self) -> list[PracticumContainerInfo]:
        raise RuntimeFailure("Docker is unavailable", ["docker", "ps"])

    def stop(self, lab: Lab) -> None:
        raise RuntimeFailure("Container could not stop", ["docker", "stop", "container"])

    def reset(self, lab: Lab) -> None:
        raise RuntimeFailure("Resource cleanup failed", ["docker", "rm", "-f", "container"])

    def status(self, lab: Lab) -> list[RuntimeResourceStatus]:
        raise RuntimeFailure("Docker is unavailable", ["docker", "inspect"])


def test_health(client: TestClient) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_validate_lab(client: TestClient, lab_definition: dict) -> None:
    response = client.post("/labs/validate", json=lab_definition)

    assert response.status_code == 200
    assert response.json()["valid"] is True
    assert response.json()["errors"] == []


def test_validate_lab_accepts_older_spec_without_optional_metadata(
    client: TestClient, lab_definition: dict
) -> None:
    lab_definition.pop("schema_version")
    lab_definition.pop("description")
    lab_definition.pop("author")
    lab_definition.pop("version")
    lab_definition.pop("manual")

    response = client.post("/labs/validate", json=lab_definition)

    assert response.status_code == 200
    lab = response.json()["lab"]
    assert lab["schema_version"] == "1.0"
    assert lab["description"] is None
    assert lab["author"] is None
    assert lab["version"] is None
    assert lab["manual"] is None


def test_create_and_get_lab(client: TestClient, lab_definition: dict) -> None:
    create_response = client.post("/labs", json=lab_definition)

    assert create_response.status_code == 201
    created = create_response.json()
    assert created["name"] == lab_definition["name"]
    assert created["description"] == lab_definition["description"]
    assert created["author"] == lab_definition["author"]
    assert created["version"] == lab_definition["version"]
    assert created["manual"] == lab_definition["manual"]
    assert created["status"] == "defined"

    get_response = client.get(f"/labs/{created['id']}")
    assert get_response.status_code == 200
    assert get_response.json() == created


def test_export_lab_returns_portable_spec(client: TestClient, lab_definition: dict) -> None:
    create_response = client.post("/labs", json=lab_definition)
    created = create_response.json()

    export_response = client.get(f"/labs/{created['id']}/export")

    assert export_response.status_code == 200
    exported = export_response.json()
    for field in LAB_RUNTIME_FIELDS:
        assert field not in exported
    expected = {key: value for key, value in created.items() if key not in LAB_RUNTIME_FIELDS}
    assert exported == expected


def test_exported_lab_can_be_validated(client: TestClient, lab_definition: dict) -> None:
    create_response = client.post("/labs", json=lab_definition)
    exported = client.get(f"/labs/{create_response.json()['id']}/export").json()

    response = client.post("/labs/validate", json=exported)

    assert response.status_code == 200
    assert response.json()["valid"] is True


def test_export_missing_lab_returns_404(client: TestClient) -> None:
    response = client.get("/labs/not-a-real-id/export")

    assert response.status_code == 404


def test_preview_imported_lab(client: TestClient, lab_definition: dict) -> None:
    import_response = client.post("/labs/import", json=lab_definition)
    imported = import_response.json()["lab"]

    preview_response = client.get(f"/labs/{imported['id']}/preview")

    assert preview_response.status_code == 200
    preview = preview_response.json()
    assert preview["id"] == imported["id"]
    assert preview["name"] == lab_definition["name"]
    assert preview["description"] == lab_definition["description"]
    assert preview["required_images"] == ["alpine:3.21"]
    assert preview["estimated_resources"] == {
        "total_cpu": 2.0,
        "total_memory_mb": 512,
        "exposed_ports": [22],
        "port_mappings": [{"host": 2222, "container": 22, "protocol": "tcp"}],
    }
    assert preview["topology"]["nodes"] == imported["nodes"]
    assert preview["topology"]["networks"] == imported["networks"]
    assert preview["topology"]["interfaces"] == imported["interfaces"]
    assert preview["manual"] == lab_definition["manual"]
    assert "id" not in preview["topology"]
    assert "status" not in preview["topology"]


def test_preview_lab_without_resource_requirements(
    client: TestClient, lab_definition: dict
) -> None:
    for node in lab_definition["nodes"]:
        node.pop("resources")
    imported = client.post("/labs/import", json=lab_definition).json()["lab"]

    preview_response = client.get(f"/labs/{imported['id']}/preview")

    assert preview_response.status_code == 200
    assert preview_response.json()["estimated_resources"] == {
        "total_cpu": None,
        "total_memory_mb": None,
        "exposed_ports": [],
        "port_mappings": [],
    }


def test_preview_missing_lab_returns_404(client: TestClient) -> None:
    response = client.get("/labs/not-a-real-id/preview")

    assert response.status_code == 404


def test_start_lab_invokes_runtime_and_sets_running(
    client: TestClient, lab_definition: dict
) -> None:
    runtime = RecordingRuntime()
    service.runtime = runtime
    created = client.post("/labs", json=lab_definition).json()

    response = client.post(f"/labs/{created['id']}/start")

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["errors"] == []
    assert body["lab"]["id"] == created["id"]
    assert body["lab"]["status"] == "running"
    assert len(runtime.started_labs) == 1
    assert runtime.started_labs[0].status == "starting"
    assert [network.id for network in runtime.started_labs[0].networks] == ["left", "right"]
    assert [node.id for node in runtime.started_labs[0].nodes] == ["host-a", "router", "host-b"]


def test_start_running_lab_is_idempotent(client: TestClient, lab_definition: dict) -> None:
    runtime = RecordingRuntime()
    service.runtime = runtime
    created = client.post("/labs", json=lab_definition).json()
    first_response = client.post(f"/labs/{created['id']}/start")

    second_response = client.post(f"/labs/{created['id']}/start")

    assert first_response.status_code == 200
    assert second_response.status_code == 200
    assert second_response.json()["success"] is True
    assert second_response.json()["lab"]["status"] == "running"
    assert len(runtime.started_labs) == 1


def test_start_lab_returns_structured_runtime_error(
    client: TestClient, lab_definition: dict
) -> None:
    service.runtime = FailingRuntime()
    created = client.post("/labs", json=lab_definition).json()

    response = client.post(f"/labs/{created['id']}/start")

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is False
    assert body["lab"]["status"] == "error"
    assert body["errors"] == [{"message": "Docker is unavailable", "command": ["docker", "ps"]}]


def test_start_missing_lab_returns_404(client: TestClient) -> None:
    response = client.post("/labs/not-a-real-id/start")

    assert response.status_code == 404


def test_stop_lab_invokes_runtime_and_sets_stopped(
    client: TestClient, lab_definition: dict
) -> None:
    runtime = RecordingRuntime()
    service.runtime = runtime
    created = client.post("/labs", json=lab_definition).json()
    client.post(f"/labs/{created['id']}/start")

    response = client.post(f"/labs/{created['id']}/stop")

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["errors"] == []
    assert body["lab"]["status"] == "stopped"
    assert len(runtime.stopped_labs) == 1
    assert runtime.stopped_labs[0].status == "stopping"


def test_stop_stopped_lab_is_idempotent(client: TestClient, lab_definition: dict) -> None:
    runtime = RecordingRuntime()
    service.runtime = runtime
    created = client.post("/labs", json=lab_definition).json()
    client.post(f"/labs/{created['id']}/stop")

    response = client.post(f"/labs/{created['id']}/stop")

    assert response.status_code == 200
    assert response.json()["success"] is True
    assert response.json()["lab"]["status"] == "stopped"
    assert len(runtime.stopped_labs) == 1


def test_stop_lab_returns_structured_runtime_error(
    client: TestClient, lab_definition: dict
) -> None:
    service.runtime = FailingRuntime()
    created = client.post("/labs", json=lab_definition).json()

    response = client.post(f"/labs/{created['id']}/stop")

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is False
    assert body["lab"]["status"] == "error"
    assert body["errors"] == [
        {"message": "Container could not stop", "command": ["docker", "stop", "container"]}
    ]


def test_stop_missing_lab_returns_404(client: TestClient) -> None:
    response = client.post("/labs/not-a-real-id/stop")

    assert response.status_code == 404


def test_reset_lab_removes_runtime_resources_and_preserves_spec(
    client: TestClient, lab_definition: dict
) -> None:
    runtime = RecordingRuntime()
    service.runtime = runtime
    created = client.post("/labs", json=lab_definition).json()
    client.post(f"/labs/{created['id']}/start")

    response = client.post(f"/labs/{created['id']}/reset")

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["lab"]["status"] == "defined"
    assert body["lab"]["manual"] == lab_definition["manual"]
    assert body["lab"]["nodes"] == created["nodes"]
    assert len(runtime.reset_labs) == 1


def test_reset_lab_returns_structured_runtime_error(
    client: TestClient, lab_definition: dict
) -> None:
    service.runtime = FailingRuntime()
    created = client.post("/labs", json=lab_definition).json()

    response = client.post(f"/labs/{created['id']}/reset")

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is False
    assert body["lab"]["status"] == "error"
    assert body["errors"] == [
        {"message": "Resource cleanup failed", "command": ["docker", "rm", "-f", "container"]}
    ]


def test_reset_missing_lab_returns_404(client: TestClient) -> None:
    response = client.post("/labs/not-a-real-id/reset")

    assert response.status_code == 404


def test_lab_runtime_status_reports_resources(
    client: TestClient, lab_definition: dict
) -> None:
    runtime = RecordingRuntime()
    service.runtime = runtime
    created = client.post("/labs", json=lab_definition).json()
    client.post(f"/labs/{created['id']}/start")

    response = client.get(f"/labs/{created['id']}/status")

    assert response.status_code == 200
    body = response.json()
    assert body["lab"]["id"] == created["id"]
    assert body["lab"]["status"] == "running"
    assert body["errors"] == []
    assert body["resources"] == [
        {
            "kind": "network",
            "id": "left",
            "name": "practicum-test-left",
            "exists": True,
            "status": "present",
            "error": None,
            "note": None,
        },
        {
            "kind": "container",
            "id": "host-a",
            "name": "practicum-test-host-a",
            "exists": True,
            "status": "running",
            "error": None,
            "note": None,
        },
    ]


def test_lab_runtime_status_reports_runtime_error(
    client: TestClient, lab_definition: dict
) -> None:
    service.runtime = FailingRuntime()
    created = client.post("/labs", json=lab_definition).json()

    response = client.get(f"/labs/{created['id']}/status")

    assert response.status_code == 200
    body = response.json()
    assert body["lab"]["id"] == created["id"]
    assert body["resources"] == []
    assert body["errors"] == [{"message": "Docker is unavailable", "command": ["docker", "inspect"]}]


def test_lab_runtime_status_missing_lab_returns_404(client: TestClient) -> None:
    response = client.get("/labs/not-a-real-id/status")

    assert response.status_code == 404


def test_import_valid_lab_adds_it_to_local_list(
    client: TestClient, lab_definition: dict
) -> None:
    import_response = client.post("/labs/import", json=lab_definition)

    assert import_response.status_code == 200
    body = import_response.json()
    assert body["imported"] is True
    assert body["errors"] == []
    assert body["lab"]["id"]
    assert body["lab"]["status"] == "defined"

    list_response = client.get("/labs")

    assert list_response.status_code == 200
    assert [lab["id"] for lab in list_response.json()] == [body["lab"]["id"]]


def test_import_invalid_lab_returns_errors_without_storing(
    client: TestClient, lab_definition: dict
) -> None:
    lab_definition["interfaces"][0]["address"] = "192.168.1.10/24"

    import_response = client.post("/labs/import", json=lab_definition)

    assert import_response.status_code == 200
    body = import_response.json()
    assert body["imported"] is False
    assert body["lab"] is None
    assert "outside network" in body["errors"][0]["message"]
    assert client.get("/labs").json() == []


def test_exported_lab_can_be_imported(client: TestClient, lab_definition: dict) -> None:
    created = client.post("/labs", json=lab_definition).json()
    exported = client.get(f"/labs/{created['id']}/export").json()
    service_size_before_import = len(client.get("/labs").json())

    import_response = client.post("/labs/import", json=exported)

    assert import_response.status_code == 200
    body = import_response.json()
    assert body["imported"] is True
    assert body["lab"]["id"] != created["id"]
    assert len(client.get("/labs").json()) == service_size_before_import + 1


def test_validate_lab_accepts_node_without_resources(
    client: TestClient, lab_definition: dict
) -> None:
    lab_definition["nodes"][0].pop("resources")

    response = client.post("/labs/validate", json=lab_definition)

    assert response.status_code == 200
    assert response.json()["lab"]["nodes"][0]["resources"] is None


def test_validate_lab_accepts_docker_resource_requirements(
    client: TestClient, lab_definition: dict
) -> None:
    lab_definition["nodes"][0]["resources"] = {
        "cpu": 2,
        "memory_mb": 512,
        "shm_size_mb": 1024,
        "exposed_ports": [80, 443],
        "port_mappings": [{"host": 8080, "container": 3000}],
    }
    lab_definition["nodes"][0]["command"] = None
    lab_definition["nodes"][0]["environment"] = {"TITLE": "Practicum"}

    response = client.post("/labs/validate", json=lab_definition)

    assert response.status_code == 200
    node = response.json()["lab"]["nodes"][0]
    assert node["command"] is None
    assert node["environment"] == {"TITLE": "Practicum"}
    resources = response.json()["lab"]["nodes"][0]["resources"]
    assert resources == {
        "cpu": 2.0,
        "memory_mb": 512,
        "shm_size_mb": 1024,
        "exposed_ports": [80, 443],
        "port_mappings": [{"host": 8080, "container": 3000, "protocol": "tcp"}],
        "sysctls": {},
    }


def test_validate_lab_rejects_invalid_environment_name(
    client: TestClient, lab_definition: dict
) -> None:
    lab_definition["nodes"][0]["environment"] = {"1INVALID": "value"}

    response = client.post("/labs/validate", json=lab_definition)

    assert response.status_code == 200
    body = response.json()
    assert body["valid"] is False
    assert body["errors"][0]["location"] == ["nodes", "0", "environment", "1INVALID", "[key]"]


def test_validate_lab_rejects_overlapping_port_mapping(
    client: TestClient, lab_definition: dict
) -> None:
    lab_definition["nodes"][0]["resources"] = {
        "exposed_ports": [3000],
        "port_mappings": [{"host": 3000, "container": 3000}],
    }

    response = client.post("/labs/validate", json=lab_definition)

    assert response.status_code == 200
    body = response.json()
    assert body["valid"] is False
    assert "exposed ports cannot overlap port mappings" in body["errors"][0]["message"]


def test_validate_lab_accepts_manual_sections(client: TestClient, lab_definition: dict) -> None:
    response = client.post("/labs/validate", json=lab_definition)

    assert response.status_code == 200
    manual = response.json()["lab"]["manual"]
    assert manual["sections"][0]["id"] == "overview"
    assert manual["sections"][0]["title"] == "Overview"
    assert "## Goal" in manual["sections"][0]["content_markdown"]
    assert manual["sections"][0]["tasks"][0]["id"] == "verify-topology"


def test_rejects_duplicate_manual_section_ids(
    client: TestClient, lab_definition: dict
) -> None:
    lab_definition["manual"]["sections"][1]["id"] = "overview"

    response = client.post("/labs/validate", json=lab_definition)

    assert response.status_code == 200
    body = response.json()
    assert body["valid"] is False
    assert body["lab"] is None
    assert "manual section ids must be unique" in body["errors"][0]["message"]


def test_rejects_duplicate_manual_task_ids(client: TestClient, lab_definition: dict) -> None:
    lab_definition["manual"]["sections"][0]["tasks"].append(
        {"id": "verify-topology", "text": "Duplicate task id"}
    )

    response = client.post("/labs/validate", json=lab_definition)

    assert response.status_code == 200
    body = response.json()
    assert body["valid"] is False
    assert "manual task ids must be unique within a section" in body["errors"][0]["message"]


def test_rejects_empty_manual_section_content(
    client: TestClient, lab_definition: dict
) -> None:
    lab_definition["manual"]["sections"][0]["content_markdown"] = ""

    response = client.post("/labs/validate", json=lab_definition)

    assert response.status_code == 200
    body = response.json()
    assert body["valid"] is False
    assert body["errors"][0]["location"] == ["manual", "sections", "0", "content_markdown"]


def test_rejects_invalid_cpu_limit(client: TestClient, lab_definition: dict) -> None:
    lab_definition["nodes"][0]["resources"]["cpu"] = 0

    response = client.post("/labs/validate", json=lab_definition)

    assert response.status_code == 200
    body = response.json()
    assert body["valid"] is False
    assert body["errors"][0]["location"] == ["nodes", "0", "resources", "cpu"]


def test_rejects_invalid_memory_limit(client: TestClient, lab_definition: dict) -> None:
    lab_definition["nodes"][0]["resources"]["memory_mb"] = 0

    response = client.post("/labs/validate", json=lab_definition)

    assert response.status_code == 200
    body = response.json()
    assert body["valid"] is False
    assert body["errors"][0]["location"] == ["nodes", "0", "resources", "memory_mb"]


def test_rejects_invalid_exposed_port(client: TestClient, lab_definition: dict) -> None:
    lab_definition["nodes"][0]["resources"]["exposed_ports"] = [0]

    response = client.post("/labs/validate", json=lab_definition)

    assert response.status_code == 200
    body = response.json()
    assert body["valid"] is False
    assert body["errors"][0]["location"] == ["nodes", "0", "resources", "exposed_ports", "0"]


def test_rejects_duplicate_exposed_ports(client: TestClient, lab_definition: dict) -> None:
    lab_definition["nodes"][0]["resources"]["exposed_ports"] = [80, 80]

    response = client.post("/labs/validate", json=lab_definition)

    assert response.status_code == 200
    body = response.json()
    assert body["valid"] is False
    assert "exposed ports must be unique" in body["errors"][0]["message"]


def test_rejects_invalid_schema_version(client: TestClient, lab_definition: dict) -> None:
    lab_definition["schema_version"] = "one"

    response = client.post("/labs/validate", json=lab_definition)

    assert response.status_code == 200
    body = response.json()
    assert body["valid"] is False
    assert body["errors"][0]["location"] == ["schema_version"]


def test_import_rejects_unsupported_schema_version(
    client: TestClient, lab_definition: dict
) -> None:
    lab_definition["schema_version"] = "2.0"

    response = client.post("/labs/import", json=lab_definition)

    assert response.status_code == 200
    body = response.json()
    assert body["imported"] is False
    assert body["lab"] is None
    assert body["errors"][0]["location"] == ["schema_version"]
    assert "not supported by this version of Practicum" in body["errors"][0]["message"]
    assert client.get("/labs").json() == []


def test_rejects_interface_outside_network(client: TestClient, lab_definition: dict) -> None:
    lab_definition["interfaces"][0]["address"] = "192.168.1.10/24"

    response = client.post("/labs/validate", json=lab_definition)

    assert response.status_code == 200
    body = response.json()
    assert body["valid"] is False
    assert "outside network" in body["errors"][0]["message"]


def test_create_lab_still_rejects_invalid_definition(
    client: TestClient, lab_definition: dict
) -> None:
    lab_definition["interfaces"][0]["address"] = "192.168.1.10/24"

    response = client.post("/labs", json=lab_definition)

    assert response.status_code == 422


def test_missing_lab_returns_404(client: TestClient) -> None:
    response = client.get("/labs/not-a-real-id")

    assert response.status_code == 404


def test_get_lab_ports_missing_lab_returns_404(client: TestClient) -> None:
    response = client.get("/labs/not-a-real-id/ports")

    assert response.status_code == 404


def test_get_lab_ports_reports_no_conflicts_when_everything_is_free(
    monkeypatch, client: TestClient, lab_definition: dict
) -> None:
    monkeypatch.setattr(ports, "is_local_port_free", lambda port, protocol="tcp": True)
    created = client.post("/labs", json=lab_definition).json()

    response = client.get(f"/labs/{created['id']}/ports")

    assert response.status_code == 200
    body = response.json()
    assert body["lab_id"] == created["id"]
    assert body["has_conflicts"] is False
    assert body["conflicts"] == []


def test_get_lab_ports_reports_conflict_with_recommendation(
    monkeypatch, client: TestClient, lab_definition: dict
) -> None:
    monkeypatch.setattr(ports, "is_local_port_free", lambda port, protocol="tcp": port != 2222)
    created = client.post("/labs", json=lab_definition).json()

    response = client.get(f"/labs/{created['id']}/ports")

    assert response.status_code == 200
    body = response.json()
    assert body["has_conflicts"] is True
    conflict = body["conflicts"][0]
    assert conflict["node_id"] == "router"
    assert conflict["host_port"] == 2222
    assert conflict["reason"] == "in_use_on_host"
    assert conflict["recommended_port"] is not None


def test_apply_port_recommendation_updates_mapping_and_rechecks(
    monkeypatch, client: TestClient, lab_definition: dict
) -> None:
    monkeypatch.setattr(ports, "is_local_port_free", lambda port, protocol="tcp": port != 2222)
    created = client.post("/labs", json=lab_definition).json()

    response = client.post(
        f"/labs/{created['id']}/ports/apply-recommendation",
        json={"node_id": "router", "host_port": 2222, "protocol": "tcp"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["has_conflicts"] is False
    assert body["conflicts"] == []

    updated = client.get(f"/labs/{created['id']}").json()
    router = next(node for node in updated["nodes"] if node["id"] == "router")
    mapping_hosts = [mapping["host"] for mapping in router["resources"]["port_mappings"]]
    assert 2222 not in mapping_hosts


def test_apply_port_recommendation_missing_lab_returns_404(client: TestClient) -> None:
    response = client.post(
        "/labs/not-a-real-id/ports/apply-recommendation",
        json={"node_id": "router", "host_port": 2222, "protocol": "tcp"},
    )

    assert response.status_code == 404


def test_apply_port_recommendation_without_conflict_returns_409(
    monkeypatch, client: TestClient, lab_definition: dict
) -> None:
    monkeypatch.setattr(ports, "is_local_port_free", lambda port, protocol="tcp": True)
    created = client.post("/labs", json=lab_definition).json()

    response = client.post(
        f"/labs/{created['id']}/ports/apply-recommendation",
        json={"node_id": "router", "host_port": 2222, "protocol": "tcp"},
    )

    assert response.status_code == 409


def test_apply_a_chosen_port_instead_of_the_recommendation(
    monkeypatch, client: TestClient, lab_definition: dict
) -> None:
    monkeypatch.setattr(ports, "is_local_port_free", lambda port, protocol="tcp": port != 2222)
    created = client.post("/labs", json=lab_definition).json()

    response = client.post(
        f"/labs/{created['id']}/ports/apply-recommendation",
        json={"node_id": "router", "host_port": 2222, "protocol": "tcp", "new_host_port": 9022},
    )

    assert response.status_code == 200
    assert response.json()["has_conflicts"] is False
    nodes = client.get(f"/labs/{created['id']}").json()["nodes"]
    router = next(n for n in nodes if n["id"] == "router")
    mappings = router["resources"]["port_mappings"]
    assert {"host": 9022, "container": 22, "protocol": "tcp"} in mappings
    assert 2222 not in [m["host"] for m in router["resources"]["port_mappings"]]


def test_a_chosen_port_is_refused_with_the_reason(
    monkeypatch, client: TestClient, lab_definition: dict
) -> None:
    monkeypatch.setattr(
        ports, "is_local_port_free", lambda port, protocol="tcp": port not in (2222, 5000)
    )
    created = client.post("/labs", json=lab_definition).json()
    url = f"/labs/{created['id']}/ports/apply-recommendation"
    base = {"node_id": "router", "host_port": 2222, "protocol": "tcp"}

    taken_on_host = client.post(url, json={**base, "new_host_port": 5000})
    assert taken_on_host.status_code == 409
    assert "5000/tcp is already in use on this machine" in taken_on_host.json()["detail"]

    api_port = client.post(url, json={**base, "new_host_port": 8000})
    assert api_port.status_code == 409
    assert "reserved by the Practicum API" in api_port.json()["detail"]

    in_lab = client.post(url, json={**base, "new_host_port": 22})  # router's own exposed 22
    assert in_lab.status_code == 409
    assert "already used by node 'router' in this lab" in in_lab.json()["detail"]

    same = client.post(url, json={**base, "new_host_port": 2222})
    assert same.status_code == 409

    out_of_range = client.post(url, json={**base, "new_host_port": 70000})
    assert out_of_range.status_code == 422

    # nothing changed: the conflict is still there, on the original port
    check = client.get(f"/labs/{created['id']}/ports").json()
    assert [c["host_port"] for c in check["conflicts"]] == [2222]


def test_port_fix_on_a_stopped_lab_recreates_its_machines(
    monkeypatch, client: TestClient, lab_definition: dict
) -> None:
    """A stopped lab keeps its containers for `docker start`; moving a port must not bring
    them back with the old mapping and the old session data (D-48)."""
    monkeypatch.setattr(ports, "is_local_port_free", lambda port, protocol="tcp": port != 2222)
    runtime = RecordingRuntime()
    service.runtime = runtime
    created = client.post("/labs", json=lab_definition).json()
    lab_id = created["id"]
    # The lab must start for this test: make the start-time port re-check pass.
    monkeypatch.setattr(ports, "is_local_port_free", lambda port, protocol="tcp": True)
    assert client.post(f"/labs/{lab_id}/start").json()["lab"]["status"] == "running"
    assert client.post(f"/labs/{lab_id}/stop").json()["lab"]["status"] == "stopped"
    monkeypatch.setattr(ports, "is_local_port_free", lambda port, protocol="tcp": port != 2222)

    response = client.post(
        f"/labs/{lab_id}/ports/apply-recommendation",
        json={"node_id": "router", "host_port": 2222, "protocol": "tcp", "new_host_port": 9022},
    )

    assert response.status_code == 200
    assert response.json()["machines_reset"] is True
    assert [lab.id for lab in runtime.reset_labs] == [lab_id]
    lab = client.get(f"/labs/{lab_id}").json()
    assert lab["status"] == "defined"
    router = next(n for n in lab["nodes"] if n["id"] == "router")
    assert 9022 in [m["host"] for m in router["resources"]["port_mappings"]]

    # A never-started lab is rewritten without any Docker work.
    other = client.post("/labs", json=lab_definition).json()
    again = client.post(
        f"/labs/{other['id']}/ports/apply-recommendation",
        json={"node_id": "router", "host_port": 2222, "protocol": "tcp"},
    )
    assert again.json()["machines_reset"] is False
    assert len(runtime.reset_labs) == 1


# ----- lifecycle enablers: restart, delete, action lock, origin, progress -------------------


def test_restart_running_lab_stops_then_starts(client: TestClient, lab_definition: dict) -> None:
    runtime = RecordingRuntime()
    service.runtime = runtime
    created = client.post("/labs", json=lab_definition).json()
    client.post(f"/labs/{created['id']}/start")

    response = client.post(f"/labs/{created['id']}/restart")

    assert response.status_code == 200
    assert response.json()["success"] is True
    assert response.json()["lab"]["status"] == "running"
    assert len(runtime.stopped_labs) == 1
    assert len(runtime.started_labs) == 2


def test_restart_stopped_lab_just_starts_it(client: TestClient, lab_definition: dict) -> None:
    runtime = RecordingRuntime()
    service.runtime = runtime
    created = client.post("/labs", json=lab_definition).json()

    response = client.post(f"/labs/{created['id']}/restart")

    assert response.status_code == 200
    assert response.json()["lab"]["status"] == "running"
    assert runtime.stopped_labs == []
    assert len(runtime.started_labs) == 1


def test_restart_missing_lab_returns_404(client: TestClient) -> None:
    assert client.post("/labs/not-a-real-id/restart").status_code == 404


def test_lifecycle_calls_are_rejected_while_lab_is_busy(
    client: TestClient, lab_definition: dict
) -> None:
    service.runtime = RecordingRuntime()
    created = client.post("/labs", json=lab_definition).json()
    service.get(created["id"]).status = "starting"  # as if another request were mid-flight

    for action in ("start", "stop", "restart", "reset"):
        response = client.post(f"/labs/{created['id']}/{action}")
        assert response.status_code == 409, action
        assert "already starting" in response.json()["detail"]
    assert client.delete(f"/labs/{created['id']}").status_code == 409


def test_start_is_blocked_by_a_host_port_conflict_detected_at_start_time(
    client: TestClient, lab_definition: dict, monkeypatch
) -> None:
    runtime = RecordingRuntime()
    service.runtime = runtime
    created = client.post("/labs", json=lab_definition).json()
    monkeypatch.setattr(ports, "is_local_port_free", lambda port, protocol="tcp": port != 2222)

    response = client.post(f"/labs/{created['id']}/start")

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is False
    assert body["lab"]["status"] == "error"
    assert body["errors"][0]["message"].startswith(
        "host port conflict: router 2222/tcp: already in use on this machine"
    )
    assert body["lab"]["last_error"].startswith("router 2222/tcp")
    assert runtime.started_labs == []  # Docker was never asked


def test_delete_lab_removes_it_and_its_runtime_resources(
    client: TestClient, lab_definition: dict
) -> None:
    runtime = RecordingRuntime()
    service.runtime = runtime
    created = client.post("/labs", json=lab_definition).json()
    client.post(f"/labs/{created['id']}/start")

    response = client.delete(f"/labs/{created['id']}")

    assert response.status_code == 204
    assert client.get(f"/labs/{created['id']}").status_code == 404
    assert client.get("/labs").json() == []
    assert len(runtime.reset_labs) == 1


def test_delete_never_started_lab_succeeds_even_when_docker_is_down(
    client: TestClient, lab_definition: dict
) -> None:
    service.runtime = FailingRuntime()  # reset raises; nothing to clean anyway
    created = client.post("/labs", json=lab_definition).json()

    response = client.delete(f"/labs/{created['id']}")

    assert response.status_code == 204
    assert client.get("/labs").json() == []


def test_delete_always_sweeps_the_labs_docker_names(
    client: TestClient, lab_definition: dict
) -> None:
    """Even a lab the API believes never started gets `docker rm -f` / `network rm` for its
    names, so a container can never outlive its lab card."""
    runtime = RecordingRuntime()
    service.runtime = runtime
    created = client.post("/labs", json=lab_definition).json()

    assert client.delete(f"/labs/{created['id']}").status_code == 204
    assert len(runtime.reset_labs) == 1


# ----- leftover sweep -------------------------------------------------------------------------


def test_sweep_removes_resources_of_unknown_labs_only(
    client: TestClient, lab_definition: dict
) -> None:
    runtime = RecordingRuntime()
    service.runtime = runtime
    kept = client.post("/labs", json=lab_definition).json()
    runtime.containers = [
        PracticumContainerInfo(name=f"practicum-{kept['id'][:8]}-host-a", lab_id=kept["id"]),
        PracticumContainerInfo(name="practicum-deadbeef-ubuntu", lab_id="dead-beef", status="running"),
        PracticumContainerInfo(name="practicum-cafebabe-router", lab_id="cafe-babe", status="exited"),
    ]
    runtime.networks = [
        DockerNetworkInfo(name=f"practicum-{kept['id'][:8]}-left", lab_id=kept["id"]),
        DockerNetworkInfo(name="practicum-deadbeef-lab-net", lab_id="dead-beef"),
        DockerNetworkInfo(name="bridge"),  # not Practicum's: never touched
    ]

    response = client.post("/docker/sweep-leftovers")

    assert response.status_code == 200
    body = response.json()
    assert sorted(body["removed_containers"]) == [
        "practicum-cafebabe-router",
        "practicum-deadbeef-ubuntu",
    ]
    assert body["removed_networks"] == ["practicum-deadbeef-lab-net"]
    assert body["errors"] == [] and body["error"] is None
    assert runtime.removed_containers == ["practicum-deadbeef-ubuntu", "practicum-cafebabe-router"]


def test_sweep_reports_docker_unavailable_instead_of_failing(client: TestClient) -> None:
    service.runtime = FailingRuntime()

    response = client.post("/docker/sweep-leftovers")

    assert response.status_code == 200
    assert response.json()["error"] == "Docker is unavailable"


def test_api_startup_sweeps_leftovers(lab_definition: dict) -> None:
    runtime = RecordingRuntime()
    service.runtime = runtime
    runtime.containers = [PracticumContainerInfo(name="practicum-old-ubuntu", lab_id="old")]

    with TestClient(app) as started_client:  # the context manager runs the lifespan
        assert started_client.get("/health").status_code == 200

    assert runtime.removed_containers == ["practicum-old-ubuntu"]


def test_delete_keeps_lab_when_its_resources_cannot_be_removed(
    client: TestClient, lab_definition: dict
) -> None:
    service.runtime = RecordingRuntime()
    created = client.post("/labs", json=lab_definition).json()
    client.post(f"/labs/{created['id']}/start")
    service.runtime = FailingRuntime()

    response = client.delete(f"/labs/{created['id']}")

    assert response.status_code == 409
    assert "Resource cleanup failed" in response.json()["detail"]
    assert client.get(f"/labs/{created['id']}").status_code == 200


def test_delete_missing_lab_returns_404(client: TestClient) -> None:
    assert client.delete("/labs/not-a-real-id").status_code == 404


def test_created_lab_records_origin_and_creation_time(
    client: TestClient, lab_definition: dict
) -> None:
    designed = client.post("/labs", json=lab_definition).json()
    quick = client.post("/labs", params={"origin": "quick_start"}, json=lab_definition).json()
    imported = client.post(
        "/labs/import", params={"source_file": "static-routing.json"}, json=lab_definition
    ).json()["lab"]

    assert designed["origin"] == "designer"
    assert designed["source_file"] is None
    assert designed["created_at"] is not None
    assert designed["last_started_at"] is None
    assert quick["origin"] == "quick_start"
    assert imported["origin"] == "imported"
    assert imported["source_file"] == "static-routing.json"
    assert client.post("/labs", params={"origin": "bogus"}, json=lab_definition).status_code == 422


def test_successful_start_records_last_started_at_and_clears_last_error(
    client: TestClient, lab_definition: dict
) -> None:
    service.runtime = FailingRuntime()
    created = client.post("/labs", json=lab_definition).json()
    failed = client.post(f"/labs/{created['id']}/start").json()["lab"]
    assert failed["last_error"] == "Docker is unavailable"
    assert failed["last_started_at"] is None

    service.runtime = RecordingRuntime()
    started = client.post(f"/labs/{created['id']}/start").json()["lab"]

    assert started["last_error"] is None
    assert started["last_started_at"] is not None
    listed = client.get("/labs").json()[0]
    assert listed["last_started_at"] == started["last_started_at"]


def test_port_recommendation_keeps_origin_and_timestamps(
    client: TestClient, lab_definition: dict, monkeypatch
) -> None:
    monkeypatch.setattr(ports, "is_local_port_free", lambda port, protocol="tcp": port != 2222)
    created = client.post(
        "/labs/import", params={"source_file": "a.json"}, json=lab_definition
    ).json()["lab"]

    client.post(
        f"/labs/{created['id']}/ports/apply-recommendation",
        json={"node_id": "router", "host_port": 2222, "protocol": "tcp"},
    )

    updated = client.get(f"/labs/{created['id']}").json()
    assert updated["origin"] == "imported"
    assert updated["source_file"] == "a.json"
    assert updated["created_at"] == created["created_at"]


def test_status_reports_per_node_start_progress(client: TestClient, lab_definition: dict) -> None:
    service.runtime = RecordingRuntime()
    created = client.post("/labs", json=lab_definition).json()
    assert client.get(f"/labs/{created['id']}/status").json()["progress"] == []

    client.post(f"/labs/{created['id']}/start")

    progress = client.get(f"/labs/{created['id']}/status").json()["progress"]
    assert [(p["node_id"], p["step"]) for p in progress] == [
        ("host-a", "ready"),
        ("router", "ready"),
        ("host-b", "ready"),
    ]
    assert progress[0]["image"] == "alpine:3.21"


def test_async_start_returns_202_and_completes_in_background(
    client: TestClient, lab_definition: dict
) -> None:
    runtime = RecordingRuntime()
    service.runtime = runtime
    created = client.post("/labs", json=lab_definition).json()

    response = client.post(f"/labs/{created['id']}/start", params={"wait": "false"})

    assert response.status_code == 202
    assert response.json()["success"] is True
    assert response.json()["pending"] is True
    thread = service._background_starts.get(created["id"])
    if thread is not None:
        thread.join(timeout=5)
    final = client.get(f"/labs/{created['id']}/status").json()
    assert final["lab"]["status"] == "running"
    assert all(p["step"] == "ready" for p in final["progress"])
    assert len(runtime.started_labs) == 1


def test_async_start_failure_is_visible_in_status(
    client: TestClient, lab_definition: dict
) -> None:
    service.runtime = FailingRuntime()
    created = client.post("/labs", json=lab_definition).json()

    response = client.post(f"/labs/{created['id']}/start", params={"wait": "false"})

    assert response.status_code == 202
    thread = service._background_starts.get(created["id"])
    if thread is not None:
        thread.join(timeout=5)
    final = client.get(f"/labs/{created['id']}/status").json()
    assert final["lab"]["status"] == "error"
    assert final["lab"]["last_error"] == "Docker is unavailable"


# ----- edit an existing lab (PUT) ------------------------------------------------------------


def test_put_replaces_definition_and_keeps_identity(client: TestClient, lab_definition: dict) -> None:
    created = client.post(
        "/labs/import", params={"source_file": "routing.json"}, json=lab_definition
    ).json()["lab"]
    lab_definition["name"] = "Static Routing v2"
    lab_definition["nodes"][0]["image"] = "ubuntu:22.04"

    response = client.put(f"/labs/{created['id']}", json=lab_definition)

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == created["id"]
    assert body["name"] == "Static Routing v2"
    assert body["nodes"][0]["image"] == "ubuntu:22.04"
    assert body["origin"] == "imported"
    assert body["source_file"] == "routing.json"
    assert body["created_at"] == created["created_at"]
    assert body["status"] == "defined"
    assert client.get(f"/labs/{created['id']}").json()["name"] == "Static Routing v2"


def test_put_validates_like_create(client: TestClient, lab_definition: dict) -> None:
    created = client.post("/labs", json=lab_definition).json()
    lab_definition["interfaces"][0]["address"] = "10.9.9.9/24"  # outside its network

    response = client.put(f"/labs/{created['id']}", json=lab_definition)

    assert response.status_code == 422
    assert client.get(f"/labs/{created['id']}").json()["name"] == created["name"]


def test_put_refuses_a_running_lab(client: TestClient, lab_definition: dict) -> None:
    service.runtime = RecordingRuntime()
    created = client.post("/labs", json=lab_definition).json()
    client.post(f"/labs/{created['id']}/start")

    response = client.put(f"/labs/{created['id']}", json=lab_definition)

    assert response.status_code == 409
    assert "stop it before editing" in response.json()["detail"]


def test_put_on_a_stopped_lab_resets_its_resources_first(
    client: TestClient, lab_definition: dict
) -> None:
    runtime = RecordingRuntime()
    service.runtime = runtime
    created = client.post("/labs", json=lab_definition).json()
    client.post(f"/labs/{created['id']}/start")
    client.post(f"/labs/{created['id']}/stop")

    response = client.put(f"/labs/{created['id']}", json=lab_definition)

    assert response.status_code == 200
    assert response.json()["status"] == "defined"
    assert len(runtime.reset_labs) == 1


def test_put_missing_lab_returns_404(client: TestClient, lab_definition: dict) -> None:
    assert client.put("/labs/not-a-real-id", json=lab_definition).status_code == 404


# ----- docker engine mode (windows quick start, phase 8) --------------------------------------


def test_docker_engine_reports_what_the_daemon_serves(client: TestClient) -> None:
    runtime = RecordingRuntime()
    runtime.engine = DockerEngineInfo(
        available=True,
        os_type="windows",
        server_version="27.3.1",
        operating_system="Windows 11 Pro",
        host_build=22631,
        isolation="hyperv",
        detail="Docker 27.3.1 is serving Windows containers.",
    )
    service.runtime = runtime

    response = client.get("/docker/engine")

    assert response.status_code == 200
    body = response.json()
    assert body["available"] is True
    assert body["os_type"] == "windows"
    assert body["host_build"] == 22631
    assert body["isolation"] == "hyperv"


def test_docker_engine_reports_an_unreachable_daemon_without_failing(client: TestClient) -> None:
    service.runtime = FailingRuntime()

    response = client.get("/docker/engine")

    assert response.status_code == 200
    assert response.json() == {
        "available": False,
        "os_type": None,
        "server_version": None,
        "operating_system": None,
        "kernel_version": None,
        "host_build": None,
        "isolation": None,
        "detail": "Docker is unavailable",
    }


def _windows_definition() -> dict:
    return {
        "name": "Windows Quick Start",
        "nodes": [
            {
                "id": "host",
                "image": "mcr.microsoft.com/windows/servercore:ltsc2022",
                "os": "windows",
                "shell": "powershell",
                "command": ["powershell", "-NoLogo", "-Command", "Start-Sleep 3600"],
                "resources": {"cpu": 2, "memory_mb": 2048},
            }
        ],
        "networks": [{"id": "lab-net", "subnet": "10.90.0.0/24"}],
        "interfaces": [{"node": "host", "network": "lab-net", "address": "10.90.0.10/24"}],
    }


def test_windows_lab_os_and_shell_survive_export_and_import(client: TestClient) -> None:
    created = client.post("/labs", json=_windows_definition(), params={"origin": "quick_start"})
    assert created.status_code == 201
    lab_id = created.json()["id"]

    exported = client.get(f"/labs/{lab_id}/export").json()
    assert exported["nodes"][0]["os"] == "windows"
    assert exported["nodes"][0]["shell"] == "powershell"

    imported = client.post("/labs/import", json=exported).json()
    assert imported["imported"] is True
    assert imported["lab"]["nodes"][0]["os"] == "windows"
    assert imported["lab"]["nodes"][0]["shell"] == "powershell"

    preview = client.get(f"/labs/{lab_id}/preview").json()
    assert preview["container_os"] == "windows"
    assert preview["topology"]["nodes"][0]["shell"] == "powershell"


def test_preview_of_a_linux_lab_says_linux(client: TestClient, lab_definition: dict) -> None:
    created = client.post("/labs", json=lab_definition).json()

    preview = client.get(f"/labs/{created['id']}/preview").json()

    assert preview["container_os"] == "linux"
    assert preview["topology"]["nodes"][0]["os"] == "linux"
    assert preview["topology"]["nodes"][0]["shell"] is None


def test_validate_rejects_mixed_operating_systems(client: TestClient, lab_definition: dict) -> None:
    lab_definition["nodes"][0]["os"] = "windows"

    response = client.post("/labs/validate", json=lab_definition)

    body = response.json()
    assert body["valid"] is False
    assert any("same operating system" in error["message"] for error in body["errors"])


def test_start_failure_from_engine_mode_is_a_structured_runtime_error(
    client: TestClient,
) -> None:
    class WrongModeRuntime(RecordingRuntime):
        def start(self, lab: Lab, on_progress=None) -> None:
            raise RuntimeFailure(
                "This lab needs Windows containers, but Docker Desktop is currently serving "
                "Linux containers.",
                ["docker", "info"],
            )

    service.runtime = WrongModeRuntime()
    created = client.post("/labs", json=_windows_definition()).json()

    response = client.post(f"/labs/{created['id']}/start")

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is False
    assert body["lab"]["status"] == "error"
    assert "needs Windows containers" in body["lab"]["last_error"]
    assert body["errors"][0]["command"] == ["docker", "info"]


def test_windows_quick_start_follows_the_existing_lifecycle_flows(client: TestClient) -> None:
    """designer-windows-quick-start: pre-start checks, async start with per-node progress,
    status, stop, restart, reset, export and delete are the same endpoints as for any lab."""
    runtime = RecordingRuntime()
    runtime.engine = DockerEngineInfo(
        available=True, os_type="windows", server_version="27.3.1", host_build=22631
    )
    service.runtime = runtime
    created = client.post(
        "/labs", json=_windows_definition(), params={"origin": "quick_start"}
    ).json()
    lab_id = created["id"]
    assert created["origin"] == "quick_start"
    assert created["nodes"][0]["os"] == "windows"

    # pre-start gate data: preview says windows, engine says windows, no conflicts
    assert client.get(f"/labs/{lab_id}/preview").json()["container_os"] == "windows"
    assert client.get("/docker/engine").json()["os_type"] == "windows"
    assert client.get(f"/labs/{lab_id}/ports").json()["has_conflicts"] is False

    # async start + progress, as the gate drives it
    response = client.post(f"/labs/{lab_id}/start", params={"wait": "false"})
    assert response.status_code == 202 and response.json()["pending"] is True
    thread = service._background_starts.get(lab_id)
    if thread is not None:
        thread.join(timeout=5)
    status = client.get(f"/labs/{lab_id}/status").json()
    assert status["lab"]["status"] == "running"
    assert [(p["node_id"], p["step"]) for p in status["progress"]] == [("host", "ready")]
    assert status["progress"][0]["image"] == "mcr.microsoft.com/windows/servercore:ltsc2022"
    started = runtime.started_labs[-1]
    assert started.nodes[0].command[0] == "powershell"  # the persistent PowerShell process

    assert client.post(f"/labs/{lab_id}/stop").json()["lab"]["status"] == "stopped"
    assert client.post(f"/labs/{lab_id}/restart").json()["lab"]["status"] == "running"
    assert client.post(f"/labs/{lab_id}/reset").json()["lab"]["status"] == "defined"
    exported = client.get(f"/labs/{lab_id}/export").json()
    assert exported["nodes"][0]["os"] == "windows" and "id" not in exported
    assert client.delete(f"/labs/{lab_id}").status_code == 204
    assert client.get("/labs").json() == []
    # stop once; restart of a stopped lab only starts; reset + delete both reset
    assert len(runtime.stopped_labs) == 1
    assert len(runtime.started_labs) == 2
    assert len(runtime.reset_labs) == 2


def test_engine_mode_change_after_creation_blocks_the_start(client: TestClient) -> None:
    """A Windows lab created while Docker served Windows containers; the engine is switched back
    before Start: the API reports the mismatch (what the gate shows) and Start fails with the
    same explanation instead of a raw Docker error."""
    runtime = RecordingRuntime()
    runtime.engine = DockerEngineInfo(available=True, os_type="windows", server_version="27.3.1")
    service.runtime = runtime
    lab_id = client.post("/labs", json=_windows_definition()).json()["id"]

    runtime.engine = DockerEngineInfo(available=True, os_type="linux", server_version="27.3.1")
    engine = client.get("/docker/engine").json()
    preview = client.get(f"/labs/{lab_id}/preview").json()
    assert engine["os_type"] == "linux" and preview["container_os"] == "windows"  # gate: mismatch

    class RealCheckRuntime(RecordingRuntime):
        def start(self, lab: Lab, on_progress=None) -> None:
            from practicum.runtime import DockerRuntime

            DockerRuntime._require_engine_os(self, lab)  # the real check, fake engine answer
            super().start(lab, on_progress)

    checked = RealCheckRuntime()
    checked.engine = runtime.engine
    service.runtime = checked
    result = client.post(f"/labs/{lab_id}/start").json()
    assert result["success"] is False
    assert result["lab"]["status"] == "error"
    assert "needs Windows containers" in result["lab"]["last_error"]
    assert "Switch to Windows containers" in result["lab"]["last_error"]
    assert checked.started_labs == []  # nothing was started
