# Import Instructor Spec

## User Story

As a student,  
I want to import a lab spec provided by my instructor,  
so that I can run the assigned lab locally.

## Why This Matters

Import is the student's first step into a lab. It must be forgiving, clear, and trustworthy because students may receive files through many channels.

## User Flow

1. The student opens Import Mode.
2. The student selects a spec file from disk.
3. The app reads the file and validates the schema.
4. The app sends the definition to the local validation API.
5. Valid labs are added to the local lab list.
6. If the imported lab has no unresolved port conflicts, the app proceeds to start it automatically (see `windows-desktop-import-lab-file.md` in the Windows Desktop Application epic). If conflicts exist, the student resolves them via the pre-start readiness gate before the lab starts.

## Functional Requirements

- The student can choose a local spec file.
- The app rejects malformed JSON.
- The app validates the imported spec.
- Valid imports are stored locally.
- Imported labs are distinguished from drafts.

## Acceptance Criteria

- The student can select a spec file from disk.
- The app validates the imported file.
- Invalid files show clear errors.
- Valid files are added to the local lab list.

## Edge Cases

- The selected file is not JSON.
- The selected file uses an unsupported schema version.
- The same lab is imported multiple times.
- The API is unavailable during import.

## Implementation Notes

- A successfully imported lab is auto-started when it has no unresolved port conflicts, so importing feels like opening a document rather than a two-step process. See `windows-desktop-import-lab-file.md` for the desktop-specific flow and `windows-desktop-prestart-lab-gate.md` for what happens when conflicts exist instead.
- Keep the original imported spec immutable or recoverable.
