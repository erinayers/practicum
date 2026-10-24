import socket

from practicum import ports
from practicum.models import Lab, LabDefinition


def test_check_lab_ports_reports_no_conflicts_when_everything_is_free(
    monkeypatch, lab_definition: dict
) -> None:
    monkeypatch.setattr(ports, "is_local_port_free", lambda port, protocol="tcp": True)
    definition = LabDefinition.model_validate(lab_definition)
    lab = Lab(id="lab-1", **definition.model_dump())

    conflicts = ports.check_lab_ports(lab)

    assert conflicts == []


def test_check_lab_ports_flags_port_already_in_use_on_host(
    monkeypatch, lab_definition: dict
) -> None:
    def fake_is_free(port: int, protocol: str = "tcp") -> bool:
        return port != 2222

    monkeypatch.setattr(ports, "is_local_port_free", fake_is_free)
    definition = LabDefinition.model_validate(lab_definition)
    lab = Lab(id="lab-1", **definition.model_dump())

    conflicts = ports.check_lab_ports(lab)

    assert len(conflicts) == 1
    conflict = conflicts[0]
    assert conflict.node_id == "router"
    assert conflict.host_port == 2222
    assert conflict.reason == "in_use_on_host"
    assert conflict.recommended_port is not None
    assert conflict.recommended_port not in {22, 2222, ports.api_reserved_port()}


def test_check_lab_ports_flags_port_reserved_by_practicum_api(
    monkeypatch, lab_definition: dict
) -> None:
    monkeypatch.setattr(ports, "is_local_port_free", lambda port, protocol="tcp": True)
    monkeypatch.setenv("PRACTICUM_API_PORT", "2222")
    definition = LabDefinition.model_validate(lab_definition)
    lab = Lab(id="lab-1", **definition.model_dump())

    conflicts = ports.check_lab_ports(lab)

    assert len(conflicts) == 1
    assert conflicts[0].host_port == 2222
    assert conflicts[0].reason == "reserved_by_practicum_api"
    assert conflicts[0].recommended_port is not None


def test_check_lab_ports_flags_duplicate_host_ports_across_nodes(
    monkeypatch, lab_definition: dict
) -> None:
    monkeypatch.setattr(ports, "is_local_port_free", lambda port, protocol="tcp": True)
    lab_definition["nodes"][0]["resources"] = {"port_mappings": [{"host": 5000, "container": 80}]}
    lab_definition["nodes"][2]["resources"] = {"port_mappings": [{"host": 5000, "container": 81}]}
    definition = LabDefinition.model_validate(lab_definition)
    lab = Lab(id="lab-1", **definition.model_dump())

    conflicts = ports.check_lab_ports(lab)

    duplicate_conflicts = [c for c in conflicts if c.reason == "duplicate_in_spec"]
    assert {c.node_id for c in duplicate_conflicts} == {"host-a", "host-b"}
    assert all(c.host_port == 5000 for c in duplicate_conflicts)


def test_check_lab_ports_recommendation_avoids_ports_already_in_use(
    monkeypatch, lab_definition: dict
) -> None:
    def fake_is_free(port: int, protocol: str = "tcp") -> bool:
        return port not in {2222, 2223}

    monkeypatch.setattr(ports, "is_local_port_free", fake_is_free)
    definition = LabDefinition.model_validate(lab_definition)
    lab = Lab(id="lab-1", **definition.model_dump())

    conflicts = ports.check_lab_ports(lab)

    assert conflicts[0].recommended_port == 2224


def test_find_available_port_skips_unavailable_ports(monkeypatch) -> None:
    monkeypatch.setattr(ports, "is_local_port_free", lambda port, protocol="tcp": True)

    result = ports.find_available_port(2000, unavailable={2001, 2002})

    assert result == 2003


def test_find_available_port_returns_none_when_range_exhausted(monkeypatch) -> None:
    monkeypatch.setattr(ports, "is_local_port_free", lambda port, protocol="tcp": False)

    result = ports.find_available_port(65533, unavailable=set())

    assert result is None


def test_is_local_port_free_reports_false_for_bound_port(real_port_probe) -> None:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        sock.listen(1)
        bound_port = sock.getsockname()[1]

        assert real_port_probe(bound_port) is False


def test_is_local_port_free_probes_udp_ports_with_udp(real_port_probe) -> None:
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.bind(("127.0.0.1", 0))
        bound_port = sock.getsockname()[1]

        assert real_port_probe(bound_port, "udp") is False
        # A TCP probe of the same number says nothing about UDP: it must not be reused.
        assert real_port_probe(bound_port, "tcp") is True


def test_api_reserved_port_defaults_to_8000(monkeypatch) -> None:
    monkeypatch.delenv("PRACTICUM_API_PORT", raising=False)

    assert ports.api_reserved_port() == 8000
