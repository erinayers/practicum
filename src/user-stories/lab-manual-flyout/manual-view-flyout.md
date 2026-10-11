# View Lab Manual While Working

## User Story

As a student,  
I want a lab manual flyout available while the lab is running,  
so that I can follow instructions without switching applications.

## Why This Matters

The manual is the student's guide through the exercise. Keeping it available inside the same app reduces friction and makes Practicum feel like one coherent learning workspace.

## User Flow

1. The student opens an imported lab.
2. The student opens the manual flyout.
3. The student reads objectives, steps, commands, and explanations.
4. The student collapses the manual and continues managing the lab.

## Functional Requirements

- The manual opens and closes from the lab view.
- The manual renders instructor-authored content.
- The manual supports headings, lists, code blocks, and links.
- The flyout does not prevent access to start, stop, status, or topology controls.
- The selected lab determines which manual is shown.

## Acceptance Criteria

- The manual can be opened and closed from the main lab view.
- The manual remains associated with the current lab.
- The manual supports headings, lists, code blocks, and links.
- The flyout does not block core lab controls.

## Edge Cases

- The lab has no manual.
- The manual contains a very long command.
- The manual contains an external link.
- The user switches labs while the flyout is open.

## Implementation Notes

- Markdown rendering is likely enough for the first version.
- Keep the flyout useful at small window sizes.
