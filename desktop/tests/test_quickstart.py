from __future__ import annotations

import base64
from ipaddress import ip_network

import pytest

from practicum_desktop.api_client import (
    CreateLabResult,
    LabsResult,
    LabSummary,
    PreviewResult,
    TopologyInfo,
    TopologyNetworkInfo,
)
from practicum_desktop.quickstart import (
    DEFAULT_NAME,
    DEFAULT_TEMPLATE,
    DEFAULT_WINDOWS_IMAGE,
    LINUXSERVER_PACKAGE_MOD,
    PACKAGE_CATALOG,
    PACKAGE_LOG_FILE,
    PACKAGE_STATUS_FILE,
    TEMPLATES,
    WEBTOP_IMAGE,
    WINDOWS_IMAGES,
    WINDOWS_INIT_SCRIPT,
    WINDOWS_PACKAGE_LOG_FILE,
    WINDOWS_PACKAGE_STATUS_FILE,
    WINDOWS_TOOL_CATALOG,
    QuickStartDraft,
    QuickStartStep,
    build_quick_start_lab,
    catalog_for,
    catalog_option,
    create_quick_start_lab,
    decode_powershell,
    desktop_package_environment,
    encode_powershell,
    existing_lab_subnets,
    package_install_command,
    packages_for_options,
    steps_to_manual,
    template_by_key,
    validate_package_name,
    windows_image_for_host,
    windows_node_command,
    windows_package_environment,
)


def test_templates_offer_desktop_terminal_and_windows() -> None:
    assert [t.key for t in TEMPLATES] == ["ubuntu-desktop", "ubuntu", "windows"]
    desktop, terminal, windows = TEMPLATES
    assert DEFAULT_TEMPLATE is desktop  # the friendliest start for non-IT labs (D-35)
    assert desktop.kind == "desktop" and desktop.image == WEBTOP_IMAGE
    assert desktop.port_mappings == ((3000, 3000), (3001, 3001))
    assert desktop.default_options == ()
    assert desktop.os == "linux" and desktop.icon_name == "desktop"
    assert terminal.kind == "terminal" and terminal.image == "ubuntu:22.04"
    assert terminal.default_options == ("git", "python3", "curl")
    assert terminal.icon_name == "terminal"
    assert packages_for_options(terminal.default_options, "terminal") == [
        "git",
        "python3",
        "python3-pip",
        "curl",
    ]
    assert windows.kind == "windows" and windows.os == "windows" and windows.shell == "powershell"
    assert windows.image == DEFAULT_WINDOWS_IMAGE.image
    assert "PowerShell" in windows.description and "not a Windows desktop" in windows.description
    assert "Chocolatey" in windows.packages_caption
    assert template_by_key("nope") is desktop


def test_desktop_template_builds_a_webtop_lab_with_package_mod() -> None:
    draft = QuickStartDraft(name="Office basics", packages=["libreoffice", "gimp"])

    lab = build_quick_start_lab(draft)

    node = lab["nodes"][0]
    assert node["image"] == WEBTOP_IMAGE
    assert node["command"] is None  # the image's own init must run
    assert node["resources"] == {
        "cpu": 2,
        "memory_mb": 2048,
        "shm_size_mb": 1024,
        "port_mappings": [
            {"host": 3000, "container": 3000},
            {"host": 3001, "container": 3001},
        ],
    }
    assert node["environment"] == {
        "TITLE": "Office basics",
        "DOCKER_MODS": LINUXSERVER_PACKAGE_MOD,
        "INSTALL_PACKAGES": "libreoffice|gimp",
    }
    assert lab["name"] == "Office basics"
    assert "desktop" in lab["description"].lower()


def test_desktop_template_without_packages_only_sets_the_title() -> None:
    lab = build_quick_start_lab(QuickStartDraft())

    node = lab["nodes"][0]
    assert node["environment"] == {"TITLE": "Ubuntu Desktop Quick Start"}
    assert lab["name"] == "Ubuntu Desktop Quick Start"
    assert desktop_package_environment([]) == {}


def test_package_name_validation() -> None:
    assert validate_package_name("git") is None
    assert validate_package_name("libssl-dev") is None
    assert validate_package_name("g++") is None
    assert "Type a package" in validate_package_name("")
    assert "not a valid package name" in validate_package_name("Git")
    assert "not a valid package name" in validate_package_name("rm -rf")


