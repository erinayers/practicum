import pytest
from fastapi.testclient import TestClient

from practicum.main import app, service
from practicum.runtime import DockerRuntime


@pytest.fixture(autouse=True)
def clear_labs() -> None:
    service.clear()
    service.runtime = DockerRuntime()


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture
def lab_definition() -> dict:
    return {
        "schema_version": "1.0",
        "name": "Static Routing Fundamentals",
        "description": "Practice configuring static routes across two routed subnets.",
        "author": "Practicum Team",
        "version": "0.1.0",
        "manual": {
            "sections": [
                {
                    "id": "overview",
                    "title": "Overview",
                    "content_markdown": (
                        "## Goal\n\nConfigure static routes so host-a can reach host-b."
                    ),
                    "tasks": [
                        {
                            "id": "verify-topology",
                            "text": "Review the topology before starting the lab.",
                        }
                    ],
                },
                {
                    "id": "configure-routes",
                    "title": "Configure Routes",
                    "content_markdown": (
                        "Add routes on each host and verify connectivity with `ping`."
                    ),
                    "tasks": [],
                },
            ]
        },
        "nodes": [
            {
                "id": "host-a",
                "image": "alpine:3.21",
                "resources": {"cpu": 0.5, "memory_mb": 128},
            },
            {
                "id": "router",
                "image": "alpine:3.21",
                "resources": {
                    "cpu": 1,
                    "memory_mb": 256,
                    "exposed_ports": [22],
                    "port_mappings": [{"host": 2222, "container": 22}],
                },
            },
            {
                "id": "host-b",
                "image": "alpine:3.21",
                "resources": {"cpu": 0.5, "memory_mb": 128},
            },
        ],
        "networks": [
            {"id": "left", "subnet": "10.0.1.0/24"},
            {"id": "right", "subnet": "10.0.2.0/24"},
        ],
        "interfaces": [
            {"node": "host-a", "network": "left", "address": "10.0.1.10/24"},
            {"node": "router", "network": "left", "address": "10.0.1.1/24"},
            {"node": "router", "network": "right", "address": "10.0.2.1/24"},
            {"node": "host-b", "network": "right", "address": "10.0.2.10/24"},
        ],
    }
