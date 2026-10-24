# Visual Topology Builder (Basic)

## User Story

As an instructor building a custom lab,
I want to see my machines and networks laid out visually as I add them,
so that I can understand and double-check my topology without reading raw tables.

## Why This Matters

The current Designer Mode (`designer-add-nodes.md`, `designer-add-networks.md`, `designer-connect-nodes-networks.md`) is implemented as plain CRUD tables with no visual feedback — it works, but it's hard to "see" the topology you've built, especially once a lab has several machines and networks. This story upgrades the presentation layer only: a card-based machine list, a schematic (not freeform) topology preview, and a networks panel, all backed by the exact same validated data model and API calls as today.

**Scope boundary:** this story is intentionally limited to static, form-driven visualization — add/remove/connect via buttons and fields, with the topology rendered automatically as a result. It does not include freeform drag-and-drop placement or auto-layout algorithms. Those are explicitly the subject of `future-roadmap/advanced-designer-features/advanced-visual-topology-designer.md`, which is flagged there as a candidate paid feature. Per `future-roadmap/open-source-core-sustainability/open-core-boundary.md`, basic topology editing must remain open source, so this story stays on the free side of that line — it should not be scoped up into drag-and-drop canvas work without revisiting that boundary decision first.

## User Flow

1. The instructor adds a machine (id, Docker image) via a form; it appears as a card in a Machines panel.
2. The instructor adds a network (id, subnet) via a form; it appears in a Networks panel.
3. The instructor connects a machine to a network with an address; the Network Topology panel automatically redraws to show the machine, the network segment, and its subnet label, in the order the connections were made.
4. The instructor can remove any machine, network, or connection; the topology view updates immediately.
5. Validation errors (duplicate IDs, an address outside its subnet, etc.) continue to show inline next to the relevant field, as today, with no change to the underlying validation rules.
6. Save/Validate continue to call the same existing API endpoints as the current Designer.

## Functional Requirements

- The Machines, Networks, and Network Topology panels all reflect the same in-memory draft state used for Validate/Save today — no new data model.
- The topology view is read-when-not-editing and only reflects connections that have actually been added; it does not infer or guess topology.
- Existing validation rules and error messages are preserved; this story changes presentation, not validation logic.
- The topology view scales to a handful of machines/networks without requiring scrolling for small labs, and scrolls gracefully for larger ones.

## Acceptance Criteria

- Adding a machine shows it as a card with its id and image.
- Adding a network shows it in the networks panel with its id and subnet.
- Connecting a machine to a network updates the topology view to show that connection and its subnet label.
- Removing a machine, network, or connection updates all affected panels immediately.
- Existing Validate and Save behavior, including error messages, is unchanged.

## Edge Cases

- A machine is connected to more than one network — the topology view must show all of its connections, not just the first.
- A lab has enough machines/networks that the topology view would overflow the available space — it should scroll rather than clip content.
- A validation error exists when the instructor tries to connect two things that are invalid together — the existing inline error pattern applies unchanged.

## Implementation Notes

- No API or data-model changes; this reuses the existing node/network/interface endpoints and validation exactly as implemented today.
- Reference design: `screen-custom` in the clickable mockup (`practicum-mockups.html`) — the Machines / Network Topology / Networks three-panel layout, including the node-card and connector-pill visual style.
- Explicitly out of scope: drag-and-drop canvas placement, auto-layout, and any other item listed under the paid "Advanced Visual Topology Designer" roadmap entry.

## Implementation Status

Done 2026-10-24 (Session 5): `DesignerDialog` became the `DesignerView` screen in `desktop/src/practicum_desktop/designer.py`, laid out like `screen-custom`.

- **Machines** panel: one card per machine (icon, id, image in monospace, derived role, ✕ remove) with the add form (id, image) at the bottom; **Network topology** panel: the schematic `TopologyView` (`widgets.py`) — cards in spec order, connectors with `network · subnet` pills between adjacent machines that share a network, every interface listed under its machine as `network · address`, networks without machines at the right — over the interfaces table and the connect form; **Networks** panel: rows (id, subnet, attached machines, ✕) with the add form.
- Removing a machine, network or connection updates all three panels and the status pill immediately. Role is derived from the interface count (1 → host, ≥2 → gateway; D-27, Tigre/11 C12).
- Validation rules and messages are unchanged and still shown inline next to the form that caused them; two client-side checks were added to mirror the server (overlapping subnets within the lab; network/broadcast address as an interface address). Validate → `POST /labs/validate`, **Save Lab** → `POST /labs` then back to the dashboard, **Save & Start** → save then the pre-start gate (D-29, Tigre/11 C2).
- No drag-and-drop or auto-layout (D-6). Editing an existing machine/network in place is still not offered (Tigre/11 S-7).
- Tests: `desktop/tests/test_designer.py` (14), `desktop/tests/test_widgets.py` (topology view). Verified end-to-end with the fake `docker` CLI (Save & Start → gate → running view with 3 nodes).