def test_windows_package_ids_are_validated_as_chocolatey_ids() -> None:
    assert validate_package_name("7zip", "windows") is None
    assert validate_package_name("nodejs-lts", "windows") is None
    assert validate_package_name("powershell-core", "windows") is None
    assert validate_package_name("dotnet_sdk.x64", "windows") is None
    assert "Type a package" in validate_package_name("", "windows")
    assert "Chocolatey package id" in validate_package_name("g++", "windows")
    assert "Chocolatey package id" in validate_package_name("rm -rf", "windows")
    assert "community.chocolatey.org" in validate_package_name("Bad Id", "windows")


def test_package_install_command_keeps_the_container_alive_and_reports_status() -> None:
    assert package_install_command([]) is None
    command = package_install_command(["git", "curl"])
    assert command[:2] == ["bash", "-c"]
    script = command[2]
    assert "apt-get install -y -qq git curl" in script
    assert script.endswith("exec sleep infinity")  # the node stays usable whatever happens
    # Visible progress: a status marker the Lab nodes table reads and login shells print.
    assert "installing packages (git curl)" in script
    assert f"> {PACKAGE_STATUS_FILE}" in script
    assert "packages ready (git curl)" in script and "install FAILED" in script
    assert "/etc/profile.d/practicum.sh" in script
    assert PACKAGE_LOG_FILE in script


def test_package_catalog_is_curated_per_template_kind() -> None:
    terminal_keys = [o.key for o in catalog_for("terminal")]
    desktop_keys = [o.key for o in catalog_for("desktop")]
    assert {"git", "python3", "nodejs", "curl"} <= set(terminal_keys) & set(desktop_keys)
    assert "tcpdump" in terminal_keys and "tcpdump" not in desktop_keys
    assert "libreoffice" in desktop_keys and "libreoffice" not in terminal_keys
    assert catalog_option("python3").packages == ("python3", "python3-pip")
    assert catalog_option("nope") is None
    assert packages_for_options(["python3", "python3", "htop"]) == [
        "python3",
        "python3-pip",
        "htop",
    ]
    for option in PACKAGE_CATALOG:
        kind = "windows" if option.kinds == ("windows",) else "terminal"
        for name in option.packages:
            assert validate_package_name(name, kind) is None, name


def test_windows_tool_catalog_is_separate_and_maps_to_chocolatey_ids() -> None:
    windows_keys = [o.key for o in catalog_for("windows")]
    assert [o.key for o in WINDOWS_TOOL_CATALOG] == windows_keys
    assert {"git", "python", "nodejs", "7zip", "pwsh", "jq"} <= set(windows_keys)
    assert "tcpdump" not in windows_keys and "libreoffice" not in windows_keys
    assert all(o.kinds == ("windows",) for o in WINDOWS_TOOL_CATALOG)
    # Same key, different package system: "git" is apt's git on Ubuntu and choco's on Windows;
    # "python" → Chocolatey's `python`, never the apt pair.
    assert catalog_option("python", "windows").packages == ("python",)
    assert catalog_option("python", "terminal") is None
    assert catalog_option("nodejs", "windows").packages == ("nodejs-lts",)
    assert catalog_option("nodejs", "terminal").packages == ("nodejs", "npm")
    assert packages_for_options(["git", "nodejs", "pwsh", "7zip"], "windows") == [
        "git",
        "nodejs-lts",
        "powershell-core",
        "7zip",
    ]
    for option in WINDOWS_TOOL_CATALOG:
        assert option.description


def test_steps_become_one_manual_section_each_with_a_done_task() -> None:
    manual = steps_to_manual(
        [
            QuickStartStep("Install dependencies", "pip install -r requirements.txt"),
            QuickStartStep("   ", "ignored: no title"),
            QuickStartStep("Start the API"),
        ]
    )

    assert [s["id"] for s in manual["sections"]] == ["step-1", "step-3"]
    first = manual["sections"][0]
    assert first["title"] == "Install dependencies"
    assert first["content_markdown"] == "pip install -r requirements.txt"
    assert first["tasks"] == [{"id": "done", "text": "Done: Install dependencies"}]
    assert manual["sections"][1]["content_markdown"] == "Start the API"  # falls back to title
    assert steps_to_manual([]) is None


