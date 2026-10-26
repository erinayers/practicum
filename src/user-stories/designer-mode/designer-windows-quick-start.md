# Windows Quick Start Template

## User Story

As an instructor or student who wants to practice Windows command-line tasks,
I want a single-container Windows Quick Start with PowerShell,
so that I can use a Windows sandbox without designing a topology.

## Scope

The first Windows template is a Windows container with a PowerShell shell, not a full Windows
desktop or VM. It depends on `windows-desktop-windows-container-readiness.md`; Docker Desktop must
be configured to use a compatible Windows-container engine before creation or start.

## User Flow

1. The user chooses **Windows** from Create New Lab after Windows-container readiness succeeds.
2. Quick Start shows a Windows base image, supported resources, Windows package choices, and the
   same name and lab-instructions fields as other templates.
3. The user creates the lab; the pre-start gate checks conflicts and shows image-pull progress.
4. On start, the running view shows the node and the user can open a PowerShell shell.

## Functional Requirements

- Create one Windows container node and no user-configurable topology.
- Use a versioned Windows Server Core image tag selected from the supported host/image
  compatibility matrix; do not use a floating `latest` tag.
- Keep the container alive in a documented, interactive-ready PowerShell process.
- Apply Windows-container resource limits through the existing lab resource model.
- Preserve Quick Start lab naming, manual sections, origin metadata, conflict gate, image-pull
  progress, dashboard lifecycle actions, and export behavior.
- Describe the template as a command-line sandbox; do not promise an interactive Windows desktop.
- Disable creation/start when Windows-container readiness is lost and direct the user to retry the
  readiness check.

## Acceptance Criteria

- The Windows template is selectable only when Windows-container readiness passes.
- Creating it produces a valid one-node lab with a pinned, compatible Windows Server Core image,
  required resource settings, and the user's manual steps.
- The container starts with PowerShell available and remains running until the user stops or resets
  the lab.
- The normal pre-start gate reports image progress and any port or network conflicts.
- The dashboard can start, stop, restart, reset, export, and delete the Windows Quick Start using
  the existing lifecycle flow.
- If Docker switches back to Linux-container mode before start, the user receives a specific
  readiness error and can retry after switching modes.

## Dependencies

- `windows-desktop-windows-container-readiness.md`
- `windows-desktop-open-windows-shell.md`
- `designer-windows-quick-start-packages.md`

## Implementation Status

**Done 2026-10-25** (Session 6).

- **Spec.** `Node.os` (`linux` | `windows`, default `linux`) and `Node.shell` (`bash` | `sh` |
  `powershell` | `cmd`, default per OS) are declared on the node - never guessed from the image.
  Validation: all nodes of a lab share one OS; the shell must fit the OS; Windows nodes refuse
  `shm_size_mb` and `sysctls`. `LabDefinition.container_os`, `LabPreview.container_os`.
- **Template.** `quickstart.TEMPLATES[2]` ("Windows", kind `windows`, os `windows`, shell
  `powershell`): one `host` node, 2 vCPU / 2048 MB, no topology to configure. The image is
  pinned from `WINDOWS_IMAGES` - Microsoft's host/container compatibility matrix
  (ltsc2025 ≥ build 26100, ltsc2022 ≥ 20348, ltsc2019 ≥ 17763): `windows_image_for_host()` picks
  the newest Server Core tag the daemon host's build can run (the Create screen passes the build
  from the readiness check as `QuickStartDraft.windows_host_build`; unknown → ltsc2022; older
  hosts are refused with the minimum build named). Never `latest`.
- **Keep-alive.** The node command is `powershell.exe -NoLogo -NoProfile -NonInteractive
  -ExecutionPolicy Bypass -EncodedCommand <WINDOWS_INIT_SCRIPT>`: a documented PowerShell init
  (status marker `C:\practicum\packages.status`, all-users profile that prints it, then
  `while ($true) { Start-Sleep 3600 }`) so the container stays up for `docker exec`. The encoded
  form is the only quoting-proof way through Docker's Windows command line; the packages it
  installs are readable in `environment.PRACTICUM_PACKAGES`.
- **Runtime.** `DockerRuntime._require_engine_os()` fails a start early with the switch
  instructions when the engine serves the other kind of container (structured
  `success=false` + `last_error`, HTTP 200 as always); Windows labs get `--driver nat` networks
  (there is no `bridge` on Windows); the status note is read with `cmd /c type`.
