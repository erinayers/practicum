# Edit an Existing Lab

## User Story

As an instructor or student,
I want to open a lab I already have — including one created from a quick start template — in the designer and change its machines, networks and connections,
so that I can grow a simple lab into a topology without starting over.

## Why This Matters

Labs could only be created, never changed (Tigre/11 S-7, C3). The dashboard mockup shows "Edit" on a card, and a quick start lab is the natural seed for a bigger lab (user feedback, 2026-10-24: "want capability to edit topology even if the image was created from a quick start config").

## User Flow

1. On the dashboard, every card that is not running offers **Edit** (a running lab must be stopped first; the app says so).
2. The designer opens in edit mode ("Edit your lab"): name, description, author, version, machines, networks and connections are pre-filled; the manual is kept as it is.
3. The instructor changes the topology and chooses **Save changes** (back to the dashboard) or **Save & Start** (pre-start gate).
4. Saving replaces the definition on the API; the lab keeps its id, origin and timestamps and returns to **Ready**, so progress and the card stay where they were.

## Functional Requirements

- `PUT /labs/{lab_id}` replaces the whole definition, validated exactly like `POST /labs`; it keeps `id`, `origin`, `source_file`, `created_at`, `last_started_at`; status becomes `defined`, `last_error` is cleared.
- A running lab answers 409 ("stop it before editing"); a busy (starting/stopping) lab answers 409; a stopped/error lab's old containers and networks are removed first (they no longer match the spec) — if that fails the lab is kept and 409 explains.
- The desktop client exposes `get_lab` (full stored lab) and `update_lab`; the designer's `load_lab` enters edit mode and passes `schema_version` and `manual` through untouched.
- Manual progress is keyed by lab id and therefore survives an edit.

## Acceptance Criteria

- Edit on a stopped or ready card (any origin) opens the designer pre-filled with that lab.
- Saving calls `PUT /labs/{id}`; the lab keeps its id/origin/created time and shows as Ready on the dashboard.
- Editing a running lab is refused with a message, both by the app and by the API.
- The lab's manual is unchanged after an edit that only touched the topology.

## Edge Cases

- The quick start's desktop node (`command: null`, ports, env) round-trips through the designer unchanged when not touched.
- Validation errors from the API (e.g. an address outside its network) are shown inline and the draft is kept.
- The lab disappears between the card and the Edit click (API restarted) — the app says it is no longer in the list.

## Implementation Notes

- Core: `LabService.replace` + `LabRunningError` (`service.py`), `PUT /labs/{lab_id}` (`main.py`). Desktop: `ApiClient.get_lab/update_lab`, `DesignerView.load_lab` / `editing_lab_id` / `PASS_THROUGH_FIELDS`, `MainWindow._on_edit_requested`, dashboard **Edit** button.
- Was Tigre/11 S-7 (without the "store invalid drafts" half, which remains out of scope).

## Implementation Status

Done 2026-10-24 (Session 5, user feedback round). Tests: `tests/test_api.py` (`test_put_*`), `desktop/tests/test_api_client.py`, `desktop/tests/test_designer.py::test_load_lab_enters_edit_mode_and_saves_with_put`, `desktop/tests/test_main_window.py` (edit flow, running refusal). Windows run pending.
