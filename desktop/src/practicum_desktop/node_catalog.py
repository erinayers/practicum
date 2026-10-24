"""Ready-made machine types for the Custom Lab designer (designer-node-catalog).

An instructor building a topology picks a machine *type* instead of typing a Docker image:
"Ubuntu host", "Router", "Web server", "Ubuntu Desktop" … Each preset is a complete node
recipe (image, start command, environment, resources, sysctls) so the machines can be
daisy-chained into a working topology — e.g. host — router — host — without knowing which
image forwards packets or which ports a desktop publishes. "Custom image" keeps the
free-form path.

Presets only produce ordinary lab nodes; nothing here is stored in the spec beyond the node
fields themselves (the preset key is kept on the node's draft for display only).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from practicum_desktop.quickstart import WEBTOP_IMAGE

KEEP_IMAGE_COMMAND = None  # `command: null` → the image's own entrypoint/CMD runs


@dataclass(frozen=True)
class NodePreset:
    key: str
    title: str
    image: str
    role: str  # host | router | server | desktop | custom
    description: str
    id_prefix: str
    glyph: str = "\u25a0"
    # None = keep the image's command (`command: null`); () = the spec default (sleep infinity);
    # otherwise the explicit argv.
    command: tuple[str, ...] | None = ()
    environment: dict[str, str] = field(default_factory=dict)
    cpu: float | None = None
    memory_mb: int | None = None
    shm_size_mb: int | None = None
    port_mappings: tuple[tuple[int, int], ...] = ()  # (host, container), tcp
    sysctls: dict[str, str] = field(default_factory=dict)
    editable_image: bool = False

    def node(self, node_id: str, image: str | None = None) -> dict[str, object]:
        """A complete lab node for this preset."""
        node: dict[str, object] = {"id": node_id, "image": image or self.image}
        if self.command is None:
            node["command"] = None
        elif self.command:
            node["command"] = list(self.command)
        if self.environment:
            node["environment"] = dict(self.environment)
        resources: dict[str, object] = {}
        if self.cpu is not None:
            resources["cpu"] = self.cpu
        if self.memory_mb is not None:
            resources["memory_mb"] = self.memory_mb
        if self.shm_size_mb is not None:
            resources["shm_size_mb"] = self.shm_size_mb
        if self.port_mappings:
            resources["port_mappings"] = [
                {"host": host, "container": container} for host, container in self.port_mappings
            ]
        if self.sysctls:
            resources["sysctls"] = dict(self.sysctls)
        if resources:
            node["resources"] = resources
        return node


PRESETS: tuple[NodePreset, ...] = (
    NodePreset(
        key="ubuntu-host",
        title="Ubuntu host",
        image="ubuntu:22.04",
        role="host",
        description="A plain Ubuntu machine you reach with Open shell (apt, python3, ping…).",
        id_prefix="host",
        glyph="\u25a0",
        cpu=1,
        memory_mb=512,
    ),
    NodePreset(
        key="alpine-host",
        title="Alpine host (tiny)",
        image="alpine:3.21",
        role="host",
        description="A very small Linux host - downloads in seconds; has ping, ip, wget.",
        id_prefix="host",
        glyph="\u25a1",
        cpu=0.5,
        memory_mb=128,
    ),
    NodePreset(
        key="router",
        title="Router",
        image="alpine:3.21",
        role="router",
        description=(
            "Forwards packets between the networks it is connected to (IP forwarding on). "
            "Connect it to two or more networks; give the hosts its address as their gateway."
        ),
        id_prefix="router",
        glyph="\u25c6",
        cpu=0.5,
        memory_mb=128,
        sysctls={"net.ipv4.ip_forward": "1"},
    ),
    NodePreset(
        key="web-server",
        title="Web server",
        image="nginx:latest",
        role="server",
        description="nginx serving a default page on port 80; published on this computer's port 8080.",
        id_prefix="web",
        glyph="\u25a3",
        command=None,
        cpu=0.5,
        memory_mb=256,
        port_mappings=((8080, 80),),
    ),
    NodePreset(
        key="ubuntu-desktop",
        title="Ubuntu Desktop",
        image=WEBTOP_IMAGE,
        role="desktop",
        description="A full Ubuntu desktop shown in Practicum's lab view (browser on port 3000).",
        id_prefix="desktop",
        glyph="\u25a3",
        command=None,
        environment={"TITLE": "Practicum"},
        cpu=2,
        memory_mb=2048,
        shm_size_mb=1024,
        port_mappings=((3000, 3000), (3001, 3001)),
    ),
    NodePreset(
        key="custom",
        title="Custom image",
        image="",
        role="custom",
        description="Any Docker image; runs `sleep infinity` unless the image has its own service.",
        id_prefix="node",
        glyph="\u25cc",
        editable_image=True,
    ),
)

DEFAULT_PRESET = PRESETS[0]


def preset_by_key(key: str | None) -> NodePreset:
    return next((p for p in PRESETS if p.key == key), PRESETS[-1])


def preset_for_node(node: dict[str, object]) -> NodePreset:
    """Best guess of the preset a stored node came from (for display when editing)."""
    image = str(node.get("image", ""))
    resources = node.get("resources") or {}
    if (
        isinstance(resources, dict)
        and (resources.get("sysctls") or {}).get("net.ipv4.ip_forward") == "1"
    ):
        return preset_by_key("router")
    for preset in PRESETS:
        if preset.image and preset.image == image and preset.key != "router":
            return preset
    return preset_by_key("custom")


def next_node_id(prefix: str, existing: list[str]) -> str:
    """'host' → 'host-1', then 'host-2' …, skipping ids already in use."""
    taken = set(existing)
    number = 1
    while f"{prefix}-{number}" in taken:
        number += 1
    return f"{prefix}-{number}"


def suggest_address(subnet: str, used: list[str], role: str = "host") -> str:
    """The next free address on `subnet` for a machine of `role`, as `ip/prefix`.

    Routers get the lowest host address (.1, .2 …) because that is what students expect a
    gateway to be; other machines start at .10 (hosts .10, .11 …). The network address, the
    broadcast address and the highest usable address (Practicum's Docker gateway, D-14) are
    skipped, as is anything already assigned.
    """
    from ipaddress import IPv4Network

    network = IPv4Network(subnet, strict=False)
    taken = {ip.split("/")[0] for ip in used}
    first = int(network.network_address) + 1
    last = int(network.broadcast_address) - 1  # highest usable = Docker gateway, skip it
    start = first if role == "router" else min(first + 9, last - 1)
    candidates = list(range(start, last)) + list(range(first, start))
    for value in candidates:
        address = str(network.network_address + (value - int(network.network_address)))
        if address not in taken:
            return f"{address}/{network.prefixlen}"
    return ""
