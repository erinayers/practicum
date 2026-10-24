"""Quick Start lab templates (designer-quick-start-lab).

A quick-start lab is a single-host lab generated from a template: the student (or an
instructor preparing one) picks the template, names the lab, optionally lists packages to
pre-install and writes the instruction steps; `build_quick_start_lab` turns that into an
ordinary lab definition that goes through the same validate/create/gate/start path as any
other lab. Steps become one manual section each.

Two kinds of template (D-35):

* **desktop** — a full Ubuntu desktop in the browser (`linuxserver/webtop`), shown inside the
  running view's embedded lab view. Meant for simple or non-IT labs where a terminal would be
  a barrier. Packages are installed by the image's own init through the LinuxServer
  `universal-package-install` mod (`DOCKER_MODS` + `INSTALL_PACKAGES=a|b|c`); the image's
  command must stay untouched (`command: null`).
* **terminal** — a plain `ubuntu:22.04` container reached with Open shell. Packages become the
  node's start command (apt-get on first boot, then `sleep infinity`).

Subnets are drawn from a dedicated /16 (D-17) so repeated quick starts don't collide with
each other or with hand-authored labs.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from ipaddress import IPv4Network, ip_network

from practicum_desktop.api_client import ApiClient, CreateLabResult

# A dedicated /16 reserved for auto-picked quick-start subnets.
QUICK_START_SUBNET_POOL = ip_network("10.90.0.0/16")

PACKAGE_NAME = re.compile(r"^[a-z0-9][a-z0-9+.\-]*$")
ID_SAFE = re.compile(r"[^a-z0-9-]+")


@dataclass(frozen=True)
class QuickStartTemplate:
    key: str
    title: str
    caption: str
    image: str
    base_label: str
    kind: str = "terminal"  # terminal | desktop
    icon: str = "\u25a0"
    default_name: str = "Ubuntu Quick Start"
    description: str = (
        "A single Ubuntu container for quickly exploring Practicum with no topology to configure."
    )
    hint: str = "one host, no network setup required."
    cpu: float = 1
    memory_mb: int = 1024
    shm_size_mb: int | None = None
    port_mappings: tuple[tuple[int, int], ...] = ()  # (host, container), tcp
    environment: tuple[tuple[str, str], ...] = ()
    default_options: tuple[str, ...] = ()  # PACKAGE_CATALOG keys preselected for this template
    packages_caption: str = "Pre-install packages onto the base image (installed at first start)."
    available: bool = True
    unavailable_reason: str = ""


WEBTOP_IMAGE = "lscr.io/linuxserver/webtop:ubuntu-xfce"
# LinuxServer.io images install extra distro packages at first start through this mod;
# packages are pipe-separated. Needs internet inside the container, like apt-get does.
LINUXSERVER_PACKAGE_MOD = "linuxserver/mods:universal-package-install"

TEMPLATES: tuple[QuickStartTemplate, ...] = (
    QuickStartTemplate(
        key="ubuntu-desktop",
        title="Ubuntu Desktop",
        caption="Desktop in the browser",
        image=WEBTOP_IMAGE,
        base_label="Ubuntu desktop (XFCE) base",
        kind="desktop",
        icon="\u25a3",  # ▣ a screen with content
        default_name="Ubuntu Desktop Quick Start",
        description=(
            "A full Ubuntu desktop that opens in Practicum's lab view - point and click, no "
            "terminal needed. Good for simple or non-IT labs."
        ),
        hint="a full desktop in your browser, no terminal or network setup required.",
        cpu=2,
        memory_mb=2048,
        shm_size_mb=1024,
        port_mappings=((3000, 3000), (3001, 3001)),
        packages_caption=(
            "Optional: Ubuntu packages to add to the desktop at first start (e.g. libreoffice, "
            "gimp). The desktop already comes with a browser, file manager and terminal."
        ),
    ),
    QuickStartTemplate(
        key="ubuntu",
        title="Ubuntu",
        caption="Terminal only",
        image="ubuntu:22.04",
        base_label="Ubuntu 22.04 base",
        kind="terminal",
        icon="\u203a_",  # ›_ a prompt
        hint="one host you work in through Open shell; no network setup required.",
        default_options=("git", "python3", "curl"),
        packages_caption="Pre-install packages onto the base Ubuntu 22.04 image.",
    ),
    QuickStartTemplate(
        key="windows",
        title="Windows",
        caption="Windows template",
        image="",
        base_label="Windows base",
        icon="\u25a6",  # ▦ window panes
        available=False,
        unavailable_reason=(
            "Coming soon. Windows containers need Docker Desktop switched to Windows "
            "container mode, which Practicum does not drive yet."
        ),
    ),
)


@dataclass(frozen=True)
class PackageOption:
    """A curated, popular package (or small group) students/instructors often want."""

    key: str  # what the chip shows
    packages: tuple[str, ...]  # apt package names installed for it
    description: str
    kinds: tuple[str, ...] = ("terminal", "desktop")


PACKAGE_CATALOG: tuple[PackageOption, ...] = (
    PackageOption("git", ("git",), "Git version control"),
    PackageOption("python3", ("python3", "python3-pip"), "Python 3 with pip"),
    PackageOption("nodejs", ("nodejs", "npm"), "Node.js with npm"),
    PackageOption("java", ("default-jdk",), "Java development kit"),
    PackageOption("build-essential", ("build-essential",), "C/C++ compiler and make"),
    PackageOption("curl", ("curl",), "Fetch URLs from the command line"),
    PackageOption("wget", ("wget",), "Download files"),
    PackageOption("jq", ("jq",), "Work with JSON in the shell"),
    PackageOption("nano", ("nano",), "Simple text editor", ("terminal",)),
    PackageOption("vim", ("vim",), "Vim editor", ("terminal",)),
    PackageOption("ping", ("iputils-ping",), "ping", ("terminal",)),
    PackageOption("ip tools", ("iproute2",), "ip addr / ip route", ("terminal",)),
    PackageOption("net-tools", ("net-tools",), "ifconfig, netstat", ("terminal",)),
    PackageOption("traceroute", ("traceroute",), "traceroute", ("terminal",)),
    PackageOption("tcpdump", ("tcpdump",), "Capture packets", ("terminal",)),
    PackageOption("nmap", ("nmap",), "Port scanner", ("terminal",)),
    PackageOption("ssh", ("openssh-client",), "ssh / scp clients", ("terminal",)),
    PackageOption("sqlite3", ("sqlite3",), "SQLite database shell"),
    PackageOption(
        "libreoffice", ("libreoffice",), "Office suite (Writer, Calc, Impress)", ("desktop",)
    ),
    PackageOption("gimp", ("gimp",), "Image editor", ("desktop",)),
    PackageOption("inkscape", ("inkscape",), "Vector graphics editor", ("desktop",)),
    PackageOption("vlc", ("vlc",), "Media player", ("desktop",)),
    PackageOption("audacity", ("audacity",), "Audio editor", ("desktop",)),
    PackageOption("thunderbird", ("thunderbird",), "E-mail client", ("desktop",)),
    PackageOption("filezilla", ("filezilla",), "FTP/SFTP client", ("desktop",)),
    PackageOption("keepassxc", ("keepassxc",), "Password manager", ("desktop",)),
    PackageOption(
        "vscodium",
        ("codium",),
        "VS Code (community build) - needs its repository; skip if unsure",
        ("desktop",),
    ),
)


def catalog_for(kind: str) -> tuple[PackageOption, ...]:
    return tuple(option for option in PACKAGE_CATALOG if kind in option.kinds)


def catalog_option(key: str) -> PackageOption | None:
    return next((option for option in PACKAGE_CATALOG if option.key == key), None)


DEFAULT_TEMPLATE = TEMPLATES[0]  # the desktop: the friendliest start (D-35)


def packages_for_options(keys: list[str] | tuple[str, ...]) -> list[str]:
    """Apt package names for catalogue keys (unknown keys are taken literally), deduplicated."""
    names: list[str] = []
    for key in keys:
        option = catalog_option(key)
        for name in option.packages if option else (key,):
            if name not in names:
                names.append(name)
    return names


DEFAULT_PACKAGES: tuple[str, ...] = tuple(packages_for_options(DEFAULT_TEMPLATE.default_options))
DEFAULT_NAME = DEFAULT_TEMPLATE.default_name
DEFAULT_DESCRIPTION = DEFAULT_TEMPLATE.description


@dataclass
class QuickStartStep:
    title: str
    details: str = ""


@dataclass
class QuickStartDraft:
    name: str = ""  # empty → the template's default name
    template: QuickStartTemplate = DEFAULT_TEMPLATE
    packages: list[str] | None = None  # None → the template's default packages
    steps: list[QuickStartStep] = field(default_factory=list)
    author: str = ""
    version: str = ""
    description: str = ""

    def __post_init__(self) -> None:
        if self.packages is None:
            self.packages = packages_for_options(self.template.default_options)


def template_by_key(key: str) -> QuickStartTemplate:
    return next((t for t in TEMPLATES if t.key == key), DEFAULT_TEMPLATE)


def validate_package_name(name: str) -> str | None:
    """None when `name` is an acceptable Debian package name, else the reason it is not."""
    if not name:
        return "Type a package name first."
    if not PACKAGE_NAME.match(name):
        return f"'{name}' is not a valid package name (lowercase letters, digits, '+', '.', '-')."
    return None


PACKAGE_STATUS_FILE = "/run/practicum-packages.status"
PACKAGE_LOG_FILE = "/var/log/practicum-packages.log"


def package_install_command(packages: list[str]) -> list[str] | None:
    """The node command that installs `packages` on first boot and then keeps the container
    alive. None (the spec default, `sleep infinity`) when there is nothing to install.

    The install runs in the background of the container's life, so the script keeps a
    one-line status in PACKAGE_STATUS_FILE ("installing …" → "ready" / "FAILED") that the
    Lab nodes table shows and that every login shell prints (`/etc/profile.d`); apt output
    goes to PACKAGE_LOG_FILE. A failed install leaves the shell usable.
    """
    if not packages:
        return None
    names = " ".join(packages)
    script = (
        "export DEBIAN_FRONTEND=noninteractive; "
        "mkdir -p /etc/profile.d /run; "
        f"printf '%s\\n' 'cat {PACKAGE_STATUS_FILE} 2>/dev/null' > /etc/profile.d/practicum.sh; "
        f"echo 'Practicum: installing packages ({names}) - this takes a minute or two; "
        f"re-open the shell to check' > {PACKAGE_STATUS_FILE}; "
        f"if (apt-get update -qq && apt-get install -y -qq {names}) > {PACKAGE_LOG_FILE} 2>&1; "
        f"then echo 'Practicum: packages ready ({names})' > {PACKAGE_STATUS_FILE}; "
        f"else echo 'Practicum: package install FAILED (is the container online? see "
        f"{PACKAGE_LOG_FILE})' > {PACKAGE_STATUS_FILE}; fi; "
        "exec sleep infinity"
    )
    return ["bash", "-c", script]


def desktop_package_environment(packages: list[str]) -> dict[str, str]:
    """Environment that makes a LinuxServer image install `packages` at first start."""
    if not packages:
        return {}
    return {"DOCKER_MODS": LINUXSERVER_PACKAGE_MOD, "INSTALL_PACKAGES": "|".join(packages)}


def steps_to_manual(steps: list[QuickStartStep]) -> dict | None:
    """One manual section per step (title + markdown details + one 'Done' task), so the
    instructions flyout shows them as numbered, checkable steps. None when there are none."""
    sections = []
    for number, step in enumerate(steps, start=1):
        title = step.title.strip()
        if not title:
            continue
        details = step.details.strip() or title
        sections.append(
            {
                "id": f"step-{number}",
                "title": title[:120],
                "content_markdown": details[:10000],
                "tasks": [{"id": "done", "text": f"Done: {title}"[:500]}],
            }
        )
    return {"sections": sections} if sections else None


def _pick_free_subnet(existing_subnets: Iterable[str]) -> IPv4Network:
    used: set[IPv4Network] = set()
    for subnet in existing_subnets:
        try:
            used.add(ip_network(subnet, strict=False))
        except ValueError:
            continue

    for candidate in QUICK_START_SUBNET_POOL.subnets(new_prefix=24):
        if not any(candidate.overlaps(taken) for taken in used):
            return candidate

    raise RuntimeError("No free quick-start subnet is available")


def build_quick_start_lab(
    draft: QuickStartDraft, existing_subnets: Iterable[str] = ()
) -> dict[str, object]:
    """A complete lab definition for `draft`, on a subnet that avoids `existing_subnets`."""
    template = draft.template
    subnet = _pick_free_subnet(existing_subnets)
    host_address = f"{subnet.network_address + 10}/{subnet.prefixlen}"
    resources: dict[str, object] = {"cpu": template.cpu, "memory_mb": template.memory_mb}
    if template.shm_size_mb is not None:
        resources["shm_size_mb"] = template.shm_size_mb
    if template.port_mappings:
        resources["port_mappings"] = [
            {"host": host, "container": container} for host, container in template.port_mappings
        ]
    node: dict[str, object] = {"id": "host", "image": template.image, "resources": resources}
    environment = dict(template.environment)
    if template.kind == "desktop":
        # The image's own init (s6) must run: keep its command and let the LinuxServer
        # package mod install the extras.
        node["command"] = None
        environment["TITLE"] = (draft.name.strip() or template.default_name)[:60]
        environment.update(desktop_package_environment(draft.packages))
    else:
        command = package_install_command(draft.packages)
        if command is not None:
            node["command"] = command
    if environment:
        node["environment"] = environment

    lab: dict[str, object] = {
        "schema_version": "1.0",
        "name": draft.name.strip() or template.default_name,
        "description": draft.description.strip() or template.description,
        "nodes": [node],
        "networks": [{"id": "lab-net", "subnet": str(subnet)}],
        "interfaces": [{"node": "host", "network": "lab-net", "address": host_address}],
    }
    if draft.author.strip():
        lab["author"] = draft.author.strip()
    if draft.version.strip():
        lab["version"] = draft.version.strip()
    manual = steps_to_manual(draft.steps)
    if manual is not None:
        lab["manual"] = manual
    return lab


# Mirrors examples/ubuntu-quickstart.json; the one-click sample used before the Quick
# start screen existed. Kept for the bundled sample/import tests.
UBUNTU_QUICK_START_LAB: dict[str, object] = {
    "schema_version": "1.0",
    "name": "Ubuntu Quick Start",
    "description": (
        "A single plain Ubuntu container for quickly exploring Practicum with no topology "
        "to configure."
    ),
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
                    '```\ndocker ps --filter "name=practicum"\n```\n\n'
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
    "interfaces": [{"node": "ubuntu", "network": "lab-net", "address": "10.50.0.10/24"}],
}


def existing_lab_subnets(api_client: ApiClient) -> list[str]:
    """Every subnet used by a lab the API knows about (so a quick start can avoid them)."""
    subnets: list[str] = []
    labs_result = api_client.list_labs()
    if not labs_result.success:
        return subnets
    for lab in labs_result.labs:
        preview = api_client.get_preview(lab.id)
        if preview.success:
            subnets.extend(network.subnet for network in preview.topology.networks)
    return subnets


def create_quick_start_lab(api_client: ApiClient, draft: QuickStartDraft) -> CreateLabResult:
    """Builds the lab for `draft` on a free subnet and saves it with origin=quick_start."""
    lab = build_quick_start_lab(draft, existing_lab_subnets(api_client))
    return api_client.create_lab(lab, origin="quick_start")
