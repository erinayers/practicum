# Choose Windows Tools in Quick Start

## User Story

As an instructor configuring a Windows Quick Start,
I want to choose supported Windows command-line tools to include,
so that students receive a useful sandbox without writing an installation script themselves.

## Functional Requirements

- Provide a curated catalog of Windows-container-compatible command-line tools, with package IDs
  and short descriptions.
- Allow instructors to add and remove catalog selections and enter additional supported package
  IDs.
- Validate package IDs and present install failures with the package name and actionable details.
- Install selected tools using a repeatable Windows-container build or initialization mechanism;
  do not reuse the Ubuntu `apt-get` or LinuxServer package paths.
- Show install progress in the existing per-node startup progress UI and make the final result
  visible from the node status and PowerShell shell.
- Keep image versions and package sources explicit so an exported lab can be reproduced.

## Acceptance Criteria

- Catalog chips and a custom package field are available only for the Windows template.
- Invalid and duplicate package IDs are rejected before lab creation.
- The resulting Windows lab installs the selected tools using the documented Windows-specific
  mechanism.
- Successful, in-progress, and failed package installation states are visible to the user.
- Ubuntu terminal and Ubuntu Desktop package selection and installation remain unchanged.

## Dependencies

- `designer-windows-quick-start.md`
- `windows-desktop-windows-container-readiness.md`
- `windows-desktop-open-windows-shell.md`

## Implementation Status

**Done 2026-10-25** (Session 6).

- **Catalog.** `quickstart.WINDOWS_TOOL_CATALOG` - 15 Windows-container-compatible command-line
  tools as Chocolatey package ids with short descriptions (git, python, nodejs-lts, dotnet-sdk,
  openjdk, powershell-core, 7zip, curl, wget, jq, vim, nano, openssh, sqlite, sysinternals; no
  GUI installers or driver-based tools such as nmap/Npcap). It is only offered for the `windows`
  template kind; `catalog_option`/`packages_for_options` are kind-aware because the same chip key
  means different packages on Ubuntu and Windows ("git" → apt `git` vs choco `git`, "python"
  → choco `python`).
- **Picker.** The Quick start screen reuses the chip UI with Windows wording ("Popular tools",
  "Other Chocolatey packages", placeholder "Any Chocolatey package id, e.g. 7zip", a several-
  minutes install note). Custom ids are validated as Chocolatey ids (`^[a-z0-9][a-z0-9._-]*$`,
  lower-cased) with a link to community.chocolatey.org in the error; duplicates (incl. a chip's
  id) are rejected before creation.
- **Mechanism.** `WINDOWS_INIT_SCRIPT` (PowerShell, passed as `-EncodedCommand`) installs
  Chocolatey from `community.chocolatey.org/install.ps1` if absent, then `choco install <id> -y
  --no-progress` one package at a time, logging to `C:\practicum\packages.log`. The package list
  lives in the node's `environment` (`PRACTICUM_PACKAGES="git 7zip"`,
  `PRACTICUM_PACKAGE_SOURCE=chocolatey`) so an exported lab states explicitly what it installs;
  the image tag is pinned. Nothing from the Ubuntu paths (`apt-get` command, LinuxServer
  `DOCKER_MODS`) is reused, and those paths are unchanged.
- **Visibility.** The script keeps the status marker `C:\practicum\packages.status`
  ("installing tools (…)" → "tools ready (…)" / "tool install FAILED for <ids> - check each
  package id…"); the core reads it per OS (`cmd /c type`) into `GET /status` → the Lab nodes
  table ("running · installing…" / "install failed", full text in the status line) and the
  PowerShell profile prints it on every Open PowerShell.
- Tests: desktop `test_quickstart.py` (catalog, validation, script contract, environment),
  `test_create_lab.py` (Windows picker), core `test_runtime.py` (Windows note command).
- **Not yet verified on Windows**: Chocolatey inside Server Core needs internet in the container
  and .NET Framework 4.8 (present on ltsc2022/2025); some package installers may need
  adjustments discovered only on a real run.

### Acceptance criteria → tests

| Criterion | Tests |
|---|---|
| Catalog tools and custom ids available for Windows and validated before creation | desktop `test_quickstart.py::test_windows_tool_catalog_is_separate_and_maps_to_chocolatey_ids`, `::test_windows_package_ids_are_validated_as_chocolatey_ids`, `test_create_lab.py::test_windows_quick_start_offers_tool_chips_and_chocolatey_ids` (chips, invalid id, duplicate, custom id in the draft) |
| Installs through a documented, repeatable Windows-specific mechanism | `test_quickstart.py::test_windows_node_command_is_an_encoded_powershell_init_that_keeps_the_container_alive` (Chocolatey install, per-package `choco install`, no apt/LinuxServer), `::test_windows_template_builds_a_one_node_powershell_lab` (`PRACTICUM_PACKAGES` env); core `test_windows_quickstart_contract.py::test_windows_example_matches_the_current_template_builder` |
| Install progress and failures visible in the existing node status UI | script contract (`installing tools (…)` / `tools ready (…)` / `tool install FAILED for <ids>`) in `test_quickstart.py`; core `test_runtime.py::test_docker_runtime_reads_the_windows_note_marker_with_type` (`GET /status` note via `cmd /c type`); desktop `test_running_view.py::test_package_install_status_is_visible_in_the_nodes_table` (state suffix, tooltip, status line for installing / failed / ready). The PowerShell-profile banner needs the Windows run. |
| Ubuntu terminal and desktop package behaviour unchanged | core `test_windows_quickstart_contract.py::test_ubuntu_quick_starts_are_unchanged_by_the_windows_work`; desktop `test_quickstart.py::test_desktop_template_builds_a_webtop_lab_with_package_mod`, `::test_package_install_command_keeps_the_container_alive_and_reports_status`, `::test_build_quick_start_lab_assembles_a_complete_definition`, `test_create_lab.py::test_popular_software_chips_drive_the_package_list`, `::test_other_packages_can_be_added_removed_and_are_validated` |

## Scope note 2026-10-25

Windows containers require Windows 10/11 Pro, Enterprise or Education (Hyper-V and the
Containers features); Windows Home — the common student laptop — cannot run them. This feature
is therefore planned to move behind the paid tier; the implementation above stays as built and
the gating, eligibility check and hosted alternative are described in the roadmap epic
[Premium Lab Platforms](../../future-roadmap/premium-lab-platforms/README.md).
