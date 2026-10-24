"""Subnet conflict detection and recommendations for a lab's networks.

Docker refuses to create a bridge network whose subnet overlaps one that already exists
("Pool overlaps with other one on this address space"), so a lab that looks fine on paper
can still fail at the very last step. This module answers, before Start: which of the
lab's subnets collide with a network already on the Docker host, who owns that network,
and what free subnet could be used instead.
"""

from __future__ import annotations

from collections.abc import Iterable
from ipaddress import IPv4Network

from practicum.models import DockerNetworkInfo, Lab, SubnetConflict

# Recommendations are drawn from here so they stay clear of hand-authored lab subnets
# (10.0.x / 10.50.x are used by the examples and the Quick Start template).
RECOMMENDATION_POOL = IPv4Network("10.90.0.0/16")


def recommend_subnet(prefix_length: int, unavailable: Iterable[IPv4Network]) -> IPv4Network | None:
    """First subnet of `prefix_length` in the pool that overlaps nothing in `unavailable`."""
    if prefix_length < RECOMMENDATION_POOL.prefixlen or prefix_length > 30:
        return None
    taken = list(unavailable)
    for candidate in RECOMMENDATION_POOL.subnets(new_prefix=prefix_length):
        if not any(candidate.overlaps(other) for other in taken):
            return candidate
    return None


def find_subnet_conflicts(
    lab: Lab,
    docker_networks: list[DockerNetworkInfo],
    known_labs: dict[str, Lab],
) -> list[SubnetConflict]:
    """Conflicts between `lab`'s subnets and networks already present on the Docker host.

    Networks belonging to `lab` itself (same practicum.lab_id) are never conflicts: a
    stopped lab keeps its networks and reuses them on the next start.
    """
    lab_subnets = [network.subnet for network in lab.networks]
    unavailable: list[IPv4Network] = list(lab_subnets)
    for docker_network in docker_networks:
        unavailable.extend(docker_network.subnets)
    for other in known_labs.values():
        if other.id != lab.id:
            unavailable.extend(network.subnet for network in other.networks)

    conflicts: list[SubnetConflict] = []
    for network in lab.networks:
        owner = _first_overlapping(network.subnet, docker_networks, lab.id)
        if owner is None:
            continue
        docker_network, owner_subnet = owner

        owner_lab = known_labs.get(docker_network.lab_id) if docker_network.lab_id else None
        if owner_lab is not None:
            reason = "overlaps_other_lab"
        elif docker_network.lab_id:
            reason = "overlaps_leftover"
        else:
            reason = "overlaps_docker_network"

        recommended = recommend_subnet(network.subnet.prefixlen, unavailable)
        if recommended is not None:
            unavailable.append(recommended)

        conflicts.append(
            SubnetConflict(
                network_id=network.id,
                subnet=network.subnet,
                reason=reason,
                owner_network_name=docker_network.name,
                owner_subnet=owner_subnet,
                owner_lab_id=docker_network.lab_id,
                owner_lab_name=owner_lab.name if owner_lab else None,
                owner_lab_status=owner_lab.status if owner_lab else None,
                owner_container_count=len(docker_network.container_names),
                recommended_subnet=recommended,
            )
        )
    return conflicts


def _first_overlapping(
    subnet: IPv4Network, docker_networks: list[DockerNetworkInfo], own_lab_id: str
) -> tuple[DockerNetworkInfo, IPv4Network] | None:
    for docker_network in docker_networks:
        if docker_network.lab_id == own_lab_id:
            continue
        for owner_subnet in docker_network.subnets:
            if owner_subnet.overlaps(subnet):
                return docker_network, owner_subnet
    return None


def move_subnet(lab: Lab, network_id: str, new_subnet: IPv4Network) -> dict:
    """Returns `lab`'s definition (as a dict) with `network_id` moved to `new_subnet`.

    Interface addresses on that network keep their host offset, so 10.50.0.10/24 on
    10.50.0.0/24 becomes 10.90.0.10/24 on 10.90.0.0/24. Raises ValueError when the new
    subnet is a different size (offsets could fall outside it).
    """
    old_subnet = next(n.subnet for n in lab.networks if n.id == network_id)
    if new_subnet.prefixlen != old_subnet.prefixlen:
        raise ValueError("the replacement subnet must have the same prefix length")

    definition = lab.model_dump(exclude={"id", "status"}, mode="json")
    for network in definition["networks"]:
        if network["id"] == network_id:
            network["subnet"] = str(new_subnet)
    for interface in definition["interfaces"]:
        if interface["network"] != network_id:
            continue
        old_ip, _, _prefix = interface["address"].partition("/")
        offset = int(IPv4Network(f"{old_ip}/32").network_address) - int(old_subnet.network_address)
        new_ip = new_subnet.network_address + offset
        interface["address"] = f"{new_ip}/{new_subnet.prefixlen}"
    return definition
