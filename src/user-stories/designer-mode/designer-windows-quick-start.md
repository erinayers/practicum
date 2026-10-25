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

Not started.