def test_build_quick_start_lab_assembles_a_complete_definition() -> None:
    draft = QuickStartDraft(
        name="Explore network traffic",
        template=template_by_key("ubuntu"),
        packages=["git", "python3"],
        steps=[QuickStartStep("Open a shell", "Use Open shell.")],
        author="Dr. Ada",
        version="1.2",
        description="Look at packets.",
    )

    lab = build_quick_start_lab(draft)

    assert lab["schema_version"] == "1.0"
    assert lab["name"] == "Explore network traffic"
    assert lab["author"] == "Dr. Ada"
    assert lab["version"] == "1.2"
    assert lab["description"] == "Look at packets."
    node = lab["nodes"][0]
    assert node["id"] == "host"
    assert node["image"] == "ubuntu:22.04"
    assert node["resources"] == {"cpu": 1, "memory_mb": 1024}
    assert "environment" not in node
    assert "git python3" in node["command"][2]
    assert lab["networks"] == [{"id": "lab-net", "subnet": "10.90.0.0/24"}]
    assert lab["interfaces"] == [{"node": "host", "network": "lab-net", "address": "10.90.0.10/24"}]
    assert lab["manual"]["sections"][0]["title"] == "Open a shell"


def test_build_quick_start_lab_defaults_and_omits_empty_optional_fields() -> None:
    terminal = template_by_key("ubuntu")
    lab = build_quick_start_lab(
        QuickStartDraft(name="   ", template=terminal, packages=[], steps=[])
    )

    assert lab["name"] == terminal.default_name == "Ubuntu Quick Start"
    assert "author" not in lab and "version" not in lab and "manual" not in lab
    assert "command" not in lab["nodes"][0]  # spec default: sleep infinity
    assert lab["description"]
    assert DEFAULT_NAME == "Ubuntu Desktop Quick Start"


def test_draft_defaults_packages_from_its_template() -> None:
    assert QuickStartDraft().packages == []
    assert QuickStartDraft(template=template_by_key("ubuntu")).packages == [
        "git",
        "python3",
        "python3-pip",
        "curl",
    ]
    assert QuickStartDraft(packages=["x"]).packages == ["x"]
    assert QuickStartDraft(template=template_by_key("windows")).packages == ["git"]


# ----- windows template (designer-windows-quick-start, designer-windows-quick-start-packages) --


def test_windows_image_is_pinned_from_the_host_compatibility_matrix() -> None:
    assert [i.tag for i in WINDOWS_IMAGES] == ["ltsc2025", "ltsc2022", "ltsc2019"]
    assert all(
        i.image.startswith("mcr.microsoft.com/windows/servercore:ltsc") for i in WINDOWS_IMAGES
    )
    assert "latest" not in [i.tag for i in WINDOWS_IMAGES]
    assert windows_image_for_host(None) is DEFAULT_WINDOWS_IMAGE  # unknown host: ltsc2022
    assert windows_image_for_host(22631).tag == "ltsc2022"  # Windows 11 23H2
    assert windows_image_for_host(26100).tag == "ltsc2025"  # Windows 11 24H2 / Server 2025
    assert windows_image_for_host(20348).tag == "ltsc2022"  # Windows Server 2022
    assert windows_image_for_host(19045).tag == "ltsc2019"  # Windows 10 22H2
    assert windows_image_for_host(17763).tag == "ltsc2019"  # Windows 10 1809 / Server 2019
    assert windows_image_for_host(17134) is None  # older than every supported image


def test_windows_template_builds_a_one_node_powershell_lab() -> None:
    draft = QuickStartDraft(
        name="PowerShell basics",
        template=template_by_key("windows"),
        packages=["git", "7zip"],
        steps=[QuickStartStep("Open PowerShell", "Use Open PowerShell on the host node.")],
        windows_host_build=22631,
    )

    lab = build_quick_start_lab(draft)

    assert lab["name"] == "PowerShell basics"
    assert len(lab["nodes"]) == 1
    node = lab["nodes"][0]
    assert node["id"] == "host"
    assert node["image"] == "mcr.microsoft.com/windows/servercore:ltsc2022"
    assert node["os"] == "windows"
    assert node["shell"] == "powershell"
    assert node["resources"] == {"cpu": 2, "memory_mb": 2048}  # no shm/sysctls on Windows
    assert node["environment"] == {
        "PRACTICUM_PACKAGES": "git 7zip",
        "PRACTICUM_PACKAGE_SOURCE": "chocolatey",
    }
    assert node["command"] == windows_node_command()
    assert lab["manual"]["sections"][0]["title"] == "Open PowerShell"
    assert lab["networks"][0]["subnet"] == "10.90.0.0/24"


