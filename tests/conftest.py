import pytest
from fastapi.testclient import TestClient

from practicum import ports
from practicum.main import app, service
from practicum.runtime import DockerRuntime

# The real loopback bind probe; tests get a "every port is free" stand-in by default so the
# suite does not depend on what happens to be listening on the machine running it
# (POST /start re-checks ports). `real_port_probe` hands the original back when a test
# wants to exercise it.
REAL_IS_LOCAL_PORT_FREE = ports.is_local_port_free


@pytest.fixture(autouse=True)
def clear_labs(monkeypatch) -> None:
    service.clear()
    service.runtime = DockerRuntime()
    monkeypatch.setattr(ports, "is_local_port_free", lambda port, protocol="tcp": True)


@pytest.fixture
def real_port_probe():
    return REAL_IS_LOCAL_PORT_FREE


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
                    "requires_screenshot": False,
                },
                {
                    "id": "configure-routes",
                    "title": "Configure Routes",
                    "content_markdown": (
                        "Add routes on each host and verify connectivity with `ping`."
                    ),
                    "tasks": [],
                    "requires_screenshot": False,
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
