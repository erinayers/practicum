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
* **windows** — a Windows Server Core command-line sandbox with PowerShell
  (designer-windows-quick-start, designer-windows-quick-start-packages). The image tag is
  pinned from `WINDOWS_IMAGES`, the host/image compatibility matrix, for the host build the
  Docker daemon reports; never a floating `latest`. Tools are Chocolatey package ids
  (`WINDOWS_TOOL_CATALOG`), installed at first start by `WINDOWS_INIT_SCRIPT` - a PowerShell
  script handed to the container as `-EncodedCommand` (the only robust way to pass a script
  through Docker's Windows command-line quoting) that reads the package list from the
  readable `PRACTICUM_PACKAGES` environment variable, keeps a status marker the Lab nodes
  table and the PowerShell profile show, and then keeps the container alive. Needs Docker
  Desktop in Windows-container mode (windows-desktop-windows-container-readiness).

Subnets are drawn from a dedicated /16 (D-17) so repeated quick starts don't collide with
each other or with hand-authored labs.
"""

from __future__ import annotations

import base64
import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from ipaddress import IPv4Network, ip_network

from practicum_desktop.api_client import ApiClient, CreateLabResult

# A dedicated /16 reserved for auto-picked quick-start subnets.
QUICK_START_SUBNET_POOL = ip_network("10.90.0.0/16")

PACKAGE_NAME = re.compile(r"^[a-z0-9][a-z0-9+.\-]*$")  # Debian package names
CHOCO_PACKAGE_ID = re.compile(r"^[a-z0-9][a-z0-9._\-]*$")  # Chocolatey package ids (lowercased)
ID_SAFE = re.compile(r"[^a-z0-9-]+")


@dataclass(frozen=True)
class QuickStartTemplate:
    key: str
    title: str
    caption: str
    image: str
    base_label: str
    kind: str = "terminal"  # terminal | desktop | windows
    os: str = "linux"  # linux | windows - the Docker engine mode the template needs
    shell: str | None = None  # declared shell for Open shell (None = the OS default)
    icon: str = "\u25a0"  # text glyph (fallback); `icon_name` is the design icon
    icon_name: str = "terminal"
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
    # Wording of the package picker, which differs per package system (apt vs Chocolatey).
    catalog_title: str = "Popular software"
    catalog_hint: str = "Tick what the lab should come with - installed at first start."
    other_packages_title: str = "Other packages"
    package_placeholder: str = "Any Ubuntu package name, e.g. htop"
    install_note: str = (
        "Installing takes a minute or two after the lab starts; the Lab nodes table and the "
        "node's shell show when the packages are ready."
    )


WEBTOP_IMAGE = "lscr.io/linuxserver/webtop:ubuntu-xfce"
# LinuxServer.io images install extra distro packages at first start through this mod;
# packages are pipe-separated. Needs internet inside the container, like apt-get does.
LINUXSERVER_PACKAGE_MOD = "linuxserver/mods:universal-package-install"


@dataclass(frozen=True)
class WindowsImage:
    """One pinned Windows Server Core tag and the host it is built for. Windows containers
    must not be newer than the host (Hyper-V isolation runs older images on a newer host;
    process isolation needs the same build), so the chooser picks the newest tag whose build
    is at or below the daemon host's build."""

    tag: str
    build: int  # the OS build the image carries (and the minimum host build)
    label: str

    @property
    def image(self) -> str:
        return f"{WINDOWS_SERVERCORE_REPOSITORY}:{self.tag}"


WINDOWS_SERVERCORE_REPOSITORY = "mcr.microsoft.com/windows/servercore"
# Newest first. Source: Microsoft's Windows container version compatibility matrix
# (learn.microsoft.com/virtualization/windowscontainers/deploy-containers/version-compatibility).
WINDOWS_IMAGES: tuple[WindowsImage, ...] = (
    WindowsImage("ltsc2025", 26100, "Windows Server 2025"),
    WindowsImage("ltsc2022", 20348, "Windows Server 2022"),
    WindowsImage("ltsc2019", 17763, "Windows Server 2019"),
)
# Used when the host build is unknown (the template's listed image): runs on every supported
# Windows 11 / Server 2022+ host with Hyper-V isolation.
DEFAULT_WINDOWS_IMAGE = WINDOWS_IMAGES[1]
WINDOWS_MIN_HOST_BUILD = WINDOWS_IMAGES[-1].build


def windows_image_for_host(host_build: int | None) -> WindowsImage | None:
    """The newest Server Core tag compatible with `host_build`; the default when the build is
    unknown; None when the host is older than every supported image."""
    if host_build is None:
        return DEFAULT_WINDOWS_IMAGE
    return next((image for image in WINDOWS_IMAGES if image.build <= host_build), None)

TEMPLATES: tuple[QuickStartTemplate, ...] = (
    QuickStartTemplate(
        key="ubuntu-desktop",
        title="Ubuntu Desktop",
        caption="Desktop in the browser",
        image=WEBTOP_IMAGE,
        base_label="Ubuntu desktop (XFCE) base",
        kind="desktop",
        icon="\u25a3",  # ▣ a screen with content
        icon_name="desktop",
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
        icon_name="terminal",
        hint="one host you work in through Open shell; no network setup required.",
        default_options=("git", "python3", "curl"),
        packages_caption="Pre-install packages onto the base Ubuntu 22.04 image.",
    ),
    QuickStartTemplate(
        key="windows",
        title="Windows",
        caption="PowerShell sandbox",
        image=DEFAULT_WINDOWS_IMAGE.image,
        base_label=f"Windows Server Core ({DEFAULT_WINDOWS_IMAGE.label}) base",
        kind="windows",
        os="windows",
        shell="powershell",
        icon="\u203a_",
        icon_name="terminal",
        default_name="Windows Quick Start",
        description=(
            "A single Windows Server Core container with a PowerShell command line - a "
            "sandbox for Windows command-line tasks, not a Windows desktop. Needs Docker "
            "Desktop switched to Windows containers."
        ),
        hint="one Windows host you work in through Open PowerShell; no network setup required.",
        cpu=2,
        memory_mb=2048,
        default_options=("git",),
        packages_caption=(
            "Pre-install command-line tools onto the Windows Server Core image with "
            "Chocolatey (installed at first start; needs internet inside the container)."
        ),
        catalog_title="Popular tools",
        catalog_hint="Tick the tools the lab should come with - installed at first start.",
        other_packages_title="Other Chocolatey packages",
        package_placeholder="Any Chocolatey package id, e.g. 7zip",
        install_note=(
            "Installing takes several minutes after the lab starts (Chocolatey plus each "
            "tool); the Lab nodes table and the node's PowerShell show when the tools are ready."
        ),
    ),
)


@dataclass(frozen=True)
class PackageOption:
    """A curated, popular package (or small group) students/instructors often want.
    `packages` are apt package names for the Ubuntu kinds and Chocolatey package ids for
    the windows kind; `kinds` says which template kinds offer the option."""

    key: str  # what the chip shows
    packages: tuple[str, ...]  # package names/ids installed for it
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

# Windows-container-compatible command-line tools, as Chocolatey package ids
# (community.chocolatey.org). Only tools whose installers run unattended inside a Server
# Core container (no GUI installers, no drivers such as Npcap) are listed.
WINDOWS_TOOL_CATALOG: tuple[PackageOption, ...] = (
    PackageOption("git", ("git",), "Git version control", ("windows",)),
    PackageOption("python", ("python",), "Python 3 with pip", ("windows",)),
    PackageOption("nodejs", ("nodejs-lts",), "Node.js LTS with npm", ("windows",)),
    PackageOption("dotnet-sdk", ("dotnet-sdk",), ".NET SDK (dotnet CLI)", ("windows",)),
    PackageOption("openjdk", ("openjdk",), "Java development kit", ("windows",)),
    PackageOption("pwsh", ("powershell-core",), "PowerShell 7 (pwsh)", ("windows",)),
    PackageOption("7zip", ("7zip",), "7-Zip archiver (7z)", ("windows",)),
    PackageOption("curl", ("curl",), "Fetch URLs from the command line", ("windows",)),
    PackageOption("wget", ("wget",), "Download files", ("windows",)),
    PackageOption("jq", ("jq",), "Work with JSON in the shell", ("windows",)),
    PackageOption("vim", ("vim",), "Vim editor", ("windows",)),
    PackageOption("nano", ("nano",), "Simple text editor", ("windows",)),
    PackageOption("openssh", ("openssh",), "ssh / scp clients", ("windows",)),
    PackageOption("sqlite", ("sqlite",), "SQLite database shell", ("windows",)),
    PackageOption(
        "sysinternals", ("sysinternals",), "Sysinternals suite (PsExec, Procmon…)", ("windows",)
    ),
)
PACKAGE_CATALOG = PACKAGE_CATALOG + WINDOWS_TOOL_CATALOG


def catalog_for(kind: str) -> tuple[PackageOption, ...]:
    return tuple(option for option in PACKAGE_CATALOG if kind in option.kinds)


def catalog_option(key: str, kind: str | None = None) -> PackageOption | None:
    """The catalogue entry shown as `key` - for template `kind` when given, because the same
    key means different packages on Ubuntu and Windows ("python3"/"python", "git"/"git")."""
    options = catalog_for(kind) if kind else PACKAGE_CATALOG
    return next((option for option in options if option.key == key), None)


DEFAULT_TEMPLATE = TEMPLATES[0]  # the desktop: the friendliest start (D-35)


def packages_for_options(keys: list[str] | tuple[str, ...], kind: str | None = None) -> list[str]:
    """Package names/ids for catalogue keys of template `kind` (unknown keys are taken
    literally), deduplicated."""
    names: list[str] = []
    for key in keys:
        option = catalog_option(key, kind)
        for name in option.packages if option else (key,):
            if name not in names:
                names.append(name)
    return names


DEFAULT_PACKAGES: tuple[str, ...] = tuple(
    packages_for_options(DEFAULT_TEMPLATE.default_options, DEFAULT_TEMPLATE.kind)
)
DEFAULT_NAME = DEFAULT_TEMPLATE.default_name
DEFAULT_DESCRIPTION = DEFAULT_TEMPLATE.description


@dataclass
class QuickStartStep:
    """One instruction step: a manual section with (normally) a single "Done" task. Steps
    loaded from a hand-authored manual may carry their original `section_id` and `tasks`
    (see `manual_editor.ManualStepsEditor.load_manual`); both are kept as they were."""

    title: str
    details: str = ""
    section_id: str | None = None
    tasks: list[dict] | None = None
    requires_screenshot: bool = False  # the instructor asks the student for a screenshot


@dataclass
class QuickStartDraft:
    name: str = ""  # empty → the template's default name
    template: QuickStartTemplate = DEFAULT_TEMPLATE
    packages: list[str] | None = None  # None → the template's default packages
    steps: list[QuickStartStep] = field(default_factory=list)
    author: str = ""
    version: str = ""
    description: str = ""
    # Windows template: the daemon host's build (from the readiness check) picks the image tag.
    windows_host_build: int | None = None

    def __post_init__(self) -> None:
        if self.packages is None:
            self.packages = packages_for_options(
                self.template.default_options, self.template.kind
            )


def template_by_key(key: str) -> QuickStartTemplate:
    return next((t for t in TEMPLATES if t.key == key), DEFAULT_TEMPLATE)


def validate_package_name(name: str, kind: str = "terminal") -> str | None:
    """None when `name` is an acceptable package name for template `kind` (a Debian package
    name, or a Chocolatey package id for the Windows template), else the reason it is not."""
    if not name:
        return "Type a package name first."
    if kind == "windows":
        if not CHOCO_PACKAGE_ID.match(name):
            return (
                f"'{name}' is not a valid Chocolatey package id (letters, digits, '.', '_', "
                "'-'; look it up at community.chocolatey.org)."
            )
        return None
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


WINDOWS_PACKAGE_DIR = r"C:\practicum"
WINDOWS_PACKAGE_STATUS_FILE = r"C:\practicum\packages.status"  # read by GET /status (core)
WINDOWS_PACKAGE_LOG_FILE = r"C:\practicum\packages.log"
CHOCOLATEY_INSTALL_URL = "https://community.chocolatey.org/install.ps1"
CHOCOLATEY_EXE = r"C:\ProgramData\chocolatey\bin\choco.exe"
WINDOWS_PACKAGES_VARIABLE = "PRACTICUM_PACKAGES"  # space-separated Chocolatey ids
WINDOWS_PACKAGE_SOURCE_VARIABLE = "PRACTICUM_PACKAGE_SOURCE"

# The Windows node's init: the same contract as the Ubuntu script (status marker, log, shell
# banner, keep-alive), in PowerShell. It is generic - the package list comes from the node's
# environment - so the exported spec stays readable: the tools are in `environment`, the
# mechanism is this documented script. Each tool is installed on its own so a failure names
# the package. The all-users PowerShell profile prints the status on every Open PowerShell
# and refreshes PATH so freshly installed tools are found without a restart.
WINDOWS_INIT_SCRIPT = f"""\
$ErrorActionPreference = 'Continue'
$dir = '{WINDOWS_PACKAGE_DIR}'
$status = '{WINDOWS_PACKAGE_STATUS_FILE}'
$log = '{WINDOWS_PACKAGE_LOG_FILE}'
New-Item -ItemType Directory -Force -Path $dir | Out-Null
$profileScript = Join-Path $PSHOME 'profile.ps1'
@(
  "`$env:Path = [Environment]::GetEnvironmentVariable('Path', 'Machine') + ';' + " +
  "[Environment]::GetEnvironmentVariable('Path', 'User')",
  "if (Test-Path '$status') {{ Get-Content '$status' }}"
) | Set-Content -Path $profileScript
$packages = @()
if ($env:{WINDOWS_PACKAGES_VARIABLE}) {{
  $packages = @($env:{WINDOWS_PACKAGES_VARIABLE} -split ' ' | Where-Object {{ $_ }})
}}
if ($packages.Count -eq 0) {{
  'Practicum: ready (no extra tools selected)' | Set-Content -Path $status
}} else {{
  $names = $packages -join ' '
  "Practicum: installing tools ($names) with Chocolatey - this takes several minutes; re-open PowerShell to check" | Set-Content -Path $status
  $failed = @()
  $fatal = ''
  try {{
    [Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor 3072
    if (-not (Test-Path '{CHOCOLATEY_EXE}')) {{
      Invoke-Expression ((New-Object System.Net.WebClient).DownloadString('{CHOCOLATEY_INSTALL_URL}')) *>> $log
    }}
    if (-not (Test-Path '{CHOCOLATEY_EXE}')) {{ throw 'Chocolatey could not be installed (is the container online?)' }}
    foreach ($package in $packages) {{
      "--- choco install $package" | Add-Content -Path $log
      & '{CHOCOLATEY_EXE}' install $package -y --no-progress --limit-output *>> $log
      if ($LASTEXITCODE -ne 0) {{ $failed += $package }}
    }}
  }} catch {{
    $fatal = $_.Exception.Message
  }}
  if ($fatal) {{
    "Practicum: tool install FAILED - $fatal (see $log)" | Set-Content -Path $status
  }} elseif ($failed.Count -gt 0) {{
    "Practicum: tool install FAILED for $($failed -join ', ') - check each package id at community.chocolatey.org and that the container is online (see $log)" | Set-Content -Path $status
  }} else {{
    "Practicum: tools ready ($names)" | Set-Content -Path $status
  }}
}}
while ($true) {{ Start-Sleep -Seconds 3600 }}
"""


def encode_powershell(script: str) -> str:
    """`powershell -EncodedCommand` form of `script` (base64 of UTF-16LE)."""
    return base64.b64encode(script.encode("utf-16-le")).decode("ascii")


def decode_powershell(encoded: str) -> str:
    return base64.b64decode(encoded).decode("utf-16-le")


def windows_node_command(script: str = WINDOWS_INIT_SCRIPT) -> list[str]:
    """The Windows node's start command: PowerShell running `script`, which ends in a
    keep-alive loop so the container stays up for `docker exec`. No argument contains a
    space or a quote, so it survives Docker's Windows command-line escaping unchanged."""
    return [
        "powershell.exe",
        "-NoLogo",
        "-NoProfile",
        "-NonInteractive",
        "-ExecutionPolicy",
        "Bypass",
        "-EncodedCommand",
        encode_powershell(script),
    ]


def windows_package_environment(packages: list[str]) -> dict[str, str]:
    """Environment that tells WINDOWS_INIT_SCRIPT which Chocolatey packages to install; empty
    when there is nothing to install (the script then just reports ready)."""
    if not packages:
        return {}
    return {
        WINDOWS_PACKAGES_VARIABLE: " ".join(packages),
        WINDOWS_PACKAGE_SOURCE_VARIABLE: "chocolatey",
    }


def steps_to_manual(steps: list[QuickStartStep]) -> dict | None:
    """One manual section per step (title + markdown details + one 'Done' task), so the
    instructions flyout shows them as numbered, checkable steps. None when there are none.
    A step's own `section_id` / `tasks` (from a loaded manual) win over the generated ones;
    ids are kept unique in any case."""
    sections = []
    used_ids: set[str] = set()
    for number, step in enumerate(steps, start=1):
        title = step.title.strip()
        if not title:
            continue
        details = step.details.strip() or title
        section_id = step.section_id if step.section_id and step.section_id not in used_ids else ""
        if not section_id:
            section_id = f"step-{number}"
            suffix = 1
            while section_id in used_ids:
                suffix += 1
                section_id = f"step-{number}-{suffix}"
        used_ids.add(section_id)
        tasks = (
            [dict(task) for task in step.tasks]
            if step.tasks is not None
            else [{"id": "done", "text": f"Done: {title}"[:500]}]
        )
        section: dict = {
            "id": section_id,
            "title": title[:120],
            "content_markdown": details[:10000],
            "tasks": tasks,
        }
        if step.requires_screenshot:
            section["requires_screenshot"] = True
        sections.append(section)
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
    image = template.image
    if template.kind == "windows":
        chosen = windows_image_for_host(draft.windows_host_build)
        if chosen is None:
            raise ValueError(
                f"No supported Windows Server Core image runs on this host (build "
                f"{draft.windows_host_build}); Windows Quick Start needs build "
                f"{WINDOWS_MIN_HOST_BUILD} ({WINDOWS_IMAGES[-1].label}) or newer."
            )
        image = chosen.image
    node: dict[str, object] = {"id": "host", "image": image, "resources": resources}
    if template.os != "linux":
        node["os"] = template.os
    if template.shell is not None:
        node["shell"] = template.shell
    environment = dict(template.environment)
    if template.kind == "windows":
        node["command"] = windows_node_command()
        environment.update(windows_package_environment(draft.packages))
    elif template.kind == "desktop":
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
