"""Service + API behaviour for subnet-conflict detection and resolution (Tigre/06 #13)."""

from ipaddress import IPv4Network

import pytest
from fastapi.testclient import TestClient

from practicum.main import service
from practicum.models import DockerNetworkInfo, Lab
from practicum.runtime import RuntimeFailure

LEFTOVER_LAB_ID = "deadbeef-0000-0000-0000-000000000000"


class FakeRuntime:
    """In-memory stand-in for DockerRuntime that answers list/remove network calls."""

    def __init__(self, networks: list[DockerNetworkInfo] | None = None) -> None:
        self.networks = networks or []
        self.removed: list[str] = []
        self.fail_listing: str | None = None

    def start(self, lab: Lab) -> None:
        pass

    def stop(self, lab: Lab) -> None:
        pass

    def reset(self, lab: Lab) -> None:
        pass

    def status(self, lab: Lab) -> list:
        return []

    def list_networks(self) -> list[DockerNetworkInfo]:
        if self.fail_listing:
            raise RuntimeFailure(self.fail_listing, ["docker", "network", "ls"])
        return list(self.networks)

    def remove_network(self, network: DockerNetworkInfo) -> None:
        self.removed.append(network.name)
        self.networks = [n for n in self.networks if n.name != network.name]


def _leftover() -> DockerNetworkInfo:
    return DockerNetworkInfo(
        name="practicum-deadbeef-left",
        subnets=[IPv4Network("10.0.1.0/24")],
        lab_id=LEFTOVER_LAB_ID,
        container_names=["practicum-deadbeef-host-a"],
    )


@pytest.fixture
def runtime() -> FakeRuntime:
    fake = FakeRuntime()
    service.runtime = fake
    return fake


def _create(client: TestClient, lab_definition: dict) -> str:
    return client.post("/labs", json=lab_definition).json()["id"]


def test_networks_reports_no_conflicts(client: TestClient, lab_definition: dict, runtime) -> None:
    runtime.networks = [DockerNetworkInfo(name="bridge", subnets=[IPv4Network("172.17.0.0/16")])]
    lab_id = _create(client, lab_definition)

    response = client.get(f"/labs/{lab_id}/networks")

    assert response.status_code == 200
    assert response.json() == {
        "lab_id": lab_id,
        "has_conflicts": False,
        "conflicts": [],
        "error": None,
    }


def test_networks_reports_leftover_conflict(
    client: TestClient, lab_definition: dict, runtime
) -> None:
    runtime.networks = [_leftover()]
    lab_id = _create(client, lab_definition)

    body = client.get(f"/labs/{lab_id}/networks").json()

    assert body["has_conflicts"] is True
    conflict = body["conflicts"][0]
    assert conflict["network_id"] == "left"
    assert conflict["subnet"] == "10.0.1.0/24"
    assert conflict["reason"] == "overlaps_leftover"
    assert conflict["owner_network_name"] == "practicum-deadbeef-left"
    assert conflict["owner_lab_id"] == LEFTOVER_LAB_ID
    assert conflict["owner_container_count"] == 1
    assert conflict["recommended_subnet"] == "10.90.0.0/24"


def test_networks_reports_other_listed_lab(
    client: TestClient, lab_definition: dict, runtime
) -> None:
    other_id = _create(client, lab_definition)
    runtime.networks = [
        DockerNetworkInfo(
            name=f"practicum-{other_id[:8]}-left",
            subnets=[IPv4Network("10.0.1.0/24")],
            lab_id=other_id,
        )
    ]
    lab_id = _create(client, lab_definition)

    conflict = client.get(f"/labs/{lab_id}/networks").json()["conflicts"][0]

    assert conflict["reason"] == "overlaps_other_lab"
    assert conflict["owner_lab_id"] == other_id
    assert conflict["owner_lab_name"] == "Static Routing Fundamentals"
    assert conflict["owner_lab_status"] == "defined"


