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
