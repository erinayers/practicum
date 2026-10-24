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

## Implementation Status (update 2026-10-24)

`ManualFlyout` is now a side panel inside the running view (the mockup's `.instructions-flyout`) instead of a `QDockWidget`: header "Lab instructions" with "N of M complete" and ×, one numbered step per manual section (marker turns green when all of its tasks are checked; the first open step is highlighted), the section's Markdown (code blocks wrap and are shaded), its tasks as checkboxes, and a footer "✓ Mark step complete" that ticks the next open task plus the existing "Reset progress". Toggled by the running view's Instructions button.

## Update 2026-10-24 (user feedback)

The flyout is now resizable (a splitter between the lab view and the instructions; minimum 240 px) and never scrolls sideways: titles, Markdown paragraphs and code blocks wrap to the panel width (labels use an ignored horizontal size policy so a long URL or container name cannot widen the panel), and tasks are a bare checkbox next to a wrapping label (`TaskRow`; QCheckBox itself cannot wrap).
