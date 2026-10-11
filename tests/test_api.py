from fastapi.testclient import TestClient

from practicum import ports
from practicum.main import service
from practicum.models import Lab, RuntimeResourceStatus
from practicum.runtime import RuntimeFailure


class RecordingRuntime:
    def __init__(self) -> None:
        self.started_labs: list[Lab] = []
        self.stopped_labs: list[Lab] = []
        self.reset_labs: list[Lab] = []

    def start(self, lab: Lab) -> None:
        self.started_labs.append(lab.model_copy(deep=True))

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
    def start(self, lab: Lab) -> None:
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
    assert "id" not in exported
    assert "status" not in exported
    expected = {key: value for key, value in created.items() if key not in {"id", "status"}}
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
        },
        {
            "kind": "container",
            "id": "host-a",
            "name": "practicum-test-host-a",
            "exists": True,
            "status": "running",
            "error": None,
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
    monkeypatch.setattr(ports, "is_local_port_free", lambda port: True)
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
    monkeypatch.setattr(ports, "is_local_port_free", lambda port: port != 2222)
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
    monkeypatch.setattr(ports, "is_local_port_free", lambda port: port != 2222)
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
    monkeypatch.setattr(ports, "is_local_port_free", lambda port: True)
    created = client.post("/labs", json=lab_definition).json()

    response = client.post(
        f"/labs/{created['id']}/ports/apply-recommendation",
        json={"node_id": "router", "host_port": 2222, "protocol": "tcp"},
    )

    assert response.status_code == 409
