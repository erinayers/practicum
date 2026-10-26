# Author Lab Manual

## User Story

As an instructor,  
I want to write a lab manual inside the designer,  
so that students receive instructions with the environment.

## Why This Matters

The topology alone is not enough. Students need step-by-step guidance, objectives, commands, checkpoints, and explanations packaged with the lab.

## User Flow

1. The instructor opens the manual editor.
2. The instructor creates sections.
3. The instructor writes formatted content.
4. The instructor previews the student view.
5. The manual is saved with the lab draft and exported spec.

## Functional Requirements

- The instructor can create, edit, reorder, and delete manual sections.
- Manual content supports headings, lists, code blocks, and links.
- Manual content is stored in the lab spec or packaged beside it.
- The instructor can preview the manual.
- The manual preserves formatting across export and import.

## Acceptance Criteria

- The instructor can create manual sections.
- The instructor can write formatted instructional content.
- The manual is stored inside or alongside the lab spec.
- The instructor can preview the manual as a student would see it.

## Edge Cases

- Manual contains links to local files that will not exist on student machines.
- Manual contains very long code blocks.
- Instructor deletes a section after students have progress data in a later version.

## Implementation Notes

- Markdown is a good first format because it is portable and easy to render.
- Manual progress should remain student-local and separate from instructor content.

## Implementation Status

Done in two steps. The spec half (`LabManual` / `ManualSection` / `ManualTask`, export and
import preserving Markdown) landed in Phase 1; the designer half landed **2026-10-25** (user
request: "there isn't a section in build your own custom lab to add the lab manual").

- **Editor.** `desktop/src/practicum_desktop/manual_editor.py` — `ManualStepsEditor`, the step
  editor the Quick start screen already had, now shared: numbered steps with a title and
  Markdown details (headings, lists, code blocks with ```, links), add / remove / renumber.
  The Custom Lab designer shows it in a **Lab instructions** panel under the three topology
  panels (draggable vertical splitter, collapsible to its header with the step count; the
  status pill reports "… · N steps").
- **Storage.** Steps become manual sections through `quickstart.steps_to_manual` (one section
  per step, a "Done: <title>" task each) inside the lab spec - nothing is packaged beside it.
  Editing an existing lab (`DesignerView.load_lab`) loads its manual into the editor; sections
  with hand-authored tasks (several tasks, custom wording, none at all) or custom ids keep them
  (`QuickStartStep.section_id` / `.tasks`), and only the task the editor generated itself is
  regenerated when a step is renamed. Removing every step removes the manual.
- **Preview.** The panel's **Preview** switches to `ManualPreview`, which renders the steps the
  way the instructions flyout does (markers, `manual.markdown_to_html`, task boxes).
- Not done: reordering steps by drag (remove + re-add for now), per-task editing beyond what a
  hand-authored spec brings in, and versioned manuals (the "student progress after a section is
  deleted" edge case - progress keys stay per section id, so renamed ids lose their ticks).
- Tests: `desktop/tests/test_manual_editor.py`, `test_designer.py` (save with manual, edit
  preserving authored tasks, preview), `test_create_lab.py` (quick start unchanged).

### Acceptance criteria → tests

| Criterion | Tests |
|---|---|
| Create manual sections | `test_manual_editor.py::test_editor_adds_removes_and_renumbers_steps`, `test_designer.py::test_designer_saves_the_steps_as_the_labs_manual` |
| Write formatted content | Markdown details; `test_manual_editor.py::test_preview_renders_markdown_markers_and_tasks` (code block rendered), core `test_models` / flyout rendering tests |
| Manual stored inside the spec | `test_designer.py::test_designer_saves_the_steps_as_the_labs_manual`, `::test_editing_keeps_hand_authored_tasks_and_regenerates_only_generated_ones`, `test_manual_editor.py::test_load_manual_round_trips_and_keeps_authored_details`; core export/import tests |
| Preview as a student sees it | `test_manual_editor.py::test_preview_renders_markdown_markers_and_tasks`, `::test_preview_toggle_switches_pages_and_refreshes`, `test_designer.py::test_manual_preview_renders_steps_like_the_flyout` |
