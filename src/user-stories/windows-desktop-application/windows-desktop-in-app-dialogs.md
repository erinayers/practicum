# In-App Dialogs Only

## User Story

As a user of the Practicum desktop app,
I want every confirmation, warning, and error to appear inside the app's own window,
so that the app always feels like one self-contained program rather than a web page borrowing my browser's dialogs.

## Why This Matters

While reviewing an interactive mockup of these flows, a native browser `confirm()` popup appeared for a destructive action (deleting a lab) and visibly broke the illusion that this was a real desktop application. The same risk exists in the real PySide6 app if native Qt dialogs or OS message boxes are reached for for quick confirmations instead of styled, in-app components. This story makes "no native popups" an explicit, cross-cutting requirement rather than something each feature re-decides for itself.

## User Flow

1. Whenever the app needs to confirm a destructive action (deleting a lab, resetting a lab, discarding unsaved designer changes, etc.), it shows a modal rendered inside the app's own window: a dimmed backdrop behind a centered card matching the app's visual style.
2. The dialog clearly states what will happen, uses a visually distinct (e.g., red) action button for destructive confirmations, and always offers a clear way to cancel.
3. The same applies to error messages (e.g., a failed Start, a validation failure) — they appear as in-app banners, inline text, or modals, never as a native OS message box.
4. The one unavoidable exception is the system file-open dialog used for importing a lab file or browsing for a file manually — that dialog is inherently OS-native and is explicitly out of scope for this constraint.

## Functional Requirements

- A single, reusable in-app confirmation component exists and is used by every destructive action in the app, rather than each screen building its own.
- The component supports at minimum: a title, a message, a confirm label, a cancel label, and a "destructive" visual variant.
- No feature uses a native OS/Qt message box, confirm dialog, or alert for anything other than the unavoidable system file picker.

## Acceptance Criteria

- Deleting a lab from the Labs Dashboard shows the in-app confirmation component, not a native dialog.
- Resetting a running lab shows the in-app confirmation component, not a native dialog.
- Any other destructive or irreversible action added to the app in the future reuses this same component rather than introducing a new native dialog.
- The only native OS dialog anywhere in the app is the system file-open picker used during import.

## Edge Cases

- A confirmation is triggered while another modal is already open — only one should be visible/actionable at a time.
- The user presses Escape or clicks outside the dialog — this should behave the same as Cancel.
- A long error message needs to be shown — the component should handle multi-line text without breaking the layout.

## Implementation Notes

- Reference implementation: the `showConfirm(title, message, confirmLabel, destructive, onConfirm)` helper and `#confirmModal` component added to the clickable mockup (`practicum-mockups.html`) after a native `confirm()` was caught in review — build the real PySide6 equivalent (e.g., a shared `QDialog` subclass) from that pattern rather than from scratch.
- This story should land before or alongside `windows-desktop-labs-dashboard.md` and `windows-desktop-lab-lifecycle-controls.md`, since both depend on it for their destructive actions (Delete and Reset).
