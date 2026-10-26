"""Cross-package contract: the lab the desktop's Windows quick start builds must be a valid lab
for the core (the authoritative validator) and carry what the stories promise - a single node
on a pinned, host-compatible Windows Server Core tag, PowerShell declared, the user's steps as
manual sections. The bundled example must stay in sync with that builder.

The desktop package is imported from the repo checkout (skipped if it is not there)."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from practicum.models import LabDefinition

ROOT = Path(__file__).resolve().parents[1]
DESKTOP_SRC = ROOT / "desktop" / "src"
EXAMPLES = ROOT / "examples"

if DESKTOP_SRC.is_dir() and str(DESKTOP_SRC) not in sys.path:
    sys.path.insert(0, str(DESKTOP_SRC))
quickstart = pytest.importorskip("practicum_desktop.quickstart")


def _windows_draft(build: int | None, packages: list[str]) -> object:
    return quickstart.QuickStartDraft(
        name="PowerShell basics",
        template=quickstart.template_by_key("windows"),
        packages=packages,
        steps=[
            quickstart.QuickStartStep("Open PowerShell", "Use **Open PowerShell**."),
            quickstart.QuickStartStep("Check git", "```\ngit --version\n```"),
        ],
        windows_host_build=build,
    )


@pytest.mark.parametrize(
    ("host_build", "expected_tag"),
    [
        (None, "ltsc2022"),
        (17763, "ltsc2019"),
        (19045, "ltsc2019"),
        (22631, "ltsc2022"),
        (26100, "ltsc2025"),
    ],
)
def test_windows_quick_start_builds_a_valid_one_node_lab(host_build, expected_tag) -> None:
    raw = quickstart.build_quick_start_lab(_windows_draft(host_build, ["git", "7zip"]))

    lab = LabDefinition.model_validate(raw)  # the core is the authority on "valid"

    assert len(lab.nodes) == 1
    node = lab.nodes[0]
    assert node.image == f"mcr.microsoft.com/windows/servercore:{expected_tag}"
    assert node.os == "windows" and node.shell == "powershell"
    assert node.effective_shell == "powershell"
    assert lab.container_os == "windows"
    assert node.resources is not None and node.resources.shm_size_mb is None
    assert node.resources.sysctls == {}
    assert node.command is not None and node.command[0] == "powershell.exe"
    assert node.environment["PRACTICUM_PACKAGES"] == "git 7zip"
    assert [s.title for s in lab.manual.sections] == ["Open PowerShell", "Check git"]
    assert [t.text for s in lab.manual.sections for t in s.tasks] == [
        "Done: Open PowerShell",
        "Done: Check git",
    ]


def test_windows_quick_start_without_tools_is_valid_too() -> None:
    lab = LabDefinition.model_validate(quickstart.build_quick_start_lab(_windows_draft(None, [])))

    assert lab.nodes[0].environment == {}
    assert lab.nodes[0].os == "windows"


def test_ubuntu_quick_starts_are_unchanged_by_the_windows_work() -> None:
    for key in ("ubuntu", "ubuntu-desktop"):
        raw = quickstart.build_quick_start_lab(
            quickstart.QuickStartDraft(template=quickstart.template_by_key(key), packages=["git"])
        )
        node = raw["nodes"][0]
        assert "os" not in node and "shell" not in node  # spec defaults: linux, bash→sh
        assert not any(k.startswith("PRACTICUM_") for k in node.get("environment", {}))
        lab = LabDefinition.model_validate(raw)
        assert lab.container_os == "linux" and lab.nodes[0].effective_shell == "bash"
    terminal = quickstart.build_quick_start_lab(
        quickstart.QuickStartDraft(template=quickstart.template_by_key("ubuntu"), packages=["git"])
    )
    assert terminal["nodes"][0]["command"][:2] == ["bash", "-c"]
    assert "apt-get install -y -qq git" in terminal["nodes"][0]["command"][2]
    desktop = quickstart.build_quick_start_lab(
        quickstart.QuickStartDraft(
            template=quickstart.template_by_key("ubuntu-desktop"), packages=["gimp"]
        )
    )
    assert desktop["nodes"][0]["command"] is None
    assert desktop["nodes"][0]["environment"]["INSTALL_PACKAGES"] == "gimp"


def test_every_example_file_is_a_valid_lab() -> None:
    files = sorted(EXAMPLES.glob("*.json"))
    assert [f.name for f in files] == [
        "static-routing.json",
        "ubuntu-quickstart.json",
        "ubuntu-webtop.json",
        "windows-quickstart.json",
    ]
    for path in files:
        LabDefinition.model_validate(json.loads(path.read_text(encoding="utf-8")))


def test_windows_example_matches_the_current_template_builder() -> None:
    """The shipped example must install with the script the code ships - not a stale copy."""
    example = json.loads((EXAMPLES / "windows-quickstart.json").read_text(encoding="utf-8"))
    lab = LabDefinition.model_validate(example)
    node = lab.nodes[0]

    assert lab.container_os == "windows" and node.shell == "powershell"
    assert node.image == quickstart.DEFAULT_WINDOWS_IMAGE.image
    assert node.command == quickstart.windows_node_command()
    assert quickstart.decode_powershell(node.command[-1]) == quickstart.WINDOWS_INIT_SCRIPT
    assert node.environment == quickstart.windows_package_environment(["git", "7zip"])
