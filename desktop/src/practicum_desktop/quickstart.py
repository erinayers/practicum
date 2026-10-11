from __future__ import annotations

import copy
from ipaddress import IPv4Network, ip_network
from typing import Iterable

from practicum_desktop.api_client import ApiClient, CreateLabResult

# A dedicated /16 reserved for auto-picked quick-start subnets, so repeated
# clicks don't collide with each other or with hand-authored labs.
QUICK_START_SUBNET_POOL = ip_network("10.90.0.0/16")

# Mirrors examples/ubuntu-quickstart.json; kept in-package so the desktop app
# can offer it with no filesystem dependency on the source repo layout.
UBUNTU_QUICK_START_LAB: dict[str, object] = {
    "schema_version": "1.0",
    "name": "Ubuntu Quick Start",
    "description": "A single plain Ubuntu container for quickly exploring Practicum with no topology to configure.",
    "author": "Practicum Team",
    "version": "0.1.0",
    "manual": {
        "sections": [
            {
                "id": "get-started",
                "title": "Get Started",
                "content_markdown": (
                    "This lab gives you a single Ubuntu 22.04 container to explore. "
                    "It has no GUI — you interact with it entirely from a shell.\n\n"
                    "1. Start the lab from Practicum.\n"
                    "2. Find the container:\n\n"
                    "```\ndocker ps --filter \"name=practicum\"\n```\n\n"
                    "3. Open a shell in it:\n\n"
                    "```\ndocker exec -it <container-name> bash\n```\n\n"
                    "You now have a full Ubuntu shell to experiment in."
                ),
                "tasks": [
                    {"id": "start-lab", "text": "Start the lab from Practicum."},
                    {
                        "id": "open-shell",
                        "text": "Open a shell in the Ubuntu container with docker exec.",
                    },
                ],
            }
        ]
    },
    "nodes": [
        {
            "id": "ubuntu",
            "image": "ubuntu:22.04",
            "resources": {"cpu": 1, "memory_mb": 512},
        }
    ],
    "networks": [{"id": "lab-net", "subnet": "10.50.0.0/24"}],
    "interfaces": [
        {"node": "ubuntu", "network": "lab-net", "address": "10.50.0.10/24"}
    ],
}


def _pick_free_subnet(existing_subnets: Iterable[str]) -> IPv4Network:
    used: set[IPv4Network] = set()
    for subnet in existing_subnets:
        try:
            used.add(ip_network(subnet, strict=False))
        except ValueError:
            continue

    for candidate in QUICK_START_SUBNET_POOL.subnets(new_prefix=24):
        if candidate not in used:
            return candidate

    raise RuntimeError("No free quick-start subnet is available")


def build_ubuntu_quick_start_lab(existing_subnets: Iterable[str] = ()) -> dict[str, object]:
    """Returns a fresh copy of the quick-start lab with a subnet that avoids existing_subnets."""
    subnet = _pick_free_subnet(existing_subnets)
    host_address = f"{subnet.network_address + 10}/{subnet.prefixlen}"

    lab = copy.deepcopy(UBUNTU_QUICK_START_LAB)
    lab["networks"][0]["subnet"] = str(subnet)
    lab["interfaces"][0]["address"] = host_address
    return lab


def create_ubuntu_quick_start_lab(api_client: ApiClient) -> CreateLabResult:
    """Builds a quick-start lab avoiding subnets already used by existing labs, then saves it."""
    existing_subnets: list[str] = []
    labs_result = api_client.list_labs()
    if labs_result.success:
        for lab in labs_result.labs:
            preview = api_client.get_preview(lab.id)
            if preview.success:
                existing_subnets.extend(preview.network_subnets)

    lab = build_ubuntu_quick_start_lab(existing_subnets)
    return api_client.create_lab(lab)
