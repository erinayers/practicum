# Create New Lab Screen

## User Story

As an instructor or student starting something new,
I want one screen that lets me choose between a quick single-host lab and a full custom lab,
so that I am not dropped into the designer when all I need is an Ubuntu box.

## Why This Matters

The clickable mockup's `screen-create` (two choice cards: Quick start with OS templates, Custom Lab with a mini topology) had no backing story (Tigre/11 finding #10). The real app only had a bare "Quick Start: Ubuntu" button that created a lab with a fixed subnet (Tigre/06 #1) and a "New Lab…" dialog.

## User Flow

1. From the welcome screen or the dashboard the user chooses **Create New Lab**.
2. The Create New Lab screen shows two cards side by side:
   - **Quick start** — "Single host": pick an operating-system template (Ubuntu available; Windows listed as coming soon and disabled) and continue to the quick start configuration (`designer-quick-start-lab.md`).
   - **Custom Lab** — "Multiple images": a small schematic (host — router — host) and a button into the designer (`designer-visual-topology-builder.md`).
3. "← Back to my labs" returns home (dashboard, or welcome when there are no labs).

## Functional Requirements

- The screen is part of the main window's screen stack, styled like the mockup (page head, two `.choice-card`s, footer "Powered by Docker").
- The template picker is a radio list; unavailable templates are disabled and explain why in a tooltip.
- The mini topology is the same schematic component the designer and the gate use, in compact mode.
- Choosing a card emits a navigation request only; no lab is created on this screen.

## Acceptance Criteria

- Create New Lab is reachable from both the welcome screen and the dashboard.
- The Ubuntu template is selected by default and the Windows template cannot be selected.
- "Quick start →" opens the quick start configuration for the selected template; "Custom Lab →" opens the designer.
- The back link returns to the user's home screen.

## Edge Cases

- The API is unreachable — the welcome screen disables Create/Import, so this screen is not reachable until Retry succeeds.

## Implementation Notes

- `desktop/src/practicum_desktop/create_lab.py` (`CreateLabScreen`, `ChoiceCard`, `TemplateOption`); templates come from `quickstart.TEMPLATES`.
- Reference design: `screen-create` in `design/practicum-mockups.html`.

## Implementation Status

Done 2026-10-24 (Session 5). Tests: `desktop/tests/test_create_lab.py` (chooser section), navigation covered in `desktop/tests/test_main_window.py::test_welcome_link_and_back_links_navigate`.
