from __future__ import annotations

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
    LINUXSERVER_PACKAGE_MOD,
    PACKAGE_CATALOG,
    PACKAGE_LOG_FILE,
    PACKAGE_STATUS_FILE,
    TEMPLATES,
    WEBTOP_IMAGE,
    QuickStartDraft,
    QuickStartStep,
    build_quick_start_lab,
    catalog_for,
    catalog_option,
    create_quick_start_lab,
    desktop_package_environment,
    existing_lab_subnets,
    package_install_command,
    packages_for_options,
    steps_to_manual,
    template_by_key,
    validate_package_name,
)


def test_templates_offer_desktop_terminal_and_a_not_yet_available_windows() -> None:
    assert [t.key for t in TEMPLATES] == ["ubuntu-desktop", "ubuntu", "windows"]
    desktop, terminal, windows = TEMPLATES
    assert DEFAULT_TEMPLATE is desktop  # the friendliest start for non-IT labs (D-35)
    assert desktop.kind == "desktop" and desktop.image == WEBTOP_IMAGE
    assert desktop.port_mappings == ((3000, 3000), (3001, 3001))
    assert desktop.default_options == ()
    assert terminal.kind == "terminal" and terminal.image == "ubuntu:22.04"
    assert terminal.default_options == ("git", "python3", "curl")
    assert packages_for_options(terminal.default_options) == [
        "git",
        "python3",
        "python3-pip",
        "curl",
    ]
    assert windows.available is False
    assert "Coming soon" in windows.unavailable_reason
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
        for name in option.packages:
            assert validate_package_name(name) is None, name


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
