# Import Lab File and Launch

## User Story

As a student,
I want to pick a lab file from a familiar file-open dialog and have Practicum take care of the rest,
so that running an instructor's lab feels as simple as opening a document.

## Why This Matters

`student-import-spec.md` already covers the API-level contract for importing a spec (`POST /labs/import`). It has been updated to confirm that, for the common case of a clean, conflict-free lab, importing should flow straight into starting it, so a student never has to find and press a separate Start button for something they just opened. This story defines that desktop-specific file-picking and auto-start experience.

## User Flow

1. The user selects "Import Existing Lab" from the Welcome screen or the Labs Dashboard.
2. The app shows a native-style "Open Lab File" picker: a short list of recently-seen or sample lab files, plus a "Browse computer…" option that opens the real OS file picker.
3. The user picks a `.json` or `.zip` lab export and confirms.
4. The app sends the file to `POST /labs/import`, showing an "Importing lab definition…" progress state.
5. If the import fails validation, the app shows the structured errors from the API inline (see Edge Cases) and does not proceed.
6. If the import succeeds and has no port conflicts, the app proceeds directly into the start sequence and lands on the running view.
7. If the import succeeds but has port conflicts, the app shows the pre-start readiness gate (`windows-desktop-prestart-lab-gate.md`) instead of starting blindly, so the student can resolve them first.

## Functional Requirements

- The only native OS dialog involved is the unavoidable system file picker reached via "Browse computer…"; everything else (the file list, progress, and errors) is rendered in-app per `windows-desktop-in-app-dialogs.md`.
- Malformed files and schema validation errors are shown clearly, without technical stack traces.
- A successfully imported lab is added to the local lab list (visible afterward on the Labs Dashboard) regardless of whether it was also started.
- Import never silently discards a file that fails to parse — the user always sees why it did not proceed.

## Acceptance Criteria

- The user can select a lab file via a file-open affordance.
- Invalid or malformed files show a clear, specific error and the import does not proceed.
- A valid, conflict-free import proceeds straight to the running view without extra clicks.
- A valid import with port conflicts stops at the pre-start readiness gate instead of starting.
- The imported lab appears in the Labs Dashboard list afterward, whether or not it was started in the same flow.

## Edge Cases

- The selected file is not valid JSON or is a `.zip` without the expected structure.
- The file uses an unsupported `schema_version`.
- The same lab file is imported more than once (should this create a duplicate lab, or detect and offer to resume the existing one?) — needs a product decision before implementation.
- The Practicum API is unreachable when import is attempted — show the existing blocked/degraded state rather than a generic failure.
- Required images for the imported lab are not present locally and need to be pulled — communicate this during the start sequence rather than appearing stuck.

## Implementation Notes

- Backend already exists: `POST /labs/import`. This story is desktop UI only.
- Confirmed product direction: importing a conflict-free lab auto-starts it (see the updated `student-import-spec.md`); this is a deliberate UX decision, not an open question.
- Reference design: the "Open Lab File" modal and the import loading sequence in the clickable mockup (`practicum-mockups.html`, `importModal` / `importingOverlay`).
- Reuse the same multi-stage progress pattern for import as for Start (see `windows-desktop-lab-lifecycle-controls.md`) rather than building a second one.

## Implementation Status (2026-10-23)

Implemented in `desktop/src/practicum_desktop/import_lab.py` (`ImportLabDialog`) and `lab_file.py`, reached from the new **Import Lab File…** button in `main_window.py`. Decisions taken while building it:

- **`.zip` is not accepted.** No bundle format exists (see `student-import-spec.md` / Tigre S-13); picking a `.zip` shows a specific "choose the .json export" message rather than a JSON parse error. Re-add `.zip` to the file filter when a bundle format is defined.
- **Duplicate imports create a new lab each time** (the API's behaviour). Detecting and offering "resume the existing lab" needs a stable lab identity in the spec and is still an open product question.
- **Unsupported `schema_version`** is rejected by the API (`LabDefinition` now accepts only major version 1) and shown inline like any other schema error.
- **Recent/sample list**: recent files live in QSettings (`recent_lab_files`, newest first, max 8; missing files are greyed out); sample labs are copies of `examples/*.json` bundled inside the desktop package (`practicum_desktop/samples/`, kept byte-identical by a test).
- **"Browse computer…"** opens the system picker (the only native dialog in the app); choosing a file there is the confirmation, so the flow continues without a second "Open".
- **Running view**: the app has no dedicated running screen yet (`windows-desktop-embedded-lab-view.md`). After a started import the main window selects the lab, shows "imported and started", and opens the manual flyout. Re-point `MainWindow._apply_pending_selection` at the running view once it exists.
- **Port check cannot be answered** (API error mid-flow): treated like a conflict — the pre-start gate opens rather than starting blind.
- **API unreachable**: the dialog shows a blocked banner pointing at the main window's status/Retry; Open/Browse are disabled.
- **Image pulls**: the "Starting containers…" stage explains the first start may take minutes; `start_lab` now uses a 15-minute timeout. Real per-image progress remains `runtime-image-pull-progress.md`.

## Implementation Status (update 2026-10-24)

The import now passes the file name to `POST /labs/import?source_file=` so the dashboard card reads "Imported from <file>", and the start stage uses `wait=false` + status polling to show the real per-node progress (image downloads) instead of a fixed "Starting containers…" text. After the dialog, the main window lands on the running view when the lab started, or on the dashboard with a note otherwise.