def test_windows_template_without_tools_has_no_package_environment() -> None:
    lab = build_quick_start_lab(QuickStartDraft(template=template_by_key("windows"), packages=[]))

    node = lab["nodes"][0]
    assert "environment" not in node
    assert node["image"] == DEFAULT_WINDOWS_IMAGE.image  # unknown host build → default tag
    assert windows_package_environment([]) == {}


def test_windows_template_refuses_an_unsupported_host() -> None:
    draft = QuickStartDraft(template=template_by_key("windows"), windows_host_build=17134)

    with pytest.raises(ValueError, match="No supported Windows Server Core image"):
        build_quick_start_lab(draft)


def test_windows_node_command_is_an_encoded_powershell_init_that_keeps_the_container_alive() -> (
    None
):
    command = windows_node_command()

    assert command[:-1] == [
        "powershell.exe",
        "-NoLogo",
        "-NoProfile",
        "-NonInteractive",
        "-ExecutionPolicy",
        "Bypass",
        "-EncodedCommand",
    ]
    assert not any(" " in part or '"' in part for part in command)  # Docker/Windows quoting safe
    script = decode_powershell(command[-1])
    assert script == WINDOWS_INIT_SCRIPT
    assert encode_powershell("x") == base64.b64encode("x".encode("utf-16-le")).decode()
    # Same contract as the Ubuntu script: status marker, log, shell banner, keep-alive.
    assert WINDOWS_PACKAGE_STATUS_FILE in script and WINDOWS_PACKAGE_LOG_FILE in script
    assert "$env:PRACTICUM_PACKAGES" in script  # packages come from the readable environment
    assert "choco.exe' install $package -y --no-progress" in script
    assert "community.chocolatey.org/install.ps1" in script
    assert "profile.ps1" in script and "Get-Content '$status'" in script  # printed on Open shell
    assert "installing tools ($names)" in script
    assert "tools ready ($names)" in script
    assert "tool install FAILED for $($failed -join ', ')" in script  # names the package
    assert script.rstrip().endswith("while ($true) { Start-Sleep -Seconds 3600 }")
    assert "apt-get" not in script and "DOCKER_MODS" not in script


def test_quick_start_subnet_avoids_existing_labs() -> None:
    lab = build_quick_start_lab(
        QuickStartDraft(), existing_subnets=["10.90.0.0/24", "10.90.1.0/24", "not-a-subnet"]
    )
    assert lab["networks"][0]["subnet"] == "10.90.2.0/24"
    assert lab["interfaces"][0]["address"] == "10.90.2.10/24"

    # A wider existing network overlapping the pool's first /24s is skipped as well.
    lab = build_quick_start_lab(QuickStartDraft(), existing_subnets=["10.90.0.0/23"])
    assert ip_network(lab["networks"][0]["subnet"]) == ip_network("10.90.2.0/24")


def test_quick_start_pool_exhaustion_is_reported() -> None:
    with pytest.raises(RuntimeError):
        build_quick_start_lab(QuickStartDraft(), existing_subnets=["10.90.0.0/16"])


class FakeApiClient:
    def __init__(self) -> None:
        self.created: list[tuple[dict, str]] = []

    def list_labs(self) -> LabsResult:
        return LabsResult(
            success=True, labs=[LabSummary("a", "A", "defined"), LabSummary("b", "B", "defined")]
        )

    def get_preview(self, lab_id: str) -> PreviewResult:
        subnet = {"a": "10.90.0.0/24", "b": "10.50.0.0/24"}[lab_id]
        return PreviewResult(
            success=True,
            topology=TopologyInfo(networks=[TopologyNetworkInfo("lab-net", subnet)]),
        )

    def create_lab(self, definition: dict, origin: str = "designer") -> CreateLabResult:
        self.created.append((definition, origin))
        return CreateLabResult(success=True, lab_id="new")


def test_create_quick_start_lab_avoids_existing_subnets_and_tags_origin() -> None:
    api = FakeApiClient()

    assert existing_lab_subnets(api) == ["10.90.0.0/24", "10.50.0.0/24"]
    result = create_quick_start_lab(api, QuickStartDraft(name="QS"))

    assert result.lab_id == "new"
    definition, origin = api.created[0]
    assert origin == "quick_start"
    assert definition["networks"][0]["subnet"] == "10.90.1.0/24"
