from ipaddress import IPv4Network

import pytest

from practicum.models import DockerNetworkInfo, Lab, LabDefinition
from practicum.networks import (
    RECOMMENDATION_POOL,
    find_subnet_conflicts,
    move_subnet,
    recommend_subnet,
)


def _lab(lab_definition: dict, lab_id: str = "11111111-aaaa-bbbb-cccc-000000000001") -> Lab:
    definition = LabDefinition.model_validate(lab_definition)
    return Lab(id=lab_id, **definition.model_dump())


def test_recommend_subnet_picks_first_free_block_in_pool() -> None:
    assert recommend_subnet(24, []) == IPv4Network("10.90.0.0/24")


def test_recommend_subnet_skips_taken_blocks() -> None:
    taken = [IPv4Network("10.90.0.0/24"), IPv4Network("10.90.1.0/25")]

    assert recommend_subnet(24, taken) == IPv4Network("10.90.2.0/24")


def test_recommend_subnet_returns_none_for_subnets_larger_than_pool() -> None:
    assert recommend_subnet(RECOMMENDATION_POOL.prefixlen - 1, []) is None


def test_no_conflicts_when_docker_has_unrelated_networks(lab_definition: dict) -> None:
    lab = _lab(lab_definition)
    docker = [DockerNetworkInfo(name="bridge", subnets=[IPv4Network("172.17.0.0/16")])]

    assert find_subnet_conflicts(lab, docker, {lab.id: lab}) == []


def test_own_networks_are_never_conflicts(lab_definition: dict) -> None:
    lab = _lab(lab_definition)
    docker = [
        DockerNetworkInfo(
            name="practicum-11111111-left",
            subnets=[IPv4Network("10.0.1.0/24")],
            lab_id=lab.id,
            container_names=["practicum-11111111-host-a"],
        )
    ]

    assert find_subnet_conflicts(lab, docker, {lab.id: lab}) == []


def test_leftover_conflict_reports_owner_and_recommendation(lab_definition: dict) -> None:
    lab = _lab(lab_definition)
    docker = [
        DockerNetworkInfo(
            name="practicum-deadbeef-left",
            subnets=[IPv4Network("10.0.1.0/24")],
            lab_id="deadbeef-0000-0000-0000-000000000000",
            container_names=["practicum-deadbeef-host-a"],
        )
    ]

    conflicts = find_subnet_conflicts(lab, docker, {lab.id: lab})

    assert len(conflicts) == 1
    conflict = conflicts[0]
    assert conflict.network_id == "left"
    assert conflict.reason == "overlaps_leftover"
    assert conflict.owner_network_name == "practicum-deadbeef-left"
    assert conflict.owner_lab_id == "deadbeef-0000-0000-0000-000000000000"
    assert conflict.owner_lab_name is None
    assert conflict.owner_container_count == 1
    assert conflict.recommended_subnet == IPv4Network("10.90.0.0/24")


def test_other_listed_lab_conflict_names_that_lab(lab_definition: dict) -> None:
    lab = _lab(lab_definition)
    other = _lab(lab_definition, lab_id="22222222-aaaa-bbbb-cccc-000000000002")
    other.status = "stopped"
    docker = [
        DockerNetworkInfo(
            name="practicum-22222222-left",
            subnets=[IPv4Network("10.0.1.0/24")],
            lab_id=other.id,
        )
    ]

    conflicts = find_subnet_conflicts(lab, docker, {lab.id: lab, other.id: other})

    assert conflicts[0].reason == "overlaps_other_lab"
    assert conflicts[0].owner_lab_name == "Static Routing Fundamentals"
    assert conflicts[0].owner_lab_status == "stopped"


def test_foreign_docker_network_partial_overlap_is_reported(lab_definition: dict) -> None:
    lab = _lab(lab_definition)
    docker = [DockerNetworkInfo(name="my-compose-net", subnets=[IPv4Network("10.0.0.0/16")])]

    conflicts = find_subnet_conflicts(lab, docker, {lab.id: lab})

    assert [c.network_id for c in conflicts] == ["left", "right"]
    assert all(c.reason == "overlaps_docker_network" for c in conflicts)
    assert conflicts[0].owner_subnet == IPv4Network("10.0.0.0/16")
    # Two distinct recommendations, neither overlapping the other or anything taken.
    assert conflicts[0].recommended_subnet == IPv4Network("10.90.0.0/24")
    assert conflicts[1].recommended_subnet == IPv4Network("10.90.1.0/24")


def test_recommendation_avoids_other_labs_subnets(lab_definition: dict) -> None:
    lab = _lab(lab_definition)
    other_def = dict(lab_definition)
    other_def["networks"] = [{"id": "n", "subnet": "10.90.0.0/24"}]
    other_def["nodes"] = [{"id": "a", "image": "alpine:3.21"}]
    other_def["interfaces"] = [{"node": "a", "network": "n", "address": "10.90.0.5/24"}]
    other = _lab(other_def, lab_id="22222222-aaaa-bbbb-cccc-000000000002")
    docker = [DockerNetworkInfo(name="x", subnets=[IPv4Network("10.0.1.0/24")])]

    conflicts = find_subnet_conflicts(lab, docker, {lab.id: lab, other.id: other})

    assert conflicts[0].recommended_subnet == IPv4Network("10.90.1.0/24")


def test_move_subnet_keeps_host_offsets(lab_definition: dict) -> None:
    lab = _lab(lab_definition)

    moved = move_subnet(lab, "left", IPv4Network("10.90.0.0/24"))

    networks = {n["id"]: n["subnet"] for n in moved["networks"]}
    assert networks == {"left": "10.90.0.0/24", "right": "10.0.2.0/24"}
    addresses = {(i["node"], i["network"]): i["address"] for i in moved["interfaces"]}
    assert addresses[("host-a", "left")] == "10.90.0.10/24"
    assert addresses[("router", "left")] == "10.90.0.1/24"
    assert addresses[("router", "right")] == "10.0.2.1/24"
    LabDefinition.model_validate(moved)  # still a valid lab


def test_move_subnet_rejects_different_prefix_length(lab_definition: dict) -> None:
    lab = _lab(lab_definition)

    with pytest.raises(ValueError, match="same prefix length"):
        move_subnet(lab, "left", IPv4Network("10.90.0.0/25"))


def test_move_subnet_rewrites_addresses_quoted_in_the_manual(lab_definition: dict) -> None:
    lab_definition["manual"]["sections"][0]["content_markdown"] = (
        "host-a is 10.0.1.10 and the router is 10.0.1.1 on 10.0.1.0/24; host-b is 10.0.2.10.\n"
        "```\nping -c 3 10.0.1.10\n```\nAlso 10.0.1.10/24. Not touched: 10.0.1.100, 110.0.1.1."
    )
    lab_definition["manual"]["sections"][0]["tasks"][0]["text"] = "Ping 10.0.1.1 from host-a."
    lab = _lab(lab_definition)

    moved = move_subnet(lab, "left", IPv4Network("10.90.0.0/24"))

    text = moved["manual"]["sections"][0]["content_markdown"]
    assert "host-a is 10.90.0.10 and the router is 10.90.0.1 on 10.90.0.0/24" in text
    assert "host-b is 10.0.2.10" in text  # other network untouched
    assert "ping -c 3 10.90.0.10" in text
    assert "Also 10.90.0.10/24." in text
    assert "10.0.1.100" in text and "110.0.1.1" in text
    assert moved["manual"]["sections"][0]["tasks"][0]["text"] == "Ping 10.90.0.1 from host-a."
