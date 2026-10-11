from __future__ import annotations

import os
import socket

from practicum.models import Lab, PortConflict

DEFAULT_MIN_RECOMMENDED_PORT = 1024
DEFAULT_MAX_RECOMMENDED_PORT = 65535


def api_reserved_port() -> int:
    return int(os.environ.get("PRACTICUM_API_PORT", "8000"))


def is_local_port_free(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.2)
        try:
            sock.bind(("127.0.0.1", port))
        except OSError:
            return False
        return True


def find_available_port(
    start_after: int,
    unavailable: set[int],
    minimum: int = DEFAULT_MIN_RECOMMENDED_PORT,
    maximum: int = DEFAULT_MAX_RECOMMENDED_PORT,
) -> int | None:
    candidate = max(start_after + 1, minimum)
    while candidate <= maximum:
        if candidate not in unavailable and is_local_port_free(candidate):
            return candidate
        candidate += 1
    return None


def check_lab_ports(lab: Lab) -> list[PortConflict]:
    """Report host port conflicts: duplicates within the spec, the Practicum API's own
    port, and ports already bound on this host. Each conflict includes a recommended,
    currently-available replacement that avoids every other port already in play."""
    reserved_port = api_reserved_port()
    mappings: list[tuple[str, int, int, str]] = []

    for node in lab.nodes:
        if node.resources is None:
            continue
        for port in node.resources.exposed_ports:
            mappings.append((node.id, port, port, "tcp"))
        for mapping in node.resources.port_mappings:
            mappings.append((node.id, mapping.host, mapping.container, mapping.protocol))

    host_counts: dict[tuple[int, str], int] = {}
    for _, host, _, protocol in mappings:
        key = (host, protocol)
        host_counts[key] = host_counts.get(key, 0) + 1

    reserved_ports = {reserved_port} | {host for _, host, _, _ in mappings}

    conflicts: list[PortConflict] = []
    for node_id, host, container, protocol in mappings:
        if host_counts[(host, protocol)] > 1:
            reason = "duplicate_in_spec"
        elif host == reserved_port:
            reason = "reserved_by_practicum_api"
        elif not is_local_port_free(host):
            reason = "in_use_on_host"
        else:
            continue

        recommended = find_available_port(host, reserved_ports)
        if recommended is not None:
            reserved_ports.add(recommended)

        conflicts.append(
            PortConflict(
                node_id=node_id,
                host_port=host,
                container_port=container,
                protocol=protocol,
                reason=reason,
                recommended_port=recommended,
            )
        )

    return conflicts
