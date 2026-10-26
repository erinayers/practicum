# Track Manual Progress

## User Story

As a student,  
I want to mark manual sections as complete,  
so that I can track my progress through the lab.

## Why This Matters

Progress tracking helps students pause and resume longer labs. It also separates student activity from the instructor's original content.

## User Flow

1. The student opens the manual.
2. The student completes a section or task.
3. The student marks it complete.
4. The app saves progress locally.
5. The app restores progress the next time the lab opens.

## Functional Requirements

- Manual sections or tasks are identifiable.
- Students can mark items complete.
- Progress is stored locally.
- Progress does not change the imported instructor spec.
- Students can reset progress separately from lab runtime resources.

## Acceptance Criteria

- Manual sections can have checkable tasks.
- Progress is stored locally.
- Progress does not modify the instructor's original spec.
- Resetting progress is available as a separate action.

## Edge Cases

- The instructor provides a new version of the same lab.
- Manual sections are reordered between versions.
- Local progress storage is unavailable.
- The student resets runtime resources but wants to keep manual progress.

## Implementation Notes

- Progress should key off stable section or task IDs.
- Do not store progress inside the exported instructor spec.

## Addendum 2026-10-25 — Export lab results (user request)

"I want to be able to export the lab results after a student has completed all of the lab
instructions." Done:

- Every tick now also records **when** (`manual_progress/<lab>/<section>/<task>_completed_at`,
  ISO 8601 with zone; cleared when unticked). Still local, still outside the instructor's spec.
- The instructions flyout's footer has **Export results** (enabled whenever the lab has tasks;
  when every task is ticked a green "All steps complete. Export your results to hand them in."
  banner appears above it). It asks for the student's name in an in-app dialog
  (`dialogs.ResultsExportDialog`, name remembered in `QSettings` `student_name`), then the
  system save picker, then writes the file.
- The file (`lab_results.py`, pure Python): `practicum-lab-results` 1.0 JSON - student, export
  time, lab facts (id, name, description, author, version, origin, source file), a summary
  (completed / total / all_complete / percent / first and last completion time) and every step
  with every task's `completed` + `completed_at`; or, with a `.md` name, a Markdown report with
  the same facts as a table. Suggested name `<lab>-results-<student>.json`.
- Acceptance: "Export results" produces a file listing all steps/tasks with completion state and
  times; works for partial progress too (gaps are visible, `all_complete` says whether the
  student finished); never alters the lab spec.
- Tests: `test_lab_results.py` (document, markdown, file formats, names), `test_manual.py`
  (timestamps, export control, banner), `test_running_view.py` (request carries the document),
  `test_main_window.py` (name dialog → picker → JSON / Markdown; cancel writes nothing),
  `test_dialogs.py`.
- Not done: sending results anywhere (the future-roadmap `lms-gradebook-export` idea builds on
  this file), signing/verifying results, and the "new lab version" edge cases above (progress
  still keys off section/task ids).

## Addendum 2026-10-25 — Screenshots as evidence (user request)

"In other lab software you can initiate a screenshot from the embedded window: (a) an option for
instructors to request a screenshot, (b) students take one from the embedded window or upload
their own."

- **Instructor (a).** `ManualSection.requires_screenshot` (spec, default false, schema still
  1.x). The shared step editor (quick start and designer) has an "Ask for a screenshot of this
  step" checkbox per step (`QuickStartStep.requires_screenshot`, `steps_to_manual` writes the
  flag only when set); the preview shows "Screenshot required …" under such steps.
- **Student (b).** Steps that require one show a screenshot row in the flyout (`manual.ScreenshotRow`):
  **Capture lab view** grabs the embedded web view (`EmbeddedLabView.capture()` - only when a
  web page is showing; otherwise it explains and points at upload, e.g. for terminal work),
  **Upload image…** opens the system image picker (`main_window.ask_image_path`, the third and
  last native dialog), **Remove** detaches. Images are stored as PNG under
  `<AppDataLocation>/screenshots/<lab>/<section>.png` (`screenshots.ScreenshotStore`; uploads are
  re-encoded and size-checked) and referenced from the same local progress keys as the ticks
  (`…/screenshot`, `…/screenshot_at`, `…/screenshot_source`). A thumbnail, the source and the time
  are shown. Reset progress deletes them too.
- **Completion.** A requested screenshot is an item of the step's progress: "N of M complete"
  counts tasks + requested screenshots, a step's marker turns done only with its screenshot
  attached, and with every task ticked but screenshots missing the footer says "attach the N
  requested screenshot(s) to finish".
- **Results export.** `practicum-lab-results` **1.1**: `steps[].requires_screenshot`,
  `steps[].screenshot {file, captured_at, source}` (null when missing), summary
  `screenshots_required` / `screenshots_attached`; `all_complete` needs every requested
  screenshot. JSON embeds each image (`png_base64` + `sha256`) so one file still hands in
  everything; a Markdown report copies the images into `<name>-screenshots/` beside it and links
  them; a new **Lab results bundle (*.zip)** holds `results.json`, `report.md` and
  `screenshots/`.
- Tests: core `test_models`; desktop `test_screenshots.py` (store), `test_manual.py` (row,
  progress rules, upload errors, reset), `test_manual_editor.py` (instructor flag round trip),
  `test_embedded_view.py` (capture only with a web page), `test_running_view.py` (capture /
  upload wiring, results), `test_main_window.py` (image picker), `test_lab_results.py`
  (document + JSON/MD/ZIP with images).
- Not done: annotating/cropping a capture, capturing a shell window (the console is a separate
  OS window - upload covers it), several screenshots per step.