def test_networks_reports_docker_failure_instead_of_raising(
    client: TestClient, lab_definition: dict, runtime
) -> None:
    runtime.fail_listing = "Docker Desktop is not running"
    lab_id = _create(client, lab_definition)

    body = client.get(f"/labs/{lab_id}/networks").json()

    assert body["has_conflicts"] is False
    assert body["conflicts"] == []
    assert body["error"] == "Docker Desktop is not running"


def test_networks_404_for_unknown_lab(client: TestClient, runtime) -> None:
    assert client.get("/labs/nope/networks").status_code == 404


def test_apply_subnet_recommendation_moves_network_and_interfaces(
    client: TestClient, lab_definition: dict, runtime
) -> None:
    runtime.networks = [_leftover()]
    lab_id = _create(client, lab_definition)

    response = client.post(
        f"/labs/{lab_id}/networks/apply-recommendation", json={"network_id": "left"}
    )

    assert response.status_code == 200
    assert response.json()["has_conflicts"] is False
    lab = client.get(f"/labs/{lab_id}").json()
    assert {n["id"]: n["subnet"] for n in lab["networks"]} == {
        "left": "10.90.0.0/24",
        "right": "10.0.2.0/24",
    }
    assert {(i["node"], i["network"]): i["address"] for i in lab["interfaces"]}[
        ("host-a", "left")
    ] == "10.90.0.10/24"
    # The portable export reflects the change too.
    assert client.get(f"/labs/{lab_id}/export").json()["networks"][0]["subnet"] == "10.90.0.0/24"


def test_apply_subnet_recommendation_409_when_nothing_to_fix(
    client: TestClient, lab_definition: dict, runtime
) -> None:
    lab_id = _create(client, lab_definition)

    response = client.post(
        f"/labs/{lab_id}/networks/apply-recommendation", json={"network_id": "left"}
    )

    assert response.status_code == 409
    assert "No recommended subnet" in response.json()["detail"]


def test_remove_leftover_removes_containers_and_network(
    client: TestClient, lab_definition: dict, runtime
) -> None:
    runtime.networks = [_leftover()]
    lab_id = _create(client, lab_definition)

    response = client.post(
        f"/labs/{lab_id}/networks/remove-leftover",
        json={"network_name": "practicum-deadbeef-left"},
    )

    assert response.status_code == 200
    assert response.json()["has_conflicts"] is False
    assert runtime.removed == ["practicum-deadbeef-left"]
    # The lab itself was not modified.
    assert client.get(f"/labs/{lab_id}").json()["networks"][0]["subnet"] == "10.0.1.0/24"


def test_remove_leftover_refuses_networks_of_listed_labs(
    client: TestClient, lab_definition: dict, runtime
) -> None:
    other_id = _create(client, lab_definition)
    runtime.networks = [
        DockerNetworkInfo(
            name=f"practicum-{other_id[:8]}-left",
            subnets=[IPv4Network("10.0.1.0/24")],
            lab_id=other_id,
        )
    ]
    lab_id = _create(client, lab_definition)

    response = client.post(
        f"/labs/{lab_id}/networks/remove-leftover",
        json={"network_name": f"practicum-{other_id[:8]}-left"},
    )

    assert response.status_code == 409
    assert "reset that lab instead" in response.json()["detail"]
    assert runtime.removed == []


def test_remove_leftover_refuses_foreign_docker_networks(
    client: TestClient, lab_definition: dict, runtime
) -> None:
    runtime.networks = [
        DockerNetworkInfo(name="compose_default", subnets=[IPv4Network("10.0.1.0/24")])
    ]
    lab_id = _create(client, lab_definition)

    response = client.post(
        f"/labs/{lab_id}/networks/remove-leftover", json={"network_name": "compose_default"}
    )

    assert response.status_code == 409
    assert "not created by Practicum" in response.json()["detail"]
    assert runtime.removed == []


def test_remove_leftover_refuses_unrelated_network_names(
    client: TestClient, lab_definition: dict, runtime
) -> None:
    runtime.networks = [_leftover()]
    lab_id = _create(client, lab_definition)

    response = client.post(
        f"/labs/{lab_id}/networks/remove-leftover", json={"network_name": "something-else"}
    )

    assert response.status_code == 409
    assert "does not conflict" in response.json()["detail"]
