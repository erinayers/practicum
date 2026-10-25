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

Not started.