- **Flows.** Quick start naming, steps → manual sections, origin `quick_start`, the gate
  (with the new Container engine check), image-pull progress, dashboard lifecycle actions
  (Start/Stop/Restart/Reset/Export/Delete/Edit) and export/import all reuse the existing paths;
  `origin_meta` says "Quick start · Windows · single host". The Create screen's description
  calls it a command-line sandbox, not a desktop. `examples/windows-quickstart.json` (also a
  bundled sample) is a ready-made export.
- Tests: desktop `test_quickstart.py` (matrix, template, command, refusal), `test_create_lab.py`,
  `test_main_window.py` (Create re-checks readiness; guard), core `test_models.py`,
  `test_runtime.py` (engine refusal both ways, nat driver, Windows note), `test_api.py`
  (export/import round trip, preview `container_os`, structured start failure). End-to-end
  against the live API with a stateful fake `docker` CLI (Linux mode → specific failure; switch
  → reset → start → running with the install note → stop/restart → export/import → delete).
- **Not yet run on Windows** with real Windows containers: Hyper-V vs process isolation, the
  first (multi-GB) Server Core pull and static `--ip` on user-defined `nat` networks are the
  things to watch (Tigre/06).

### Acceptance criteria → tests

| Criterion | Tests |
|---|---|
| Selectable only when readiness passes | desktop `test_create_lab.py::test_linux_engine_keeps_ubuntu_templates_and_explains_windows_with_links_and_retry`, `::test_windows_engine_enables_the_windows_template_and_disables_the_ubuntu_ones`, `::test_no_docker_explains_and_keeps_the_windows_cta_disabled`; `test_main_window.py::test_windows_quick_start_opens_with_the_host_build_and_is_guarded` (manually verified on the Create screen) |
| Create produces a valid one-node lab with a pinned, compatible image and the user's steps | core `test_windows_quickstart_contract.py::test_windows_quick_start_builds_a_valid_one_node_lab` (desktop builder → `LabDefinition.model_validate` for host builds None/17763/19045/22631/26100), `::test_windows_example_matches_the_current_template_builder`; desktop `test_quickstart.py::test_windows_image_is_pinned_from_the_host_compatibility_matrix`, `::test_windows_template_builds_a_one_node_powershell_lab`, `::test_windows_template_refuses_an_unsupported_host`; `test_main_window.py::test_windows_quick_start_create_rechecks_readiness_first` (created definition) |
| Persistent PowerShell process; existing pre-start, progress and lifecycle flows | desktop `test_quickstart.py::test_windows_node_command_is_an_encoded_powershell_init_that_keeps_the_container_alive`; core `test_runtime.py::test_docker_runtime_starts_a_windows_lab_with_a_nat_network` (argv), `test_api.py::test_windows_quick_start_follows_the_existing_lifecycle_flows` (preview/engine/ports → `wait=false` start + progress → stop/restart/reset/export/delete); desktop `test_prestart_gate.py::test_windows_lab_starts_through_the_same_gate_flow_with_pull_progress`, `test_dashboard.py::test_windows_quick_start_card_has_the_same_lifecycle_actions` |
| Engine-mode change after creation detected before start and explained | core `test_api.py::test_engine_mode_change_after_creation_blocks_the_start`, `::test_start_failure_from_engine_mode_is_a_structured_runtime_error`, `test_runtime.py::test_docker_runtime_refuses_to_start_a_windows_lab_on_a_linux_engine` (+ `_linux_lab_on_a_windows_engine`); desktop `test_prestart_gate.py::test_windows_lab_on_a_linux_engine_blocks_start_until_retry_sees_windows_mode`, `::test_linux_lab_on_a_windows_engine_is_blocked_with_the_switch_back_hint`, `test_import_lab.py::test_windows_lab_on_a_linux_engine_defers_to_the_gate_instead_of_starting`, `test_main_window.py::test_windows_quick_start_create_rechecks_readiness_first` |

## Scope note 2026-10-25

Windows containers require Windows 10/11 Pro, Enterprise or Education (Hyper-V and the
Containers features); Windows Home — the common student laptop — cannot run them. This feature
is therefore planned to move behind the paid tier; the implementation above stays as built and
the gating, eligibility check and hosted alternative are described in the roadmap epic
[Premium Lab Platforms](../../future-roadmap/premium-lab-platforms/README.md).
