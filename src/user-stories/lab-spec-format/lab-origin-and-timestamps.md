# Lab Origin and Activity Timestamps

## User Story

As a returning user looking at my labs dashboard,
I want each card to say where a lab came from and when I last used it,
so that I can tell "the file my instructor sent" from "the quick start I clicked yesterday" at a glance.

## Why This Matters

The dashboard mockup shows "Imported from python-api-lab.zip", "Quick start · Ubuntu · single host", "Last run yesterday" and "Opened 12 minutes ago". None of that existed in the stored lab (Tigre/11 C4, proposal S-5). It is bookkeeping about *this machine*, so it must not leak into the portable spec that students exchange.

## User Flow

1. A lab is created from the designer, from a quick start template, or by importing a file; the API records which.
2. The card's meta line reads "Custom lab · 3 machines · 2 networks", "Quick start · single host" or "Imported from static-routing.json".
3. The card's footer reads "Created 20 minutes ago" until the lab is first started, then "Last run yesterday" / "Started 12 minutes ago".
4. When a lifecycle action fails, the card shows the reason under the name and offers Reset.

## Functional Requirements

- The stored `Lab` carries `origin` (`designer` | `imported` | `quick_start`), `source_file` (file name, imports only), `created_at`, `last_started_at` and `last_error`.
- `POST /labs?origin=` (default `designer`) and `POST /labs/import?source_file=` set them; `POST /start` sets `last_started_at` on success; every lifecycle action sets or clears `last_error`.
- `GET /labs/{lab_id}/export` (and `move_subnet`, port/subnet recommendations) exclude these fields: the exported spec is unchanged, and rewriting a lab's definition preserves them.
- The desktop's `LabSummary` parses them (tolerating an older API without them) and `labels.py` words the meta and activity lines.

## Acceptance Criteria

- A created, quick-started and imported lab each report the matching `origin` (and `source_file` for the import) from `GET /labs`.
- The exported spec of any lab contains none of the bookkeeping fields.
- `last_started_at` is set after a successful start and `last_error` is cleared; a failed action sets `last_error`.
- Applying a port or subnet recommendation keeps `origin`, `source_file` and `created_at`.

## Edge Cases

- An older API without these fields — the desktop falls back to `designer` / no timestamps and still renders the cards.
- A lab file named with a path — only the file name is recorded (the desktop passes `Path.name`).

## Implementation Notes

- Core: `LAB_RUNTIME_FIELDS`, `LabOrigin` and the new `Lab` fields in `src/practicum/models.py`; `LabService.create(origin, source_file)`, `_with_definition`, timestamps in `start`/`stop`/`reset` (`src/practicum/service.py`); query parameters in `src/practicum/main.py`. Desktop: `LabSummary`, `ORIGIN_LABELS` (`api_client.py`), `labels.py` (`origin_meta`, `activity_line`, `relative_time`).
- Resolves Tigre/09 Q-6 (origin tracked API-side, not in the spec).

## Implementation Status

Done 2026-10-24 (Session 5). Tests: `tests/test_api.py` (`test_created_lab_records_origin_and_creation_time`, `test_successful_start_records_last_started_at_and_clears_last_error`, `test_port_recommendation_keeps_origin_and_timestamps`, export test), `tests/test_service.py::test_export_strips_local_bookkeeping_fields`, `desktop/tests/test_labels.py`, `desktop/tests/test_api_client.py::test_list_labs_parses_origin_timestamps_and_counts`.
