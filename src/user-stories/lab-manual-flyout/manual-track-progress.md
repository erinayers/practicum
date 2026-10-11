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
